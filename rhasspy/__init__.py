"""Rhasspy command-line interface"""
import argparse
import asyncio
import io
import json
import logging
# Configure logging
import logging.config
import os
import sys
import threading
import time
import wave
from typing import Any

from rhasspy.audio_recorder import AudioData
from rhasspy.core import RhasspyCore
from rhasspy.profiles import Profile
from rhasspy.utils import buffer_to_wav
from rhasspy.wake import WakeWordDetected

logger = logging.getLogger("rhasspy")

# -----------------------------------------------------------------------------
# Globals
# -----------------------------------------------------------------------------
mic_stdin_thread = None
mic_stdin_running = False

# -----------------------------------------------------------------------------


async def main() -> None:
    """Main method"""
    global mic_stdin_running, mic_stdin_thread

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Rhasspy")
    parser.add_argument(
        "--profile", "-p", required=True, type=str, help="Name of profile to use"
    )
    parser.add_argument(
        "--system-profiles",
        type=str,
        help="Directory with base profile files (read only)",
        default=os.path.join(os.getcwd(), "profiles"),
    )
    parser.add_argument(
        "--user-profiles",
        type=str,
        help="Directory with user profile files (read/write)",
        default=os.path.expanduser("~/.config/rhasspy/profiles"),
    )
    parser.add_argument(
        "--set",
        "-s",
        nargs=2,
        action="append",
        help="Set a profile setting value",
        default=[],
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG log to console"
    )
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Don't check profile for necessary files",
    )

    sub_parsers = parser.add_subparsers(dest="command")
    sub_parsers.required = True

    # info
    info_parser = sub_parsers.add_parser("info", help="Profile information")
    info_parser.add_argument(
        "--defaults", action="store_true", help="Only print default settings"
    )

    # wav2text
    wav2text_parser = sub_parsers.add_parser(
        "wav2text", help="WAV file to text transcription"
    )
    wav2text_parser.add_argument("wav_files", nargs="*", help="Paths to WAV files")

    # text2intent
    text2intent_parser = sub_parsers.add_parser(
        "text2intent", help="Text parsed to intent"
    )
    text2intent_parser.add_argument("sentences", nargs="*", help="Sentences to parse")
    text2intent_parser.add_argument(
        "--handle", action="store_true", help="Pass result to intent handler"
    )

    # wav2intent
    wav2intent_parser = sub_parsers.add_parser(
        "wav2intent", help="WAV file to parsed intent"
    )
    wav2intent_parser.add_argument("wav_files", nargs="*", help="Paths to WAV files")
    wav2intent_parser.add_argument(
        "--handle", action="store_true", help="Pass result to intent handler"
    )

    # train
    train_parser = sub_parsers.add_parser("train", help="Re-train profile")
    train_parser.add_argument(
        "--no-cache", action="store_true", help="Clear training cache"
    )

    # mic2wav
    mic2wav_parser = sub_parsers.add_parser("mic2wav", help="Voice command to WAV data")
    mic2wav_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum number of seconds to record (default=profile)",
    )

    # mic2text
    mic2text_parser = sub_parsers.add_parser(
        "mic2text", help="Voice command to text transcription"
    )
    mic2text_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum number of seconds to record (default=profile)",
    )

    # mic2intent
    mic2intent_parser = sub_parsers.add_parser(
        "mic2intent", help="Voice command to parsed intent"
    )
    mic2intent_parser.add_argument(
        "--stdin", action="store_true", help="Read audio data from stdin"
    )
    mic2intent_parser.add_argument(
        "--handle", action="store_true", help="Pass result to intent handler"
    )
    mic2intent_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum number of seconds to record (default=profile)",
    )

    # word2phonemes
    word2phonemes_parser = sub_parsers.add_parser(
        "word2phonemes", help="Get pronunciation(s) for word(s)"
    )
    word2phonemes_parser.add_argument("words", nargs="*", help="Word(s) to pronounce")
    word2phonemes_parser.add_argument(
        "-n", type=int, default=1, help="Maximum number of pronunciations"
    )

    # word2wav
    word2wav_parser = sub_parsers.add_parser("word2wav", help="Pronounce word")
    word2wav_parser.add_argument("word", help="Word to pronounce")

    # wav2mqtt
    wav2mqtt_parser = sub_parsers.add_parser(
        "wav2mqtt", help="Push WAV file(s) to MQTT"
    )
    wav2mqtt_parser.add_argument("wav_files", nargs="*", help="Paths to WAV files")
    wav2mqtt_parser.add_argument(
        "--frames",
        type=int,
        default=480,
        help="WAV frames per MQTT message (default=0 for all)",
    )
    wav2mqtt_parser.add_argument(
        "--site-id", type=str, default="default", help="Hermes siteId (default=default)"
    )
    wav2mqtt_parser.add_argument(
        "--silence-before",
        type=float,
        default=0,
        help="Seconds of silence to add before each WAV",
    )
    wav2mqtt_parser.add_argument(
        "--silence-after",
        type=float,
        default=0,
        help="Seconds of silence to add after each WAV",
    )
    wav2mqtt_parser.add_argument(
        "--pause",
        type=float,
        default=0.01,
        help="Seconds to wait before sending next chunk (default=0.01)",
    )

    # text2wav
    text2wav_parser = sub_parsers.add_parser(
        "text2wav", help="Output WAV file using text to speech system"
    )
    text2wav_parser.add_argument("sentence", help="Sentence to speak")

    # text2speech
    text2speech_parser = sub_parsers.add_parser(
        "text2speech", help="Speak sentences using text to speech system"
    )
    text2speech_parser.add_argument("sentences", nargs="*", help="Sentences to speak")

    # sleep
    sub_parsers.add_parser("sleep", help="Wait for wake word")

    # download
    download_parser = sub_parsers.add_parser("download", help="Download profile files")
    download_parser.add_argument(
        "--delete", action="store_true", help="Clear download cache before downloading"
    )

    # check
    sub_parsers.add_parser("check", help="Check downloaded profile files")

    # -------------------------------------------------------------------------

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    profiles_dirs = [args.system_profiles, args.user_profiles]
    logger.debug(profiles_dirs)

    # Create rhasspy core
    core = RhasspyCore(args.profile, args.system_profiles, args.user_profiles)

    # Add profile settings from the command line
    extra_settings = {}
    for key, value in args.set:
        try:
            value = json.loads(value)
        except Exception:
            pass

        logger.debug("Profile: %s=%s", key, value)
        extra_settings[key] = value
        core.profile.set(key, value)

    # Handle command
    if args.command == "info":
        if args.defaults:
            # Print default settings
            json.dump(core.defaults, sys.stdout, indent=4)
        else:
            # Print profile settings
            json.dump(core.profile.json, sys.stdout, indent=4)
    elif args.command == "sentences":
        sentences_path = core.profile.read_path(
            core.profile.get("speech_to_text.sentences_ini", "sentences.ini")
        )

        with open(sentences_path, "r") as sentences_file:
            sys.stdout.write(sentences_file.read())
    else:
        # Patch profile
        profile = core.profile
        profile.set("rhasspy.listen_on_start", False)
        profile.set("rhasspy.preload_profile", False)

        if args.command == "wav2mqtt":
            profile.set("mqtt.enabled", True)
        elif args.command in ["mic2intent"] and args.stdin:
            profile.set("microphone.system", "stdin")
            profile.set("microphone.stdin.auto_start", False)
            mic_stdin_running = True
        elif args.command == "text2wav":
            profile.set("sounds.system", "dummy")

        # Set environment variables
        os.environ["RHASSPY_BASE_DIR"] = os.getcwd()
        os.environ["RHASSPY_PROFILE"] = core.profile.name
        os.environ["RHASSPY_PROFILE_DIR"] = core.profile.write_dir()

        # Execute command
        command_funcs = {
            "wav2text": wav2text,
            "text2intent": text2intent,
            "wav2intent": wav2intent,
            "train": train_profile,
            "mic2text": mic2text,
            "mic2intent": mic2intent,
            "mic2wav": mic2wav,
            "word2phonemes": word2phonemes,
            "word2wav": word2wav,
            "wav2mqtt": wav2mqtt,
            "text2wav": text2wav,
            "text2speech": text2speech,
            "sleep": sleep,
            "download": download,
            "check": check,
        }

        # Automatically start core
        await core.start()

        if not args.no_check and (args.command not in ["check", "download"]):
            # Verify that profile has necessary files
            missing_files = core.check_profile()
            if len(missing_files) > 0:
                logger.fatal(
                    "Missing required files for %s: %s. Please run download command and try again.",
                    profile.name,
                    missing_files.keys(),
                )
                sys.exit(1)

        if mic_stdin_running:
            logger.debug("Reading audio data from stdin")
            mic_stdin_thread = threading.Thread(
                target=read_audio_stdin, args=(core,), daemon=True
            )
            mic_stdin_thread.start()

        # Run command
        try:
            await command_funcs[args.command](core, profile, args)

            if mic_stdin_thread is not None:
                mic_stdin_running = False
                mic_stdin_thread.join()
        finally:
            await core.shutdown()


