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

OPENAI_API_KEY=sk...

Hopefully you lot can make it better, or at least have some fun with it. Enjoy!

Possible future angles-
- A better memory hierarchy to improve Claude/Quill's continuity. Currently I'm just giving the whole transcript to (another) Claude via their GUI and asking it to summarize, then I'm manually updating the summary.py file and the instructions variable.
- Wire in RVC in place of elevenlabs. It's an intriguing open source voice library.
- Maybe at some point I'd think about wiring in other LLMs but frankly Claude has my heart currently. And I say that as someone that has been smugly pooping on all self-proclaimed GPT4-killers for about a year (cough gemini). Claude is remarkable.
- The elevenlabs custom voice models are pretty stunning. A colleague and I have been thinking about trying a format where each of us interview Claudes with each other's cloned voice. That would furrow some brows I bet. Perhaps the 'latent noise' podcast will become a thing.

