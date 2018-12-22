#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

from thespian.actors import ActorSystem

from events import TranscribeWav, WavTranscription
from sphinx import PocketsphinxSpeechActor

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    profile = Profile('en', ['profiles'])

    # Start actor system
    system = ActorSystem('multiprocQueueBase')

    try:
        pass
    finally:
        # Shut down actor system
        system.shutdown()
