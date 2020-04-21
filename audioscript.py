filepath = "audio/"
output_filepath = "transcripts/"
audio_output = "audio_chunks/"
glob_id = 0
glob_end = 0

from pydub import AudioSegment
from pydub.silence import split_on_silence
import io
import os
import audioop
import math
from google.cloud import speech_v1p1beta1 as speech
from google.cloud.speech_v1p1beta1 import enums
from google.cloud.speech_v1p1beta1 import types
import wave
import subprocess
import sys
import tempfile
from google.cloud import storage

import pysrt

def percentile(arr, percent):
    arr = sorted(arr)
    index = (len(arr) - 1) * percent
    floor = math.floor(index)
    ceil = math.ceil(index)
    if floor == ceil:
        return arr[int(index)]
    low_value = arr[int(floor)] * (ceil - index)
    high_value = arr[int(ceil)] * (index - floor)
    return low_value + high_value

def mp3_to_wav(fname):
    if fname.split('.')[1] == 'mp3':
        sound = AudioSegment.from_mp3(fname)
        fname = fname.split('.')[0] + '.wav'
        sound.export(fname, format="wav")
        return fname.split('.')[0] + ".wav"
    elif (fname.split('.')[1] != "wav"):
        print("+ Converting Wav")
        return conv_wav(fname)
    return fname

def frame_rate_channel(fname):
    with wave.open(fname, "rb") as wave_file:
        frame_rate = wave_file.getframerate()
        channels = wave_file.getnchannels()
        return frame_rate,channels

def stereo_to_mono(fname):
    sound = AudioSegment.from_wav(fname)
    sound = sound.set_channels(1)
    sound.export(fname, format="wav")

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client.from_service_account_json('secret.json')
    buckets = list(storage_client.list_buckets())
    print(buckets)
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    print("+ Uploading File")
    blob.upload_from_filename(source_file_name)
    print("+ File Uploaded")

def delete_blob(bucket_name, blob_name):
    """Deletes a blob from the bucket."""
    storage_client = storage.Client.from_service_account_json('secret.json')
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(blob_name)

    blob.delete()

def speechregion(filename, frame_width=4096, min_region_size=0.5, max_region_size=6): # pylint: disable=too-many-locals

    reader = wave.open(filename)
    sample_width = reader.getsampwidth()
    rate = reader.getframerate()
    n_channels = reader.getnchannels()
    chunk_duration = float(frame_width) / rate

    n_chunks = int(math.ceil(reader.getnframes()*1.0 / frame_width))
    energies = []

    for _ in range(n_chunks):
        chunk = reader.readframes(frame_width)
        energies.append(audioop.rms(chunk, sample_width * n_channels))

    threshold = percentile(energies, 0.2)

    elapsed_time = 0

    regions = []
    region_start = None

    for energy in energies:
        is_silence = energy <= threshold
        max_exceeded = region_start and elapsed_time - region_start >= max_region_size

        if (max_exceeded or is_silence) and region_start:
            print("+ GOTCHA..")
            if elapsed_time - region_start >= min_region_size:
                print("HELLO")
                regions.append((region_start, elapsed_time))
                region_start = None

        elif (not region_start) and (not is_silence):
            region_start = elapsed_time
        elapsed_time += chunk_duration
    print(regions)
    return regions

def each_chunk(fname, frm_rate, chnl, lang):
    file_name = audio_output + fname
    frame_rate = frm_rate
    channels = chnl
    
    if channels > 1:
        stereo_to_mono(file_name)
    
    bucket_name = 'audioscript'
    source_file_name = audio_output + fname
    destination_blob_name = fname
    
    upload_blob(bucket_name, source_file_name, destination_blob_name)
    
    gcs_uri = 'gs://audioscript/' + fname
    transcript = ''
    print("+ Recognizing Speech")
    client = speech.SpeechClient.from_service_account_json("secret.json")
    audio = { "uri" : gcs_uri }

    config = {
        "encoding":enums.RecognitionConfig.AudioEncoding.LINEAR16,
        "sample_rate_hertz":frame_rate,
        "language_code":lang,
        "enable_speaker_diarization":True,
        "diarization_speaker_count":2,
    }

    # Detects speech in the audio file
    operation = client.long_running_recognize(config, audio)
    response = operation.result(timeout=10000)

    try:
        result = response.results[-1]
        alternative = result.alternatives[0]

        print(u"Transcript: {}".format(alternative.transcript))
        transcript = ""
        main = glob_id
        for word in alternative.words:
            transcript += word.word +" "
        
        print(transcript)
    except Exception as e:
        print("\n! ERROR on ", fname, "\n")
    
    delete_blob(bucket_name, destination_blob_name)
    return transcript

def conv_wav(filename):
    temp = filename.split(".")[0] + ".wav"
    if not os.path.isfile(filename):
        print("The given file does not exist: {}".format(filename))
        raise Exception("Invalid filepath: {}".format(filename))
    command = ["ffmpeg", "-y", "-i", filename,
               "-loglevel", "error", temp]
    subprocess.check_output(command, stdin=open(os.devnull), shell=True)
    return temp

def live_sub(transcript, transcript_filename):
    ''' Coming Soon '''
    pass

def audioscript(fname, lang):
    
    file_name = fname
    file_name = mp3_to_wav(file_name)
    print("+ Segmenting Audio")
    sound = AudioSegment.from_wav(file_name)
    print("+ Len :",len(sound))
    print("+ Minimizing In Chunks")
    transcript = []
    
    speechReg = speechregion(file_name)
    frame_rate, channels = frame_rate_channel(file_name)
    c = 0
    for i in speechReg:
        print(i[0], i[1])
        spch = sound[(i[0]*1000):(i[1]*1000)]
        spch.export(audio_output+"chunk{0}.wav".format(c), format="wav")
        transcript.append(each_chunk("chunk{0}.wav".format(c), frame_rate, channels, lang))
        os.remove(audio_output+"chunk{0}.wav".format(c))
        # print(i)
        c+=1
    print(transcript)
    return transcript, speechReg

def write_transcripts(transcript_filename,transcript, reg):
    print(transcript)
    import six
    sub_rip = pysrt.SubRipFile()
    for i, (start, end), text in zip(range(len(transcript)), reg, transcript):
        print(i, start, end, text)
        item = pysrt.SubRipItem()
        item.index = i
        item.text = six.text_type(text)
        item.start.seconds = max(0, start)
        item.end.seconds = end
        sub_rip.append(item)
    fin_sub = '\n'.join(six.text_type(item) for item in sub_rip)
    with open(output_filepath + transcript_filename, "wb") as f:
        f.write(fin_sub.encode("utf-8"))
    print("+ Successfully Generated Subtitles.")
    return True


if __name__ == "__main__":

    try:
        fname = sys.argv[1]
        try:
            codec = sys.argv[2]
        except:
            print("+ No Codec Given. Defaults to 'en-US'")
            codec = "en-US"
            # raise("")
        print(fname)
        exists = os.path.isdir(output_filepath)
        if not exists:
            os.mkdir(output_filepath)
        transcript, reg = audioscript(fname, codec)
        transcript_filename = fname.split('.')[0] + '.srt'
        write_transcripts(transcript_filename,transcript, reg)
    except Exception as e:
        print("! Pass A Valid Configuration.\nError : [", e, "]")