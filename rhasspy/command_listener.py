import io
import math
import logging
import threading
import wave
import queue

from .actor import RhasspyActor
from .audio_recorder import StartStreaming, StopStreaming, AudioData

# -----------------------------------------------------------------------------

class ListenForCommand:
    def __init__(self, receiver=None):
        self.receiver = receiver

class VoiceCommand:
    def __init__(self, data: bytes):
        self.data = data

# -----------------------------------------------------------------------------

class WebrtcvadCommandListener(RhasspyActor):
    '''Listens to microphone for voice commands bracketed by silence.'''
    def __init__(self):
        RhasspyActor.__init__(self)
        self.recorder = None
        self.receiver = None
        self.buffer = None
        self.chunk = None

    def to_started(self, from_state):
        import webrtcvad
        self.recorder = self.config['recorder']

        settings = self.profile.get('command.webrtcvad')
        self.sample_rate = settings['sample_rate']  # 16Khz
        self.chunk_size = settings['chunk_size']  # 10,20,30 ms
        self.vad_mode = settings['vad_mode'] # 0-3 (aggressiveness)
        self.min_sec = settings['min_sec']  # min seconds that command must last
        self.silence_sec = settings['silence_sec']  # min seconds of silence after command
        self.timeout_sec = settings['timeout_sec']  # max seconds that command can last

        self.seconds_per_buffer = self.chunk_size / self.sample_rate
        self.max_buffers = int(math.ceil(self.timeout_sec / self.seconds_per_buffer))

        self.vad = None
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(self.vad_mode)

        self.transition('loaded')

    # -------------------------------------------------------------------------

    def to_loaded(self, from_state):
        # Recording state
        self.chunk = bytes()
        self.max_buffers = int(math.ceil(self.timeout_sec / self.seconds_per_buffer))
        self.silence_buffers = int(math.ceil(self.silence_sec / self.seconds_per_buffer))
        self.min_phrase_buffers = int(math.ceil(self.min_sec / self.seconds_per_buffer))
        self.in_phrase = False
        self.after_phrase = False

    def in_loaded(self, message, sender):
        if isinstance(message, ListenForCommand):
            self.receiver = message.receiver or sender
            self.transition('listening')
            self.send(self.recorder, StartStreaming(self.myAddress))

    def in_listening(self, message, sender):
        if isinstance(message, AudioData):
            self.chunk += message.data
            if len(self.chunk) >= self.chunk_size:
                data = self.chunk[:self.chunk_size]
                self.chunk = self.chunk[self.chunk_size:]
                finished = self.process_data(data)
                if finished:
                    self.send(self.recorder, StopStreaming(self.myAddress))
                    self.send(self.receiver, VoiceCommand(self.buffer))
                    self.buffer = None
                    self.transition('loaded')

    # -------------------------------------------------------------------------

    def process_data(self, data):
        finished = False

        # Check maximum number of seconds to record
        self.max_buffers -= 1
        if self.max_buffers <= 0:
            # Timeout
            finished = True
            self._logger.warn('Timeout')

        # Detect speech in chunk
        is_speech = self.vad.is_speech(data, self.sample_rate)
        if is_speech and not self.in_phrase:
            # Start of phrase
            self.in_phrase = True
            self.after_phrase = False
            self.min_phrase_buffers = int(math.ceil(self.min_sec / self.seconds_per_buffer))
            self.buffer = data
        elif self.in_phrase and (self.min_phrase_buffers > 0):
            # In phrase, before minimum seconds
            self.buffer += data
            self.min_phrase_buffers -= 1
        elif self.in_phrase and is_speech:
            # In phrase, after minimum seconds
            self.buffer += data
        elif not is_speech:
            # Outside of speech
            if self.after_phrase and (self.silence_buffers > 0):
                # After phrase, before stop
                self.silence_buffers -= 1
                self.buffer += data
            elif self.after_phrase and (self.silence_buffers <= 0):
                # Phrase complete
                finished = True
                self.buffer += data
            elif self.in_phrase and (self.min_phrase_buffers <= 0):
                # Transition to after phrase
                self.after_phrase = True
                self.silence_buffers = int(math.ceil(self.silence_sec / self.seconds_per_buffer))

        return finished
