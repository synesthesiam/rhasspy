"""Actor events for Rhasspy"""
from typing import Any, Dict, List, Optional

import pywrapfst as fst

from rhasspy.actor import RhasspyActor

# -----------------------------------------------------------------------------
# Wake
# -----------------------------------------------------------------------------


class ListenForWakeWord:
    """Request to start listening for a wake word."""

    def __init__(self, receiver: Optional[RhasspyActor] = None, record=True) -> None:
        self.receiver = receiver
        self.record = record


class StopListeningForWakeWord:
    """Request to stop listening for a wake word."""

    def __init__(
        self, receiver: Optional[RhasspyActor] = None, record=True, clear_all=False
    ) -> None:
        self.receiver = receiver
        self.record = record
        self.clear_all = clear_all


class WakeWordDetected:
    """Response when wake word is detected."""

    def __init__(self, name: str, audio_data_info: Dict[Any, Any] = None) -> None:
        self.name = name
        self.audio_data_info = audio_data_info or {}


class WakeWordNotDetected:
    """Response when wake word is not detected."""

    def __init__(self, name: str, audio_data_info: Dict[Any, Any] = None) -> None:
        self.name = name
        self.audio_data_info = audio_data_info or {}


class PauseListeningForWakeWord:
    """Pause wake word detection."""

    pass


class ResumeListeningForWakeWord:
    """Resume wake word detection."""

    pass


# -----------------------------------------------------------------------------
# audio Player
# -----------------------------------------------------------------------------


class PlayWavFile:
    """Play a WAV file."""

    def __init__(self, wav_path: str, receiver: Optional[RhasspyActor] = None) -> None:
        self.wav_path = wav_path
        self.receiver = receiver


