# Two-way AI voice
These python scripts handle a two way voice conversation with Anthropic Claude, using ElevenLabs, Faster-Whisper, and Pygame. 

![diagram](https://github.com/ccappetta/bidirectional_streaming_ai_voice/assets/36048795/a43d6e1d-4f6a-42c6-9e93-11f19466e989)

The rough loop can be seen in the diagram. The human audio is captured via microphone and then transcribed using Faster-Whisper. The transcription is added to the array of conversation messages and sent to Anthropic Claude 3 as a prompt. The Claude 3 reply tokens are streamed back (which afaik only works synchronously). 
In parallel with the LLM tokens streaming into the terminal, chunks of text are asynchronously sent to elevenlabs api for text-to-speech audio generation, and then the returned audio files are queued and played back with pygame.

Spacebar triggers the transition between human and AI turns.

It doesn't feel exceptionally elegant, but it does seem to work. It's definitely quicker than the designs I was finding that wait for the full LLM reply to be generated before invoking audio generation (and then edit out the latency... I see you youtube :). 

I built this on my windows machine, I'm not quite sure why. You'll probably need to make some tweaks if runing on mac or linux. Also there are a ton of libraries to install, just tank through the errors and resolve them one at a time, I believe in you.

You'll need a .env file with:
ANTHROPIC_API_KEY=sk-...
ELEVENLABS_API_KEY=4...
OPENAI_API_KEY=sk...

Hopefully you lot can make it better, or at least have some fun with it. Enjoy!
