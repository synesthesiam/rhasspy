#!/usr/bin/env python3
import os
import logging
import subprocess
import tempfile

from .actor import RhasspyActor

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class AudioPlayer:
    '''Base class for WAV based audio players'''
    def __init__(self, core, device=None):
        '''Optional audio device handled by sub-classes.'''
        self.core = core
        self.device = device

    def play_file(self, path: str):
        '''Plays a WAV file from a path'''
        pass

    def play_data(self, wav_data: bytes):
        '''Plays a WAV file from a buffer'''
        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as wav_file:
            wav_file.write(wav_data)
            wav_file.seek(0)
            self.play_file(wav_file.name)

# -----------------------------------------------------------------------------
# APlay based audio player
# -----------------------------------------------------------------------------

class PlayWavFile:
    def __init__(self, wav_path: str):
        self.wav_path = wav_path

class PlayWavData:
    def __init__(self, wav_data: bytes):
        self.wav_data = wav_data

class APlayAudioPlayer(RhasspyActor):
    '''Plays WAV files using aplay'''

    def to_started(self, from_state):
        self.device = self.config.get('device') \
            or self.profile.get('sounds.aplay.device')

    def in_started(self, message, sender):
        if isinstance(message, PlayWavFile):
            self.play_file(message.wav_path)
        elif isinstance(message, PlayWavData):
            self.play_data(message.wav_data)

    # -------------------------------------------------------------------------

    def play_file(self, path: str):
        if not os.path.exists(path):
            return

        aplay_cmd = ['aplay', '-q']

        if self.device is not None:
            aplay_cmd.extend(['-D', str(self.device)])

        # Play file
        aplay_cmd.append(path)

        self._logger.debug(aplay_cmd)
        subprocess.run(aplay_cmd)

    def play_data(self, wav_data: bytes):
        aplay_cmd = ['aplay', '-q']

        if self.device is not None:
            aplay_cmd.extend(['-D', str(self.device)])

        self._logger.debug(aplay_cmd)

        # Play data
        subprocess.run(aplay_cmd, input=wav_data)

# -----------------------------------------------------------------------------
# MQTT audio player for Snips.AI Hermes Protocol
# https://docs.snips.ai/ressources/hermes-protocol
# -----------------------------------------------------------------------------

class HeremesAudioPlayer(AudioPlayer):
    '''Sends audio data over MQTT via Hermes protocol'''
    def play_file(self, path: str):
        if not os.path.exists(path):
            return

        with open(path, 'rb') as wav_file:
            self.play_data(wav_file.read())

    def play_data(self, wav_data: bytes):
        self.core.get_mqtt_client().play_bytes(wav_data)
