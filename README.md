# Two-way AI voice
These python scripts run a two-way voice conversation with Anthropic Claude, using ElevenLabs for TTS, Faster-Whisper for speech to text, and Pygame for audio playback. 

You can see it in action here: https://youtu.be/fVab674FGLI

![diagram](https://github.com/ccappetta/bidirectional_streaming_ai_voice/assets/36048795/a43d6e1d-4f6a-42c6-9e93-11f19466e989)

The rough loop can be seen in the diagram. The human audio is captured via microphone and then transcribed using Faster-Whisper. The transcription is added to the array of conversation messages and sent to Anthropic Claude 3 as a prompt. The Claude 3 reply tokens are streamed back (which afaik only works synchronously). 
In parallel with the LLM tokens streaming into the terminal, chunks of text are asynchronously sent to elevenlabs api for text-to-speech audio generation, and then the returned audio files are queued and played back with pygame.

Spacebar triggers the transition between human and AI turns.

It doesn't feel exceptionally elegant, but it does seem to work. It's definitely quicker than the designs I was finding that wait for the full LLM reply to be generated before invoking audio generation (and then edit out the latency... I see you youtube :). 

I built this on my windows machine, I'm not quite sure why. You'll probably need to make some tweaks if runing on mac or linux. Also there are a ton of libraries to install, just tank through the errors and resolve them one at a time, I believe in you. Claude can probably help. Or GPT4.

main.py is the backbone of the thing, it calls summaries.py for the summary info that is included in the current instructions. async_tasks.py handles the audio generation and playback. The script also expects a folder called input (which temporarily holds the user audio file), another folder called output (which stores all of the elevenlabs audio files... if we are paying for them may as well hold onto them), and a folder called transcripts (for the conversation transcripts).

You'll need a .env file with:

ANTHROPIC_API_KEY=sk-...

ELEVENLABS_API_KEY=4...





## Some thoughts on performance:

The crux latency consideration is between the time the user hits spacebar and the time the LLM audio playback begins; there are quite a few things happening in that sequence. I was poking around with some rough logging and thought the ballpark times of each mechanism breakpoint might be useful to someone.
- Spacebar press
- User audio file is generated and faster-whisper transcribes it to text (~4.5 seconds)
- Transcribed user text is sent to anthropic and the first LLm response token is streamed back (~3.5 seconds)
- Enough LLM tokens are streamed back to generate a ~150 character chunk and send that text off to Elevenlabs (~1.25 seconds)
- Elevenlabs generates and returns the audio file (~1.25 seconds)
- Pygame playback begins (0.1 second)

So we can see that the transcription of the user's audio is likely the best area for performanc gains. Perhaps with some element of audio chunking and parallel transcription so that the bulk of the audio is transcribed by the time the 'turn end' spacebar is pressed. Or perhaps there is another better transcription approach than faster-whisper. I think we can tolerate some level of inaccuracy because the LLMs these days seem pretty able to handle typos and mistypes... which also extends to them handling mediocre transcriptions
There likely isn't much gain to be found in the outside anthropic and elevenlabs APIs. Elevenlabs does have a websocket streaming design that I was initially trying but moved away from. I needed the anthropic token streaming to be synchronous so thats why audio generation and playback had to become async... so I'm not recalling if thats why I made that decision or not. If someone explores that I would be interested in hearing. At the time I was working with MVP and VLC libraries with mixed success, so perhaps the websocket approach would work better with the pygame audio playback I eventually settled on.
There may also be some gains in the chunking logic, if a smaller first chunk is sent out to elevenlabs that would shave off some of that ~1.25 seconds. Though it does seem like that 150 characters and punctuation breakpoint logic does seem to align to the first sentence generally, and having elevenlabs generate by the sentence seems intuitively to me like a way to get better audio than sending partial sentences to generate independently. I'd be interested in what others find if they explore this.



## Mac users check out this good comment from  @martoast:
Mac users change this line so that you use the CPU for speech to text.
```
compute_type = "float32"

segments, _ = WhisperModel(
model_size, device="cpu", compute_type=compute_type).transcribe(temp_file_path)
```




## Possible future angles-
- A better memory hierarchy to improve Claude/Quill's continuity. Currently I'm just giving the whole transcript to (another) Claude via their GUI and asking it to summarize, then I'm manually updating the summary.py file and the instructions variable.
- Wire in RVC in place of elevenlabs. It's an intriguing open source voice library.
- Maybe at some point I'd think about wiring in other LLMs but frankly Claude has my heart currently. And I say that as someone that has been smugly pooping on all self-proclaimed GPT4-killers for about a year (cough gemini). Claude is remarkable.
- The elevenlabs custom voice models are pretty stunning. A colleague and I have been thinking about trying a format where each of us interview Claudes with each other's cloned voice. That would furrow some brows I bet. Perhaps the 'latent noise' podcast will become a thing.

Hopefully you lot can make it better, or at least have some fun with it. Enjoy!

Thanks for reading.

