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
    def play_wav(self, path: str, device: Optional[str] = None):
        pass

    def play_wav(self, wav_data: bytes, device: Optional[str] = None):
        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as wav_file:
            wav_file.write(wav_data)
            wav_file.seek(0)
            self.play_wav(wav_file.name)

# -----------------------------------------------------------------------------

class APlayAudioPlayer(AudioPlayer):
    def play_wav(self, path: str, device: str=None):
        aplay_cmd = ['aplay']

        if device is not None:
            aplay_cmd.extend(['-D', str(device)])

        aplay_cmd.append(path)
        subprocess.run(aplay_cmd)

    def play_wav(self, wav_data: bytes, device: str=None):
        aplay_cmd = ['aplay']

        if device is not None:
            aplay_cmd.extend(['-D', str(device)])

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

if __name__ == '__main__':
    # Start actor system
    system = ActorSystem('multiprocQueueBase')

    try:
        actor = system.createActor(APlayActor)
        system.ask(actor, PlayWavFile('etc/wav/beep_lo.wav'))
    finally:
        # Shut down actor system
        system.shutdown()
