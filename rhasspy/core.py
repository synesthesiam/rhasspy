import os
import sys
import logging
import subprocess
import shutil
import tempfile
import urllib.request
import platform
import gzip
from collections import defaultdict
import concurrent.futures
from typing import List, Dict, Optional, Any, Callable, Tuple, Union, Set

import pydash

# Internal imports
from .actor import ConfigureEvent, ActorSystem, RhasspyActor
from .profiles import Profile
from .audio_recorder import AudioData, StartRecordingToBuffer, StopRecordingToBuffer
from .stt import WavTranscription
from .intent import IntentRecognized
from .intent_handler import IntentHandled
from .pronounce import WordPronunciations, WordPhonemes, WordSpoken
from .tts import SentenceSpoken
from .dialogue import (
    DialogueManager,
    GetMicrophones,
    TestMicrophones,
    ListenForCommand,
    ListenForWakeWord,
    WakeWordDetected,
    WakeWordNotDetected,
    TrainProfile,
    ProfileTrainingFailed,
    GetWordPhonemes,
    SpeakWord,
    GetWordPronunciations,
    TranscribeWav,
    PlayWavData,
    PlayWavFile,
    RecognizeIntent,
    HandleIntent,
    ProfileTrainingComplete,
    ProfileTrainingFailed,
    MqttPublish,
    GetVoiceCommand,
    VoiceCommand,
    GetActorStates,
    GetSpeakers,
    SpeakSentence,
    GetProblems,
    Problems,
)

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
        self._logger.debug(f"Loaded profile from {self.profile.json_path}")
        self._logger.debug(
            f"Profile files will be written to {self.profile.write_path()}"
        )

        self.defaults = Profile.load_defaults(system_profiles_dir)

    # -------------------------------------------------------------------------

    def start(
        self,
        preload: Optional[bool] = None,
        block: bool = True,
        timeout: float = 60,
        observer: Optional[RhasspyActor] = None,
    ) -> None:
        """Start Rhasspy"""

        if self.actor_system is None:
            self.actor_system = ActorSystem()

        if preload is None:
            preload = self.profile.get("rhasspy.preload_profile", False)

        assert self.actor_system is not None
        self.dialogue_manager = self.actor_system.createActor(DialogueManager)
        with self.actor_system.private() as sys:
            sys.ask(
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
                result = sys.listen(timeout)

    # -------------------------------------------------------------------------

    def get_microphones(self, system: Optional[str] = None) -> Dict[Any, Any]:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, GetMicrophones(system))
            assert isinstance(result, dict), result
            return result

    def test_microphones(self, system: Optional[str] = None) -> Dict[Any, Any]:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, TestMicrophones(system))
            assert isinstance(result, dict), result
            return result

    def get_speakers(self, system: Optional[str] = None) -> Dict[Any, Any]:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, GetSpeakers(system))
            assert isinstance(result, dict), result
            return result

    # -------------------------------------------------------------------------

    def listen_for_wake(self) -> None:
        assert self.actor_system is not None
        self.actor_system.tell(self.dialogue_manager, ListenForWakeWord())

    def listen_for_command(self, handle: bool = True) -> Dict[str, Any]:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, ListenForCommand(handle=handle))
            assert isinstance(result, dict), result
            return result

    def record_command(self, timeout: Optional[float] = None) -> VoiceCommand:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, GetVoiceCommand(timeout=timeout))
            assert isinstance(result, VoiceCommand), result
            return result

    # -------------------------------------------------------------------------

    def transcribe_wav(self, wav_data: bytes) -> WavTranscription:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(
                self.dialogue_manager, TranscribeWav(wav_data, handle=False)
            )
            assert isinstance(result, WavTranscription), result
            return result

    def recognize_intent(self, text: str) -> IntentRecognized:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            # Fix casing
            dict_casing = self.profile.get("speech_to_text.dictionary_casing", "")
            if dict_casing == "lower":
                text = text.lower()
            elif dict_casing == "upper":
                text = text.upper()

            result = sys.ask(self.dialogue_manager, RecognizeIntent(text, handle=False))
            assert isinstance(result, IntentRecognized), result

            # Add slots
            intent_slots = {}
            for ev in result.intent.get("entities", []):
                intent_slots[ev["entity"]] = ev["value"]

            result.intent["slots"] = intent_slots

            return result

    def handle_intent(self, intent: Dict[str, Any]) -> IntentHandled:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, HandleIntent(intent))
            assert isinstance(result, IntentHandled), result
            return result

    # -------------------------------------------------------------------------

    def start_recording_wav(self, buffer_name: str = "") -> None:
        assert self.actor_system is not None
        self.actor_system.tell(
            self.dialogue_manager, StartRecordingToBuffer(buffer_name)
        )

    def stop_recording_wav(self, buffer_name: str = "") -> AudioData:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = self.actor_system.ask(
                self.dialogue_manager, StopRecordingToBuffer(buffer_name)
            )
            assert isinstance(result, AudioData), result
            return result

    # -------------------------------------------------------------------------

    def play_wav_data(self, wav_data: bytes) -> None:
        assert self.actor_system is not None
        self.actor_system.tell(self.dialogue_manager, PlayWavData(wav_data))

    def play_wav_file(self, wav_path: str) -> None:
        assert self.actor_system is not None
        self.actor_system.tell(self.dialogue_manager, PlayWavFile(wav_path))

    # -------------------------------------------------------------------------

    def get_word_pronunciations(
        self, words: List[str], n: int = 5
    ) -> WordPronunciations:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, GetWordPronunciations(words, n))
            assert isinstance(result, WordPronunciations), result
            return result

    def get_word_phonemes(self, word: str) -> WordPhonemes:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, GetWordPhonemes(word))
            assert isinstance(result, WordPhonemes), result
            return result

    def speak_word(self, word: str) -> WordSpoken:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, SpeakWord(word))
            assert isinstance(result, WordSpoken), result
            return result

    def speak_sentence(self, sentence: str) -> SentenceSpoken:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, SpeakSentence(sentence))
            assert isinstance(result, SentenceSpoken), result
            return result

    # -------------------------------------------------------------------------

    def train(
        self, reload_actors: bool = True
    ) -> Union[ProfileTrainingComplete, ProfileTrainingFailed]:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(
                self.dialogue_manager, TrainProfile(reload_actors=reload_actors)
            )
            assert isinstance(result, ProfileTrainingComplete) or isinstance(
                result, ProfileTrainingFailed
            ), result
            return result

    # -------------------------------------------------------------------------

    def mqtt_publish(self, topic: str, payload: bytes) -> None:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            sys.tell(self.dialogue_manager, MqttPublish(topic, payload))

    # -------------------------------------------------------------------------

    def wakeup_and_wait(self) -> Union[WakeWordDetected, WakeWordNotDetected]:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, ListenForWakeWord())
            assert isinstance(result, WakeWordDetected) or isinstance(
                result, WakeWordNotDetected
            ), result

            return result

    # -------------------------------------------------------------------------

    def get_actor_states(self) -> Dict[str, str]:
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, GetActorStates())
            assert isinstance(result, dict), result
            return result

    # -------------------------------------------------------------------------

    def send_audio_data(self, data: AudioData) -> None:
        assert self.actor_system is not None
        self.actor_system.tell(self.dialogue_manager, data)

    # -------------------------------------------------------------------------

    def shutdown(self) -> None:
        # Clear environment variables
        rhasspy_vars = [v for v in os.environ if v.startswith("RHASSPY")]

        for v in rhasspy_vars:
            del os.environ[v]

        # Stop actor system
        if self.actor_system is not None:
            self.actor_system.shutdown()
            self.actor_system = None

    # -------------------------------------------------------------------------

    def check_profile(self) -> Dict[str, str]:
        """Returns True if the profile has all necessary files downloaded."""
        output_dir = self.profile.write_path()
        missing_files: Dict[str, Any] = {}

        # Load configuration
        conditions = self.profile.get("download.conditions", {})

        # Check conditions
        for setting_name in conditions:
            real_value = self.profile.get(setting_name, None)

            # Compare setting values
            for setting_value, files_dict in conditions[setting_name].items():
                compare_func = lambda v1, v2: v1 == v2

                if compare_func(setting_value, real_value):
                    # Check if file needs to be downloaded
                    for dest_name in files_dict:
                        dest_path = os.path.join(output_dir, dest_name)
                        if not os.path.exists(dest_path):
                            missing_files[dest_path] = (setting_name, setting_value)

        return missing_files

    def _get_compare_func(self, value: str):
        """Use mini-language to allow for profile setting value comparison."""
        if value.startswith(">="):
            f_value = float(value[2:])
            return lambda v: v >= f_value
        elif value.startswith("<="):
            f_value = float(value[2:])
            return lambda v: v <= f_value
        elif value.startswith(">"):
            f_value = float(value[1:])
            return lambda v: v > f_value
        elif value.startswith("<"):
            f_value = float(value[1:])
            return lambda v: v < f_value
        elif value.startswith("!"):
            return lambda v: v != value
        else:
            return lambda v: v == value

    def _unpack_gz(self, src_path, temp_dir):
        # Strip off .gz and put relative to temporary directory
        temp_file_path = os.path.join(temp_dir, os.path.split(src_path[:-3])[1])

        # Decompress single file
        with open(src_path, "rb") as src_file:
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(gzip.decompress(src_file.read()))

        return temp_file_path

    # -------------------------------------------------------------------------

    def download_profile(self, delete=False) -> None:
        """Downloads all necessary profile files from the internet and extracts them."""
        output_dir = self.profile.write_path()
        download_dir = self.profile.write_path(
            self.profile.get("download.cache_dir", "download")
        )

        if delete and os.path.exists(download_dir):
            self._logger.debug(f"Deleting download cache at {download_dir}")
            shutil.rmtree(download_dir)

        os.makedirs(download_dir, exist_ok=True)

        # Load configuration
        conditions = self.profile.get("download.conditions", {})
        all_files = self.profile.get("download.files", {})
        files_to_copy = {}
        files_to_extract: Dict[str, List[Any]] = defaultdict(list)
        files_to_download: Set[str] = set()

        def download_file(url, filename):
            try:
                self._logger.debug(f"Downloading {url} to {filename}")
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                urllib.request.urlretrieve(url, filename)
            except Exception as e:
                self._logger.exception(url)

        # Check conditions
        machine_type = platform.machine()
        with concurrent.futures.ThreadPoolExecutor() as executor:
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
                                files_to_extract[src_path].append(
                                    (dest_path, src_extract)
                                )
                            else:
                                # Just a regular file
                                src_path = os.path.join(download_dir, src_name)
                                files_to_copy[src_path] = dest_path

                            # Get download/cache info for file
                            src_info = all_files.get(src_name, None)
                            if src_info is None:
                                self._logger.error(
                                    f"No entry for download file {src_name}"
                                )
                                continue

                            if not src_info.get("cache", True):
                                # File will be downloaded in-place
                                files_to_copy.pop(src_path)
                                src_path = dest_path

                            # Check if file is already in cache
                            if os.path.exists(src_path):
                                self._logger.debug(
                                    f"Using cached {src_path} for {dest_name}"
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
                                            f"No entry for download file {src_name} with machine type {machine_type}"
                                        )
                                        continue

                                # Schedule file for download
                                if not src_url in files_to_download:
                                    executor.submit(download_file, src_url, src_path)
                                    files_to_download.add(src_url)

        # Copy files
        for src_path, dest_path in files_to_copy.items():
            # Remove existing file/directory
            if os.path.isdir(dest_path):
                self._logger.debug(f"Removing {dest_path}")
                shutil.rmtree(dest_path)
            elif os.path.isfile(dest_path):
                self._logger.debug(f"Removing {dest_path}")
                os.unlink(dest_path)

            # Create necessary directories
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            # Copy file/directory as is
            self._logger.debug(f"Copying {src_path} to {dest_path}")
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

            unpack = lambda temp_dir: shutil.unpack_archive(src_path, temp_dir)
            if not known_format:
                # Handle special archives
                if src_path.endswith(".gz"):
                    # Single file compressed with gzip
                    unpack = lambda temp_dir: self._unpack_gz(src_path, temp_dir)
                else:
                    # Very bad situation
                    self._logger.warning(
                        f"Unknown archive extension {src_path}. This is probably going to fail."
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
                        self._logger.debug(f"Removing {dest_path}")
                        shutil.rmtree(dest_path)
                    elif os.path.isfile(dest_path):
                        self._logger.debug(f"Removing {dest_path}")
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
                    self._logger.debug(f"Copying {extract_path} to {dest_path}")
                    if os.path.isdir(extract_path):
                        ignore = None
                        if len(src_exclude) > 0:
                            ignore = lambda cur_dir, filenames: src_exclude[cur_dir]

                        shutil.copytree(extract_path, dest_path, ignore=ignore)
                    else:
                        shutil.copy2(extract_path, dest_path)

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Returns a dictionary with problems from each actor."""
        assert self.actor_system is not None
        with self.actor_system.private() as sys:
            result = sys.ask(self.dialogue_manager, GetProblems())
            assert isinstance(result, Problems), result
            return result.problems
