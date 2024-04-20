# fmt: off
import os
import sys
import asyncio
import keyboard
import time
import tempfile
import anthropic
import datetime
import assemblyai as aai
import sounddevice as sd
import numpy as np
from async_tasks import start_async_tasks, text_to_speech_queue
from threading import Thread
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
from dotenv import load_dotenv
from colorama import init, Fore, Style
# Redirect stdout to devnull while importing Pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
# fmt: on


# Credentials and API keys
load_dotenv()
aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
anthropic_key = os.getenv('ANTHROPIC_KEY')

# Initialize colorama and Anthropic client
init(autoreset=True)
client = anthropic.Anthropic(api_key=anthropic_key)

# Initialize Pygame for audio playback
pygame.mixer.init()
pygame.init()


# Global variables
conversation_history = []
shutdown_event = asyncio.Event()
model_size = "small"
compute_type = "float16"
recording_finished = False
is_recording = False


class States:
    WAITING_FOR_USER = 1
    RECORDING_USER_INPUT = 2
    PROCESSING_USER_INPUT = 3
    GENERATING_RESPONSE = 4
    PLAYING_RESPONSE = 5


current_state = States.WAITING_FOR_USER

system_message = '''Claude, your responses in this conversation will be converted to speech in real-time for a voice-based interaction. Please optimize your replies for this format:
Be concise and focus on the most salient points. Aim for brevity over lengthy explanations.
Jump straight into your key ideas without summarizing or affirming the human's stance each time.
Make your points directly. Turn the conversation back to the human quickly. You don't need to re-state or summarize what you've already said. Think of this as me interviewing you, you do not need to wrap up your comments with open ended questions.

Feel free to be unexpected, witty, irreverent, and humorous when appropriate. Don't be afraid to make keen observations, ask thought-provoking questions, or leave some ideas incomplete for us to ponder. The goal is an engaging, unpredictable, interesting dialogue.
If a great insight, joke, or question comes to mind that doesn't fit the current topic, go ahead and say it anyway. We can always circle back to the main thread later. Serendipity and tangents are welcome.
The overall goal is to have a lively, natural conversation with plenty of back-and-forth. Prioritize concision, but also allow room for humor, improvisation, and provocative ideas. Efficiency is good, but so is keeping things fun and stimulating. We would prefer to cover a topic with many brief back and forth comments rather than a few long monologues. Do not emote using asterisksin your replies. Communicate in a natural spoken style.'''

print("\nClaude's instructions: " + system_message + Fore.YELLOW +
      "\n\nPress spacebar to capture your audio and begin the conversation." + Style.RESET_ALL)


def record_audio():
    global is_recording
    fs = 44100  # Sample rate
    duration = 90  # Maximum possible duration, but we can stop earlier
    block_duration = 0.1  # Duration of each audio block in seconds

    # Callback function to be called for each audio block. Frames, time, and status are used by library mechanisms outside this script so need to stay.
    def callback(indata, frames, time, status):
        nonlocal audio_data
        if is_recording:
            audio_data.append(indata.copy())

    # Set the flag to True to start recording
    is_recording = True

    audio_data = []
    # Start recording in a non-blocking manner
    with sd.InputStream(callback=callback, samplerate=fs, channels=1, blocksize=int(fs * block_duration)):
        while is_recording and len(audio_data) * block_duration < duration:
            sd.sleep(int(block_duration * 1000))

    # Convert the audio data to a NumPy array
    audio_data = np.concatenate(audio_data, axis=0)

    return audio_data, fs


def on_space_press(event):
    global is_recording, current_state
    if event.name == 'space':
        if current_state == States.WAITING_FOR_USER:
            is_recording = True
            current_state = States.RECORDING_USER_INPUT
            print(Fore.YELLOW + "Recording started. Press the space bar to stop.")
        elif current_state == States.RECORDING_USER_INPUT and is_recording:
            is_recording = False  # This will trigger the recording to stop
            print("Recording stopped. Processing input...")
            current_state = States.PROCESSING_USER_INPUT


def transcribe_audio_to_text(audio_data, sample_rate):
    start_time = time.time()  # Record the start time
    temp_dir = './input/'
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = tempfile.mktemp(suffix='.wav', dir=temp_dir)
    try:
        write(temp_file_path, sample_rate, audio_data)
        segments, _ = WhisperModel(
            model_size, device="cuda", compute_type=compute_type).transcribe(temp_file_path)
        transcript = " ".join(segment.text for segment in segments)
        print(Fore.GREEN + "User:", transcript)
        end_time = time.time()  # Record the end time
        duration = end_time - start_time  # Calculate the duration
        print(f"[Transcription: {duration:.2f} seconds]")
        return transcript
    except Exception as e:
        print(Fore.RED + "Error during transcription:", e)
    finally:
        os.remove(temp_file_path)