class PlayWavData:
    """Play a WAV buffer."""

    def __init__(
        self, wav_data: bytes, receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.wav_data = wav_data
        self.receiver = receiver


class WavPlayed:
    """Response to PlayWavFile or PlayWavData."""

    pass


# -----------------------------------------------------------------------------
# Audio Recording
# -----------------------------------------------------------------------------


class AudioData:
    """Raw 16-bit 16Khz audio data."""

    def __init__(self, data: bytes, **kwargs: Any) -> None:
        self.data = data
        self.info = kwargs


class StartStreaming:
    """Tells microphone to begin recording. Emits AudioData chunks."""

    def __init__(self, receiver: Optional[RhasspyActor] = None) -> None:
        self.receiver = receiver


class StopStreaming:
    """Tells microphone to stop recording."""

    def __init__(self, receiver: Optional[RhasspyActor] = None) -> None:
        self.receiver = receiver


class StartRecordingToBuffer:
    """Tells microphone to record audio data to named buffer."""

    def __init__(self, buffer_name: str) -> None:
        self.buffer_name = buffer_name


class StopRecordingToBuffer:
    """Tells microphone to stop recording to buffer and emit AudioData."""

    def __init__(
        self, buffer_name: str, receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.buffer_name = buffer_name
        self.receiver = receiver


# -----------------------------------------------------------------------------
# Command Listener
# -----------------------------------------------------------------------------


class ListenForCommand:
    """Tell Rhasspy to listen for a voice command."""

    def __init__(
        self,
        receiver: Optional[RhasspyActor] = None,
        handle: bool = True,
        timeout: Optional[float] = None,
        entities: List[Dict[str, Any]] = None,
    ) -> None:
        self.receiver = receiver
        self.handle = handle
        self.timeout = timeout
        self.entities = entities or []


class VoiceCommand:
    """Response to ListenForCommand."""

    def __init__(self, data: bytes, timeout: bool = False, handle: bool = True) -> None:
        self.data = data
        self.timeout = timeout
        self.handle = handle


# -----------------------------------------------------------------------------
# Intent Recognition
# -----------------------------------------------------------------------------


class RecognizeIntent:
    """Request to recognize an intent."""

    def __init__(
        self,
        text: str,
        receiver: Optional[RhasspyActor] = None,
        handle: bool = True,
        confidence: float = 1,
    ) -> None:
        self.text = text
        self.confidence = confidence
        self.receiver = receiver
        self.handle = handle


class IntentRecognized:
    """Response to RecognizeIntent."""

    def __init__(self, intent: Dict[str, Any], handle: bool = True) -> None:
        self.intent = intent
        self.handle = handle


# -----------------------------------------------------------------------------
# Intent Handling
# -----------------------------------------------------------------------------


class HandleIntent:
    """Request to handle intent."""

    def __init__(
        self, intent: Dict[str, Any], receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.intent = intent
        self.receiver = receiver


class IntentHandled:
    """Response to HandleIntent."""

    def __init__(self, intent: Dict[str, Any]) -> None:
        self.intent = intent


class ForwardIntent:
    """Request intent be forwarded to Home Assistant."""

    def __init__(
        self, intent: Dict[str, Any], receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.intent = intent
        self.receiver = receiver


class IntentForwarded:
    """Response to ForwardIntent."""

    def __init__(self, intent: Dict[str, Any]) -> None:
        self.intent = intent


# -----------------------------------------------------------------------------
# Intent Handling
# -----------------------------------------------------------------------------


class TrainIntent:
    """Request to train intent recognizer."""

    def __init__(self, intent_fst, receiver: Optional[RhasspyActor] = None) -> None:
        self.intent_fst = intent_fst
        self.receiver = receiver


class IntentTrainingComplete:
    """Response when training is successful."""

    pass


class IntentTrainingFailed:
    """Response when training fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


# -----------------------------------------------------------------------------
# MQTT
# -----------------------------------------------------------------------------


class MqttPublish:
    """Request to publish payload to topic."""

    def __init__(self, topic: str, payload: bytes) -> None:
        self.topic = topic
        self.payload = payload


class MqttSubscribe:
    """Request to subscribe to a topic."""

    def __init__(self, topic: str, receiver: Optional[RhasspyActor] = None) -> None:
        self.topic = topic
        self.receiver = receiver


class MqttConnected:
    """Response when connected to broker."""

    pass


class MqttDisconnected:
    """Response when disconnected from broker."""

    pass


class MqttMessage:
    """Response when MQTT message is received."""

    def __init__(self, topic: str, payload: bytes) -> None:
        self.topic = topic
        self.payload = payload


# -----------------------------------------------------------------------------
# Word Pronunciation
# -----------------------------------------------------------------------------


class SpeakWord:
    """Speak a word's pronunciation"""

    def __init__(self, word: str, receiver: Optional[RhasspyActor] = None) -> None:
        self.word = word
        self.receiver = receiver


class WordSpoken:
    """Response to SpeakWord"""

    def __init__(self, word: str, wav_data: bytes, phonemes: str) -> None:
        self.word = word
        self.wav_data = wav_data
        self.phonemes = phonemes


class GetWordPhonemes:
    """Get eSpeak phonemes for a word"""

    def __init__(self, word: str, receiver: Optional[RhasspyActor] = None) -> None:
        self.word = word
        self.receiver = receiver


class WordPhonemes:
    """Response to GetWordPhonemes"""

    def __init__(self, word: str, phonemes: str) -> None:
        self.word = word
        self.phonemes = phonemes


class GetWordPronunciations:
    """Look up or guess word pronunciation(s)"""

    def __init__(
        self, words: List[str], n: int = 5, receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.words = words
        self.n = n
        self.receiver = receiver


class WordPronunciations:
    """Response to GetWordPronunciations"""

    def __init__(self, pronunciations: Dict[str, Dict[str, Any]]) -> None:
        self.pronunciations = pronunciations


class PronunciationFailed:
    """Response when g2p fails"""

    def __init__(self, reason: str) -> None:
        self.reason = reason


# -----------------------------------------------------------------------------
# Speech to Text
# -----------------------------------------------------------------------------


class TranscribeWav:
    """Request to transcribe text from WAV buffer."""

    def __init__(
        self,
        wav_data: bytes,
        receiver: Optional[RhasspyActor] = None,
        handle: bool = True,
    ) -> None:
        self.wav_data = wav_data
        self.receiver = receiver
        self.handle = handle


class WavTranscription:
    """Response to TranscribeWav."""

    def __init__(self, text: str, handle: bool = True, confidence: float = 1) -> None:
        self.text = text
        self.confidence = confidence
        self.handle = handle


# -----------------------------------------------------------------------------
# Speech Training
# -----------------------------------------------------------------------------


class TrainSpeech:
    """Request to train speech to text system."""

    def __init__(
        self, intent_fst: fst.Fst, receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.intent_fst = intent_fst
        self.receiver = receiver


class SpeechTrainingComplete:
    """Response when training is successful."""

    def __init__(self, intent_fst: fst.Fst) -> None:
        self.intent_fst = intent_fst


class SpeechTrainingFailed:
    """Response when training fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


# -----------------------------------------------------------------------------
# Text to Speech
# -----------------------------------------------------------------------------


class SpeakSentence:
    """Request to speak a sentence."""

    def __init__(
        self,
        sentence: str,
        receiver: Optional[RhasspyActor] = None,
        play: bool = True,
        voice: Optional[str] = None,
        language: Optional[str] = None,
    ) -> None:
        self.sentence = sentence
        self.receiver = receiver
        self.play = play
        self.voice = voice
        self.language = language


class SentenceSpoken:
    """Response when sentence is spoken."""

    def __init__(self, wav_data: Optional[bytes] = None):
        self.wav_data: bytes = wav_data or bytes()


# -----------------------------------------------------------------------------
# Dialogue
# -----------------------------------------------------------------------------


class GetMicrophones:
    """Request list of micrphones."""

    def __init__(self, system: Optional[str] = None) -> None:
        self.system = system


class TestMicrophones:
    """Request live microphones."""

    def __init__(self, system: Optional[str] = None) -> None:
        self.system = system


class GetSpeakers:
    """Request list of audio players."""

    def __init__(self, system: Optional[str] = None) -> None:
        self.system = system


class TrainProfile:
    """Request training for profile."""

    def __init__(
        self, receiver: Optional[RhasspyActor] = None, reload_actors: bool = True
    ) -> None:
        self.receiver = receiver
        self.reload_actors = reload_actors


class ProfileTrainingFailed:
    """Response when training fails."""

    def __init__(self, reason: str):
        self.reason = reason

    def __repr__(self):
        return f"FAILED: {self.reason}"


class ProfileTrainingComplete:
    """Response when training succeeds."""

    def __repr__(self):
        return "OK"


class Ready:
    """Emitted when all actors have been loaded."""

    def __init__(
        self, timeout: bool = False, problems: Optional[Dict[str, Any]] = None
    ) -> None:
        self.timeout = timeout
        self.problems = problems or {}


class GetVoiceCommand:
    """Request to record a voice command."""

    def __init__(
        self, receiver: Optional[RhasspyActor] = None, timeout: Optional[float] = None
    ) -> None:
        self.receiver = receiver
        self.timeout = timeout


class GetActorStates:
    """Request for actors' current states."""

    pass


class GetProblems:
    """Request any problems during startup."""

    pass


class Problems:
    """Response to GetProblems."""

    def __init__(self, problems: Optional[Dict[str, Any]] = None):
        self.problems = problems or {}
