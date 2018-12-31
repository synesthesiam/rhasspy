#!/usr/bin/env python3
import os
import logging
import subprocess
import tempfile
from typing import Optional

# from thespian.actors import Actor, ActorSystem

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class AudioPlayer:
    def __init__(self, device=None):
        self.device = device

    def play_file(self, path: str):
        pass

    def play_data(self, wav_data: bytes):
        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as wav_file:
            wav_file.write(wav_data)
            wav_file.seek(0)
            self.play_file(wav_file.name)

# -----------------------------------------------------------------------------

class APlayAudioPlayer(AudioPlayer):
    def __init__(self, device=None):
        AudioPlayer.__init__(self, device)

    def play_file(self, path: str):
        if not os.path.exists(path):
            return

        aplay_cmd = ['aplay', '-q']

        if self.device is not None:
            aplay_cmd.extend(['-D', str(self.device)])

        aplay_cmd.append(path)

        logger.debug(aplay_cmd)
        subprocess.run(aplay_cmd)

    def play_data(self, wav_data: bytes):
        aplay_cmd = ['aplay', '-q']

        if self.device is not None:
            aplay_cmd.extend(['-D', str(self.device)])

        logger.debug(aplay_cmd)

        subprocess.run(aplay_cmd, input=wav_data)

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------

# class PlayWavFile:
#     def __init__(self, path: str, device: str=None):
#         self.path = path
#         self.device = device

# class WavFilePlayed:
#     def __init__(self, path: str):
#         self.path = path

# -----------------------------------------------------------------------------
# aplay Based Actor
# -----------------------------------------------------------------------------

# class APlayActor(Actor):
#     def receiveMessage(self, message, sender):
#         try:
#             if isinstance(message, PlayWavFile):
#                 self.play_wav(message.path, message.device)
#                 self.send(sender, WavFilePlayed(message.path))
#         except Exception as e:
#             logger.exception('receiveMessage')

#     def play_wav(self, path: str, device: str=None):
#         aplay_cmd = ['aplay']

#         if device is not None:
#             aplay_cmd.extend(['-D', str(device)])

#         aplay_cmd.append(path)
#         subprocess.run(aplay_cmd)

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

# if __name__ == '__main__':
#     # Start actor system
#     system = ActorSystem('multiprocQueueBase')

#     try:
#         actor = system.createActor(APlayActor)
#         system.ask(actor, PlayWavFile('etc/wav/beep_lo.wav'))
#     finally:
#         # Shut down actor system
#         system.shutdown()
