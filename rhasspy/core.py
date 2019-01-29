import os
import sys
from typing import List, Dict, Optional, Any, Callable, Tuple, Union

import pydash
from thespian.actors import ActorSystem, ActorAddress

# Internal imports
from .actor import ConfigureEvent
from .profiles import Profile
from .audio_recorder import AudioData, StartRecordingToBuffer, StopRecordingToBuffer
from .stt import WavTranscription
from .intent import IntentRecognized
from .intent_handler import IntentHandled
from .pronounce import WordPronunciation, WordPhonemes, WordSpoken
from .dialogue import (DialogueManager, GetMicrophones, TestMicrophones,
                       ListenForCommand, ListenForWakeWord,
                       TrainProfile, ProfileTrainingFailed,
                       GetWordPhonemes, SpeakWord, GetWordPronunciations,
                       TranscribeWav, PlayWavData, PlayWavFile,
                       RecognizeIntent, HandleIntent,
                       ProfileTrainingComplete, ProfileTrainingFailed)

# -----------------------------------------------------------------------------

class RhasspyCore:
    '''Core class for Rhasspy functionality.'''

    def __init__(self,
                 profile_name: str,
                 profiles_dirs: List[str],
                 actor_system: Optional[ActorSystem] = None) -> None:

        self.profiles_dirs = profiles_dirs
        self.profile_name = profile_name
        self.actor_system = actor_system or ActorSystem('multiprocQueueBase')

        self.profile = Profile(profile_name, profiles_dirs)
        self.defaults = Profile.load_defaults(profiles_dirs)

        # ---------------------------------------------------------------------

        preload = self.profile.get('rhasspy.preload_profile', False)
        self.dialogue_manager = self.actor_system.createActor(DialogueManager)
        with self.actor_system.private() as sys:
            print(dir(sys))
            sys.ask(self.dialogue_manager,
                    ConfigureEvent(self.profile, preload=preload, ready=True))

            # Block until ready
            sys.listen()

    # -------------------------------------------------------------------------

    def get_microphones(self, system=None) -> Dict[Any, Any]:
        with self.actor_system.private() as sys:
            return sys.ask(self.dialogue_manager, GetMicrophones(system))

    def test_microphones(self, system=None) -> Dict[Any, Any]:
        with self.actor_system.private() as sys:
            return sys.ask(self.dialogue_manager, TestMicrophones(system))

    # -------------------------------------------------------------------------

    def listen_for_wake(self) -> None:
        self.actor_system.tell(self.dialogue_manager, ListenForWakeWord())


    def listen_for_command(self, handle=True) -> None:
        with self.actor_system.private() as sys:
            return sys.ask(self.dialogue_manager, ListenForCommand(handle=handle))

    # -------------------------------------------------------------------------

    def transcribe_wav(self, wav_data: bytes) -> WavTranscription:
        with self.actor_system.private() as sys:
            return sys.ask(self.dialogue_manager, TranscribeWav(wav_data, handle=False))

    def recognize_intent(self, text: str) -> IntentRecognized:
        with self.actor_system.private() as sys:
            return sys.ask(self.dialogue_manager, RecognizeIntent(text, handle=False))

    def handle_intent(self, intent: Dict[str, Any]) -> IntentHandled:
        with self.actor_system.private() as sys:
            return sys.ask(self.dialogue_manager, HandleIntent(intent))

    # -------------------------------------------------------------------------

    def start_recording_wav(self, buffer_name:str = ''):
        self.actor_system.tell(self.dialogue_manager,
                               StartRecordingToBuffer(buffer_name))

    def stop_recording_wav(self, buffer_name:str = '') -> AudioData:
        with self.actor_system.private() as sys:
            return self.actor_system.ask(self.dialogue_manager,
                                         StopRecordingToBuffer(buffer_name))

    # -------------------------------------------------------------------------

    def play_wav_data(self, wav_data: bytes) -> None:
        self.actor_system.tell(self.dialogue_manager, PlayWavData(wav_data))

    def play_wav_file(self, wav_path: str) -> None:
        self.actor_system.tell(self.dialogue_manager, PlayWavFile(wav_data))

    # -------------------------------------------------------------------------

    def get_word_pronunciations(self, word: str, n: int = 5) -> WordPronunciation:
        with self.actor_system.private() as sys:
            return sys.ask(self.dialogue_manager, GetWordPronunciations(word, n))

    def get_word_phonemes(self, word: str) -> WordPhonemes:
        with self.actor_system.private() as sys:
            return sys.ask(self.dialogue_manager, GetWordPhonemes(word))

    def speak_word(self, word: str) -> WordSpoken:
        with self.actor_system.private() as sys:
            return sys.ask(self.dialogue_manager, SpeakWord(word))

    # -------------------------------------------------------------------------

    def train(self) -> Union[ProfileTrainingComplete, ProfileTrainingFailed]:
        with self.actor_system.private() as sys:
            return sys.ask(self.dialogue_manager, TrainProfile())

    # -------------------------------------------------------------------------

    def shutdown(self) -> None:
        if self.actor_system is not None:
            self.actor_system.shutdown()
            self.actor_system = None
