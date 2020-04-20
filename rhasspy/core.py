"""Core Rhasspy commands."""
import asyncio
import gzip
import logging
import os
import platform
import shutil
import ssl
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp

# Internal imports
from rhasspy.actor import ActorSystem, ConfigureEvent, RhasspyActor
from rhasspy.dialogue import DialogueManager
from rhasspy.events import (
    AudioData,
    GetActorStates,
    GetMicrophones,
    GetProblems,
    GetSpeakers,
    GetVoiceCommand,
    GetWordPhonemes,
    GetWordPronunciations,
    HandleIntent,
    IntentHandled,
    IntentRecognized,
    ListenForCommand,
    ListenForWakeWord,
    MqttPublish,
    PlayWavData,
    PlayWavFile,
    Problems,
    ProfileTrainingComplete,
    ProfileTrainingFailed,
    RecognizeIntent,
    SentenceSpoken,
    SpeakSentence,
    SpeakWord,
    StopListeningForWakeWord,
    StartRecordingToBuffer,
    StopRecordingToBuffer,
    TestMicrophones,
    TrainProfile,
    TranscribeWav,
    VoiceCommand,
    WakeWordDetected,
    WakeWordNotDetected,
    WavTranscription,
    WordPhonemes,
    WordPronunciations,
    WordSpoken,
)
from rhasspy.profiles import Profile
from rhasspy.utils import numbers_to_words

# -----------------------------------------------------------------------------