# -----------------------------------------------------------------------------
# wav2text: transcribe WAV file(s) to text
# -----------------------------------------------------------------------------


async def wav2text(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Transcribe WAV file(s)"""
    if len(args.wav_files) > 0:
        # Read WAV paths from argument list
        transcriptions = {}
        for wav_path in args.wav_files:
            with open(wav_path, "rb") as wav_file:
                text = (await core.transcribe_wav(wav_file.read())).text
                transcriptions[wav_path] = text

        # Output JSON
        json.dump(transcriptions, sys.stdout, indent=4)
    else:
        # Read WAV data from stdin
        text = (await core.transcribe_wav(sys.stdin.buffer.read())).text

        # Output text
        print(text)


# -----------------------------------------------------------------------------
# text2intent: parse text into intent(s)
# -----------------------------------------------------------------------------


async def text2intent(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Parse sentences from command line or stdin"""
    intents = {}
    sentences = args.sentences if len(args.sentences) > 0 else sys.stdin
    for sentence in sentences:
        sentence = sentence.strip()
        intent = (await core.recognize_intent(sentence)).intent

        if args.handle:
            intent = (await core.handle_intent(intent)).intent

        intents[sentence] = intent

    # Output JSON
    json.dump(intents, sys.stdout, indent=4)


# -----------------------------------------------------------------------------
# wav2intent: transcribe WAV file(s) to text and parse into intent(s)
# -----------------------------------------------------------------------------


async def wav2intent(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Recognize intent from WAV file(s)"""
    if len(args.wav_files) > 0:
        # Read WAV paths from argument list
        transcriptions = {}
        for wav_path in args.wav_files:
            with open(wav_path, "rb") as wav_file:
                text = (await core.transcribe_wav(wav_file.read())).text
                transcriptions[wav_path] = text

        # Parse intents
        intents = {}
        for wav_path, sentence in transcriptions.items():
            intent = (await core.recognize_intent(sentence)).intent

            if args.handle:
                intent = (await core.handle_intent(intent)).intent

            intents[wav_path] = intent

        # Output JSON
        json.dump(intents, sys.stdout, indent=4)
    else:
        # Read WAV data from stdin
        sentence = (await core.transcribe_wav(sys.stdin.buffer.read())).text
        intent = (await core.recognize_intent(sentence)).intent

        if args.handle:
            intent = (await core.handle_intent(intent)).intent

        # Output JSON
        json.dump(intent, sys.stdout, indent=4)


# -----------------------------------------------------------------------------
# train: re-train profile speech/intent recognizers
# -----------------------------------------------------------------------------


async def train_profile(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Train Rhasspy profile"""
    result = await core.train(reload_actors=False, no_cache=args.no_cache)
    print(result)


# -----------------------------------------------------------------------------
# mic2wav: record voice command and output WAV data
# -----------------------------------------------------------------------------


async def mic2wav(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Record voice command from microphone"""
    # Listen until silence
    wav_data = buffer_to_wav((await core.record_command(args.timeout)).data)

    # Output WAV data
    sys.stdout.buffer.write(wav_data)


# -----------------------------------------------------------------------------
# mic2text: record voice command, then transcribe
# -----------------------------------------------------------------------------


async def mic2text(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Record voice command and transcribe"""
    # Listen until silence
    wav_data = buffer_to_wav((await core.record_command(args.timeout)).data)

    # Transcribe
    text = (await core.transcribe_wav(wav_data)).text

    # Output text
    print(text)


# -----------------------------------------------------------------------------
# mic2intent: record voice command, then transcribe/parse
# -----------------------------------------------------------------------------


def read_audio_stdin(core: RhasspyCore, chunk_size: int = 960):
    """Record audio chunks from stdin"""
    global mic_stdin_running
    while mic_stdin_running:
        audio_data = sys.stdin.buffer.read(chunk_size)
        core.send_audio_data(AudioData(audio_data))


async def mic2intent(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Record voice command, transcribe, and recognize intent"""
    # Listen until silence
    wav_data = buffer_to_wav((await core.record_command(args.timeout)).data)

    # Transcribe
    sentence = (await core.transcribe_wav(wav_data)).text

    # Parse
    intent = (await core.recognize_intent(sentence)).intent

    if args.handle:
        intent = (await core.handle_intent(intent)).intent

    # Output JSON
    json.dump(intent, sys.stdout, indent=4)


# -----------------------------------------------------------------------------
# word2phonemes: get pronunciation(s) for a word
# -----------------------------------------------------------------------------


async def word2phonemes(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Get pronunciation(s) for word(s)"""
    words = args.words if len(args.words) > 0 else sys.stdin

    # Get pronunciations for all words
    pronunciations = (
        await core.get_word_pronunciations(words, n=args.n)
    ).pronunciations

    # Output JSON
    json.dump(pronunciations, sys.stdout, indent=4)


# -----------------------------------------------------------------------------
# word2wav: pronounce word as WAV data
# -----------------------------------------------------------------------------


async def word2wav(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Speak a word's pronunciation"""
    # Get pronunciation for word
    all_pronunciations = (
        await core.get_word_pronunciations([args.word], n=1)
    ).pronunciations
    word_pronunciations = all_pronunciations[args.word]["pronunciations"]

    # Convert from CMU phonemes to eSpeak phonemes
    espeak_str = (await core.get_word_phonemes(word_pronunciations[0])).phonemes

    # Pronounce as WAV
    wav_data = (await core.speak_word(espeak_str)).wav_data

    # Output WAV data
    sys.stdout.buffer.write(wav_data)


# -----------------------------------------------------------------------------
# wav2mqtt: output WAV data to MQTT via Hermes protocol
# -----------------------------------------------------------------------------


def _send_frame(
    core: RhasspyCore,
    topic: str,
    audio_data: bytes,
    rate: int,
    width: int,
    channels: int,
) -> None:
    """Send a single audio frame via MQTT"""
    with io.BytesIO() as mqtt_buffer:
        mqtt_file: wave.Wave_write = wave.open(mqtt_buffer, mode="wb")
        with mqtt_file:
            mqtt_file.setframerate(rate)
            mqtt_file.setsampwidth(width)
            mqtt_file.setnchannels(channels)
            mqtt_file.writeframes(audio_data)

        # Send audio frame WAV
        mqtt_payload = mqtt_buffer.getvalue()
        core.mqtt_publish(topic, mqtt_payload)


async def wav2mqtt(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Publish WAV to MQTT as audio frames"""
    # hermes/audioServer/<SITE_ID>/audioFrame
    topic = "hermes/audioServer/%s/audioFrame" % args.site_id

    if len(args.wav_files) > 0:
        # Read WAV paths from argument list
        for wav_path in args.wav_files:
            with wave.open(wav_path, "rb") as wav_file:
                rate = wav_file.getframerate()
                width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()

                if args.frames > 0:
                    # Split into chunks
                    chunk_size = args.frames * width * channels
                    if args.silence_before > 0:
                        # Silence
                        num_chunks = int(
                            (args.silence_before * rate * width * channels) / chunk_size
                        )
                        for _ in range(num_chunks):
                            _send_frame(
                                core, topic, bytes(chunk_size), rate, width, channels
                            )
                            time.sleep(args.pause)

                    # Read actual audio data
                    audio_data = wav_file.readframes(args.frames)

                    while len(audio_data) > 0:
                        _send_frame(core, topic, audio_data, rate, width, channels)
                        time.sleep(args.pause)

                        # Read next chunk
                        audio_data = wav_file.readframes(args.frames)

                    if args.silence_after > 0:
                        # Silence
                        num_chunks = int(
                            (args.silence_after * rate * width * channels) / chunk_size
                        )
                        for _ in range(num_chunks):
                            _send_frame(
                                core, topic, bytes(chunk_size), rate, width, channels
                            )
                            time.sleep(args.pause)
                else:
                    # Send all at once
                    audio_data = wav_file.readframes(wav_file.getnframes())
                    _send_frame(core, topic, audio_data, rate, width, channels)

            print(wav_path)


# -----------------------------------------------------------------------------
# text2wav: speak sentence and output WAV
# -----------------------------------------------------------------------------


async def text2wav(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Speak a sentence and output WAV data"""
    result = await core.speak_sentence(args)
    sys.stdout.buffer.write(result.wav_data)


# -----------------------------------------------------------------------------
# text2speech: speak sentences
# -----------------------------------------------------------------------------


async def text2speech(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Speak sentences"""
    sentences = args.sentences
    if len(sentences) == 0:
        sentences = sys.stdin

    for sentence in sentences:
        sentence = sentence.strip()
        await core.speak_sentence(sentence)


# -----------------------------------------------------------------------------
# sleep: wait for wake word
# -----------------------------------------------------------------------------


async def sleep(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Wait for wake word to be spoken"""
    result = await core.wakeup_and_wait()
    if isinstance(result, WakeWordDetected):
        print(result.name)
    else:
        print("")  # not detected


# -----------------------------------------------------------------------------
# download: download profile files
# -----------------------------------------------------------------------------


async def download(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Download necessary profile files"""
    await core.download_profile(delete=args.delete)
    print("OK")


# -----------------------------------------------------------------------------
# check: check profile files
# -----------------------------------------------------------------------------


async def check(core: RhasspyCore, profile: Profile, args: Any) -> None:
    """Verify that profile files are downloaded"""
    missing_files = core.check_profile()
    json.dump(missing_files, sys.stdout, indent=4)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
