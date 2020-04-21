# AudioScript
Auto Generate Subtitle File For Any Type Of Audio and Video. Using Python and Google Speech-to-Text API. This application mainly focuses on the lack of subtitles for media files, this will generate the .srt file for any language.
> Supported Codecs
- .mp3
- .mp4
- .wav
- .avi
- .mov
- .mts
- .m4a
- `All of the media codecs`

> # Installation
Use `git clone https://github.com/dmcrobin/AudioScript.git` and change directory to AudioScript.

- Install Requirements<br>
`pip install requirements.txt`
- Run The Command<br>
`./audioscript.py [audio/video]_file.[ext] [language]` <br>
For example, `./audioscript.py hello.mp4 en-US`<br>
List of languages, goto [Google's language support](https://cloud.google.com/speech-to-text/docs/languages)
- Get Your Transcript
Go to `transcripts` folder, .srt will be generated, depending on the length of your media file.

### This application uses a JSON file that gives access to upload small chunks of audio to your bucket for faster processing, to download your own secret.json file please check in later

Peace!