def generate_and_process_text(user_input, transcript_file):
    # Trim whitespace and check if input is empty
    user_input = user_input.strip()
    if user_input:  # Proceed only if user_input is not empty
        conversation_history.append({"role": "user", "content": user_input})
        with open(transcript_file, "a") as file:
            file.write(f"~~~\n\nUser: {user_input}\n\n~~~\n")
    else:
        print(Fore.RED + "Received empty input, skipping...")
        return  # Skip processing for empty input

    claude_response = ""
    buffer = ""
    min_chunk_size = 150
    splitters = (".", "?", "!")

    # Before streaming, validate conversation_history
    validated_history = [
        msg for msg in conversation_history if msg.get("content").strip()]

    try:
        with client.messages.stream(
            max_tokens=1024,
            messages=validated_history,
            system=system_message,
            model="claude-3-opus-20240229",
        ) as stream:
            for text in stream.text_stream:
                print(Fore.CYAN + text + Style.RESET_ALL, end="", flush=True)
                claude_response += text
                buffer += text

                # Check if buffer is ready to be chunked
                last_splitter_pos = max(buffer.rfind(splitter)
                                        for splitter in splitters)
                if len(buffer) >= min_chunk_size and last_splitter_pos != -1:
                    chunk = buffer[:last_splitter_pos+1]
                    buffer = buffer[last_splitter_pos+1:]

                    # Queue this chunk for async TTS processing
                    queue_chunk_for_processing(chunk)
    except anthropic.APIError as e:
        print(Fore.RED + f"Anthropic API Error: {e}")
        return

    # Process any remaining text in buffer
    if buffer:
        queue_chunk_for_processing(buffer)

    # Append Claude's full response to the conversation history
    conversation_history.append(
        {"role": "assistant", "content": claude_response})

    # Write Claude's completed response to the transcript file
    with open(transcript_file, "a") as file:
        file.write(f"\nClaude: {claude_response}\n\n")

    print()  # Newline for separation


def queue_chunk_for_processing(chunk):
    # Queue the chunk for asynchronous processing
    text_to_speech_queue.put_nowait(chunk)


def run_async_tasks():
    # Set up the event loop and run the async tasks

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(start_async_tasks(text_to_speech_queue))

    try:
        loop.run_until_complete(shutdown_event.wait())
    finally:
        loop.close()


def parse_transcript(transcript_content):
    conversation_history = []
    lines = transcript_content.strip().split("\n")
    for line in lines:
        if line.startswith("User: "):
            user_input = line[6:]
            conversation_history.append(
                {"role": "user", "content": user_input})
        elif line.startswith("Claude: "):
            claude_response = line[8:]
            conversation_history.append(
                {"role": "assistant", "content": claude_response})

    # Check if the last message is from the user
    if conversation_history and conversation_history[-1]["role"] == "user":
        # Append a filler message from Claude
        conversation_history.append({"role": "assistant", "content": "..."})

    return conversation_history


def determine_current_state(conversation_history):
    if conversation_history[-1]["role"] == "assistant":
        return States.WAITING_FOR_USER
    else:
        return States.GENERATING_RESPONSE


def setup_new_transcript_file():
    transcripts_directory = "transcripts"
    os.makedirs(transcripts_directory, exist_ok=True)

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    transcript_file = f"{transcripts_directory}/transcript_{timestamp}.txt"
    with open(transcript_file, "w") as file:
        file.write(f"Transcription started at {timestamp}\n\n")

    return transcript_file


def setup_transcript_file(transcript_filename):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    new_transcript_file = f"transcripts/transcript_{timestamp}.txt"

    # Copy the content of the original transcript into the new file
    with open(transcript_filename, "r") as original_file, open(new_transcript_file, "w") as new_file:
        original_content = original_file.read()
        new_file.write(original_content)
        new_file.write(f"\nTranscription resumed at {timestamp}\n\n")

    return new_transcript_file


def main():
    global current_state, is_recording, conversation_history

    if len(sys.argv) == 2:
        transcript_filename = sys.argv[1]
        try:
            with open(transcript_filename, "r") as file:
                transcript_content = file.read()
            conversation_history = parse_transcript(transcript_content)
            current_state = determine_current_state(conversation_history)
            transcript_file = setup_transcript_file(transcript_filename)
            print(Fore.GREEN +
                  f"Resuming conversation from {transcript_filename}")
        except FileNotFoundError:
            print(
                Fore.RED + f"Transcript file '{transcript_filename}' not found. Starting a new conversation.")
            transcript_file = setup_new_transcript_file()
    else:
        transcript_file = setup_new_transcript_file()

    thread = Thread(target=run_async_tasks)
    thread.start()

    previous_state = None

    try:
        keyboard.on_press(on_space_press)
        while True:
            if current_state != previous_state:
                previous_state = current_state  # Update previous_state

            if current_state == States.RECORDING_USER_INPUT:
                # Start recording
                recording, fs = record_audio()
                current_state = States.PROCESSING_USER_INPUT

            elif current_state == States.PROCESSING_USER_INPUT:
                # Transcribe and process input
                user_input = transcribe_audio_to_text(recording, fs)
                generate_and_process_text(user_input, transcript_file)
                current_state = States.GENERATING_RESPONSE

            elif current_state == States.GENERATING_RESPONSE:
                if not pygame.mixer.music.get_busy():  # Check if pygame playback is completed
                    current_state = States.WAITING_FOR_USER

            # Add a short sleep to prevent the loop from hogging CPU
            time.sleep(0.1)

    except KeyboardInterrupt:
        print(Fore.RED + "\nShutting down gracefully...")
        shutdown_event.set()
        thread.join()


if __name__ == "__main__":
    main()
