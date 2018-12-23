#!/usr/bin/env python3
import os
import logging
import subprocess

from thespian.actors import Actor, ActorSystem

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------

class PlayWavFile:
    def __init__(self, path: str, device: str=None):
        self.path = path
        self.device = device

class WavFilePlayed:
    def __init__(self, path: str):
        self.path = path

# -----------------------------------------------------------------------------
# aplay Based Actor
# -----------------------------------------------------------------------------

class APlayActor(Actor):
    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, PlayWavFile):
                self.play_wav(message.path, message.device)
                self.send(sender, WavFilePlayed(message.path))
        except Exception as e:
            logging.exception('receiveMessage')

    def play_wav(self, path: str, device: str=None):
        aplay_cmd = ['aplay']

        if device is not None:
            aplay_cmd.extend(['-D', str(device)])

        aplay_cmd.append(path)
        subprocess.run(aplay_cmd)

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