class RhasspyCore:
    """Core class for Rhasspy functionality."""

    def __init__(
        self,
        profile_name: str,
        system_profiles_dir: str,
        user_profiles_dir: str,
        actor_system: Optional[ActorSystem] = None,
    ) -> None:

        self._logger = logging.getLogger(self.__class__.__name__)
        self.profiles_dirs: List[str] = [user_profiles_dir, system_profiles_dir]
        self.profile_name = profile_name
        self.actor_system = actor_system

        self.profile = Profile(
            self.profile_name, system_profiles_dir, user_profiles_dir
        )
        self._logger.debug("Loaded profile from %s", self.profile.json_path)
        self._logger.debug(
            "Profile files will be written to %s", self.profile.write_path()
        )

        self.defaults = Profile.load_defaults(system_profiles_dir)

        self.loop = asyncio.get_event_loop()

        self.ssl_context = ssl.SSLContext()
        self._session: Optional[aiohttp.ClientSession] = aiohttp.ClientSession()
        self.dialogue_manager: Optional[RhasspyActor] = None

        self.download_status: List[str] = []

    # -------------------------------------------------------------------------

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get HTTP client session."""
        assert self._session is not None
        return self._session

    @property
    def siteId(self) -> str:
        """Get default MQTT siteId"""
        try:
            return self.profile.get("mqtt.siteId", "default").split(",")[0]
        except Exception:
            return "default"

    # -------------------------------------------------------------------------

    async def start(
        self,
        preload: Optional[bool] = None,
        block: bool = True,
        timeout: float = 60,
        observer: Optional[RhasspyActor] = None,
    ) -> None:
        """Start Rhasspy core."""

        if self.actor_system is None:
            self.actor_system = ActorSystem()

        if preload is None:
            preload = self.profile.get("rhasspy.preload_profile", False)

        assert self.actor_system is not None
        self.dialogue_manager = self.actor_system.createActor(DialogueManager)
        with self.actor_system.private() as sys:
            await sys.async_ask(
                self.dialogue_manager,
                ConfigureEvent(
                    self.profile,
                    preload=preload,
                    ready=block,
                    transitions=False,
                    load_timeout_sec=30,
                    observer=observer,
                ),
            )

            # Block until ready
            if block:
                await sys.async_listen(timeout)

    # -------------------------------------------------------------------------

    async def get_microphones(self, system: Optional[str] = None) -> Dict[Any, Any]:
        """Get available audio recording devices."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(self.dialogue_manager, GetMicrophones(system))
            assert isinstance(result, dict), result
            return result

    async def test_microphones(self, system: Optional[str] = None) -> Dict[Any, Any]:
        """Listen to all microphones and determine if they're live."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(self.dialogue_manager, TestMicrophones(system))
            assert isinstance(result, dict), result
            return result

    async def get_speakers(self, system: Optional[str] = None) -> Dict[Any, Any]:
        """Get available audio playback devices."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(self.dialogue_manager, GetSpeakers(system))
            assert isinstance(result, dict), result
            return result

    # -------------------------------------------------------------------------

    def listen_for_wake(self, enabled: bool = True) -> None:
        """Tell Rhasspy to start listening for a wake word."""
        assert self.actor_system is not None

        if enabled:
            self.actor_system.tell(self.dialogue_manager, ListenForWakeWord())
        else:
            self.actor_system.tell(self.dialogue_manager, StopListeningForWakeWord())

    async def listen_for_command(
        self,
        handle: bool = True,
        timeout: Optional[float] = None,
        entity: Optional[str] = None,
        value: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Block until a voice command has been spoken. Optionally handle it."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            entities = None
            if entity is not None:
                entities = [{"entity": entity, "value": value}]

            result = await sys.async_ask(
                self.dialogue_manager,
                ListenForCommand(handle=handle, timeout=timeout, entities=entities),
            )
            assert isinstance(result, dict), result

            return result

    async def record_command(self, timeout: Optional[float] = None) -> VoiceCommand:
        """Record a single voice command."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(
                self.dialogue_manager, GetVoiceCommand(timeout=timeout)
            )
            assert isinstance(result, VoiceCommand), result
            return result

    # -------------------------------------------------------------------------

    async def transcribe_wav(self, wav_data: bytes) -> WavTranscription:
        """Transcribe text from WAV buffer."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(
                self.dialogue_manager, TranscribeWav(wav_data, handle=False)
            )
            assert isinstance(result, WavTranscription), result
            return result

    async def recognize_intent(self, text: str, wakeId: str = "") -> IntentRecognized:
        """Recognize an intent from text."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            # Fix casing
            dict_casing = self.profile.get("speech_to_text.dictionary_casing", "")
            if dict_casing == "lower":
                text = text.lower()
            elif dict_casing == "upper":
                text = text.upper()

            # Replace numbers
            if self.profile.get("intent.replace_numbers", True):
                language = self.profile.get("language", "")
                if not language:
                    language = None

                # 75 -> seventy five
                text = numbers_to_words(text, language=language)

            result = await sys.async_ask(
                self.dialogue_manager, RecognizeIntent(text, handle=False)
            )
            assert isinstance(result, IntentRecognized), result

            # Add slots
            intent_slots = {}
            for ev in result.intent.get("entities", []):
                intent_slots[ev["entity"]] = ev["value"]

            result.intent["slots"] = intent_slots

            # Add wake/site ID
            result.intent["wakeId"] = wakeId
            result.intent["siteId"] = self.profile.get("mqtt.site_id", "default")

            return result

    async def handle_intent(self, intent: Dict[str, Any]) -> IntentHandled:
        """Handle an intent."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(self.dialogue_manager, HandleIntent(intent))
            assert isinstance(result, IntentHandled), result
            return result

    # -------------------------------------------------------------------------

    def start_recording_wav(self, buffer_name: str = "") -> None:
        """Record audio data to a named buffer."""
        assert self.actor_system is not None
        self.actor_system.tell(
            self.dialogue_manager, StartRecordingToBuffer(buffer_name)
        )

    async def stop_recording_wav(self, buffer_name: str = "") -> AudioData:
        """Stop recording audio data to a named buffer."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(
                self.dialogue_manager, StopRecordingToBuffer(buffer_name)
            )
            assert isinstance(result, AudioData), result
            return result

    # -------------------------------------------------------------------------

    def play_wav_data(self, wav_data: bytes) -> None:
        """Play WAV buffer through audio playback system."""
        assert self.actor_system is not None
        self.actor_system.tell(self.dialogue_manager, PlayWavData(wav_data))

    def play_wav_file(self, wav_path: str) -> None:
        """Play WAV file through audio playback system."""
        assert self.actor_system is not None
        self.actor_system.tell(self.dialogue_manager, PlayWavFile(wav_path))

    # -------------------------------------------------------------------------

    async def get_word_pronunciations(
        self, words: List[str], n: int = 5
    ) -> WordPronunciations:
        """Look up or guess pronunciations for a word."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(
                self.dialogue_manager, GetWordPronunciations(words, n)
            )
            assert isinstance(result, WordPronunciations), result
            return result

    async def get_word_phonemes(self, word: str) -> WordPhonemes:
        """Get eSpeak phonemes for a word."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(self.dialogue_manager, GetWordPhonemes(word))
            assert isinstance(result, WordPhonemes), result
            return result

    async def speak_word(self, word: str) -> WordSpoken:
        """Speak a single word."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(self.dialogue_manager, SpeakWord(word))
            assert isinstance(result, WordSpoken), result
            return result

    async def speak_sentence(
        self,
        sentence: str,
        play: bool = True,
        language: Optional[str] = None,
        voice: Optional[str] = None,
        siteId: Optional[str] = None,
    ) -> SentenceSpoken:
        """Speak an entire sentence using text to speech system."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(
                self.dialogue_manager,
                SpeakSentence(
                    sentence, play=play, language=language, voice=voice, siteId=siteId
                ),
            )
            assert isinstance(result, SentenceSpoken), result
            return result

    # -------------------------------------------------------------------------

    async def train(
        self, reload_actors: bool = True, no_cache: bool = False
    ) -> Union[ProfileTrainingComplete, ProfileTrainingFailed]:
        """Generate speech/intent artifacts for profile."""
        if no_cache:
            # Delete doit database
            profile_dir = Path(self.profile.write_path())
            for db_path in profile_dir.glob(".doit.db*"):
                if db_path.is_file():
                    db_path.unlink()

        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(
                self.dialogue_manager, TrainProfile(reload_actors=reload_actors)
            )
            assert isinstance(
                result, (ProfileTrainingComplete, ProfileTrainingFailed)
            ), result
            return result

    # -------------------------------------------------------------------------

    def mqtt_publish(self, topic: str, payload: bytes) -> None:
        """Publish a payload to an MQTT topic."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            sys.tell(self.dialogue_manager, MqttPublish(topic, payload))

    # -------------------------------------------------------------------------

    async def wakeup_and_wait(self) -> Union[WakeWordDetected, WakeWordNotDetected]:
        """Listen for a wake word to be detected or not."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(self.dialogue_manager, ListenForWakeWord())
            assert isinstance(result, (WakeWordDetected, WakeWordNotDetected)), result

            return result

    # -------------------------------------------------------------------------

    async def get_actor_states(self) -> Dict[str, str]:
        """Get the current state of each Rhasspy actor."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(self.dialogue_manager, GetActorStates())
            assert isinstance(result, dict), result
            return result

    # -------------------------------------------------------------------------

    def send_audio_data(self, data: AudioData) -> None:
        """Send raw audio data to Rhasspy."""
        assert self.actor_system is not None
        self.actor_system.tell(self.dialogue_manager, data)

    # -------------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Shut down actors."""
        # Clear environment variables
        rhasspy_vars = [v for v in os.environ if v.startswith("RHASSPY")]

        for v in rhasspy_vars:
            del os.environ[v]

        # Stop actor system
        if self.actor_system is not None:
            self.actor_system.shutdown()
            self.actor_system = None

        if self._session is not None:
            await self._session.close()
            self._session = None

    # -------------------------------------------------------------------------

    def check_profile(self) -> Dict[str, str]:
        """Return True if the profile has all necessary files downloaded."""
        output_dir = self.profile.write_path()
        missing_files: Dict[str, Any] = {}

        # Load configuration
        conditions = self.profile.get("download.conditions", {})

        # Check conditions
        for setting_name in conditions:
            real_value = self.profile.get(setting_name, None)

            # Compare setting values
            for setting_value, files_dict in conditions[setting_name].items():
                compare_func = self._get_compare_func(setting_value)

                if compare_func(real_value):
                    # Check if file needs to be downloaded
                    for dest_name in files_dict:
                        dest_path = os.path.join(output_dir, dest_name)
                        if not os.path.exists(dest_path) or (
                            os.path.getsize(dest_path) == 0
                        ):
                            missing_files[dest_path] = (setting_name, setting_value)

        return missing_files

    def _get_compare_func(self, value: str):
        """Use mini-language to allow for profile setting value comparison."""
        if value.startswith(">="):
            f_value = float(value[2:])
            return lambda v: v >= f_value

        if value.startswith("<="):
            f_value = float(value[2:])
            return lambda v: v <= f_value

        if value.startswith(">"):
            f_value = float(value[1:])
            return lambda v: v > f_value

        if value.startswith("<"):
            f_value = float(value[1:])
            return lambda v: v < f_value

        if value.startswith("!"):
            return lambda v: v != value

        return lambda v: str(v) == value

    def _unpack_gz(self, src_path, temp_dir):
        # Strip off .gz and put relative to temporary directory
        temp_file_path = os.path.join(temp_dir, os.path.split(src_path[:-3])[1])

        # Decompress single file
        with open(src_path, "rb") as src_file:
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(gzip.decompress(src_file.read()))

        return temp_file_path

    # -------------------------------------------------------------------------

    async def download_profile(self, delete=False, chunk_size=4096) -> None:
        """Download all necessary profile files from the internet and extract them."""
        self.download_status = []

        output_dir = Path(self.profile.write_path())
        download_dir = Path(
            self.profile.write_path(self.profile.get("download.cache_dir", "download"))
        )

        if delete and download_dir.exists():
            self._logger.debug("Deleting download cache at %s", download_dir)
            shutil.rmtree(download_dir)

        download_dir.mkdir(parents=True, exist_ok=True)

        # Load configuration
        conditions = self.profile.get("download.conditions", {})
        all_files = self.profile.get("download.files", {})
        files_to_copy = {}
        files_to_extract: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        files_to_download: Set[str] = set()

        async def download_file(url, filename):
            try:
                status = f"Downloading {url} to {filename}"
                self.download_status.append(status)
                self._logger.debug(status)
                os.makedirs(os.path.dirname(filename), exist_ok=True)

                async with self.session.get(url, ssl=self.ssl_context) as response:
                    with open(filename, "wb") as out_file:
                        async for chunk in response.content.iter_chunked(chunk_size):
                            out_file.write(chunk)

                status = f"Downloaded {filename}"
                self.download_status.append(status)
                self._logger.debug(status)
            except Exception:
                self._logger.exception(url)

                # Try to delete partially downloaded file
                try:
                    status = f"Failed to download {filename}"
                    self.download_status.append(status)
                    self._logger.debug(status)
                    os.unlink(filename)
                except Exception:
                    pass

        # Check conditions
        machine_type = platform.machine()
        download_tasks = []
        for setting_name in conditions:
            real_value = self.profile.get(setting_name, None)

            # Compare setting values
            for setting_value, files_dict in conditions[setting_name].items():
                compare_func = self._get_compare_func(setting_value)

                if compare_func(real_value):
                    # Check if file needs to be downloaded
                    for dest_name, src_name in files_dict.items():
                        dest_path = os.path.join(output_dir, dest_name)
                        if ":" in src_name:
                            # File is an archive
                            src_name, src_extract = src_name.split(":", maxsplit=1)
                            src_path = os.path.join(download_dir, src_name)
                            files_to_extract[src_path].append((dest_path, src_extract))
                        else:
                            # Just a regular file
                            src_path = os.path.join(download_dir, src_name)
                            files_to_copy[src_path] = dest_path

                        # Get download/cache info for file
                        src_info = all_files.get(src_name, None)
                        if src_info is None:
                            self._logger.error(
                                "No entry for download file %s", src_name
                            )
                            continue

                        if not src_info.get("cache", True):
                            # File will be downloaded in-place
                            files_to_copy.pop(src_path)
                            src_path = dest_path

                        # Check if file is already in cache
                        if os.path.exists(src_path) and (os.path.getsize(src_path) > 0):
                            self._logger.debug(
                                "Using cached %s for %s", src_path, dest_name
                            )
                        else:
                            # File needs to be downloaded
                            src_url = src_info.get("url", None)
                            if src_url is None:
                                # Try with machine type
                                if machine_type in src_info:
                                    src_url = src_info[machine_type]["url"]
                                else:
                                    self._logger.error(
                                        "No entry for download file %s with machine type %s",
                                        src_url,
                                        machine_type,
                                    )
                                    continue

                            # Schedule file for download
                            if src_url not in files_to_download:
                                download_tasks.append(
                                    self.loop.create_task(
                                        download_file(src_url, src_path)
                                    )
                                )
                                files_to_download.add(src_url)

        # Wait for downloads to complete
        await asyncio.gather(*download_tasks)

        # Copy files
        for src_path, dest_path in files_to_copy.items():
            # Remove existing file/directory
            if os.path.isdir(dest_path):
                self._logger.debug("Removing %s", dest_path)
                shutil.rmtree(dest_path)
            elif os.path.isfile(dest_path):
                self._logger.debug("Removing %s", dest_path)
                os.unlink(dest_path)

            # Create necessary directories
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            # Copy file/directory as is
            status = f"Copying {src_path} to {dest_path}"
            self.download_status.append(status)
            self._logger.debug(status)
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dest_path)
            else:
                shutil.copy2(src_path, dest_path)

        # Extract/install files
        unpack_extensions = [
            ext for fmt in shutil.get_unpack_formats() for ext in fmt[1]
        ]

        for src_path, extract_paths in files_to_extract.items():
            # Check if the file extension will be understood by shutil.unpack_archive
            known_format = False
            for ext in unpack_extensions:
                if src_path.endswith(ext):
                    known_format = True

            def unpack_default(temp_dir):
                return shutil.unpack_archive(src_path, temp_dir)

            def unpack_gz(temp_dir):
                return self._unpack_gz(src_path, temp_dir)

            unpack = unpack_default

            if not known_format:
                # Handle special archives
                if src_path.endswith(".gz"):
                    # Single file compressed with gzip
                    unpack = unpack_gz
                else:
                    # Very bad situation
                    self._logger.warning(
                        "Unknown archive extension %s. This is probably going to fail.",
                        src_path,
                    )

            # Cached file is an archive. Unpack first.
            with tempfile.TemporaryDirectory() as temp_dir:
                unpack(temp_dir)

                for dest_path, src_extract in extract_paths:
                    src_exclude: Dict[str, List[str]] = {}
                    if "!" in src_extract:
                        extract_parts = src_extract.split("!")
                        src_extract = extract_parts[0]
                        src_exclude = defaultdict(list)
                        for exclude_path in extract_parts[1:]:
                            exclude_path = os.path.join(temp_dir, exclude_path)
                            exclude_dir, exclude_name = os.path.split(exclude_path)
                            src_exclude[exclude_dir].append(exclude_name)

                    # Remove existing file/directory
                    if os.path.isdir(dest_path):
                        self._logger.debug("Removing %s", dest_path)
                        shutil.rmtree(dest_path)
                    elif os.path.isfile(dest_path):
                        self._logger.debug("Removing %s", dest_path)
                        os.unlink(dest_path)

                    # Create necessary directories
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                    if src_extract.endswith(":"):
                        # Unpack .gz inside archive
                        src_path = os.path.join(temp_dir, src_extract[:-1])
                        extract_path = self._unpack_gz(src_path, temp_dir)
                    else:
                        # Regular file
                        extract_path = os.path.join(temp_dir, src_extract)

                    # Copy specific file/directory
                    status = f"Copying {extract_path} to {dest_path}"
                    self.download_status.append(status)
                    self._logger.debug(status)
                    if os.path.isdir(extract_path):
                        if src_exclude:
                            # Ignore some files
                            # pylint: disable=W0640
                            shutil.copytree(
                                extract_path,
                                dest_path,
                                ignore=lambda d, fs: src_exclude[d],
                            )
                        else:
                            # Copy everything
                            shutil.copytree(extract_path, dest_path)
                    else:
                        shutil.copy2(extract_path, dest_path)

    # -------------------------------------------------------------------------

    async def get_problems(self) -> Dict[str, Any]:
        """Return a dictionary with problems from each actor."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = await sys.async_ask(self.dialogue_manager, GetProblems())
            assert isinstance(result, Problems), result
            return result.problems
