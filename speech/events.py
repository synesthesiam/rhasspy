#!/usr/bin/env python3
from typing import List

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------

class TranscribeWav:
    def __init__(self, wav_data: bytes):
        self.wav_data = wav_data

class WavTranscription:
    def __init__(self, text: str):
        self.text = text

# -----------------------------------------------------------------------------

class TrainLanguageModel:
    def __init__(self, sentences: List[str]):
        self.sentences = sentences

class LanguageModelTrained:
    def __init__(self, arpa_lm: str):
        self.arpa_lm = arpa_lm
