import io
import math
import logging
import threading
import wave
import queue
from datetime import timedelta

from thespian.actors import WakeupMessage

from .actor import RhasspyActor
from .audio_recorder import StartStreaming, StopStreaming, AudioData

# -----------------------------------------------------------------------------

class ListenForCommand:
    def __init__(self, receiver=None, handle=True, timeout=None):
        self.receiver = receiver
        self.handle = handle
        self.timeout = timeout

class VoiceCommand:
    def __init__(self, data: bytes, timeout=False, handle=True):
        self.data = data
        self.timeout = timeout
        self.handle = handle

# -----------------------------------------------------------------------------

class DummyCommandListener(RhasspyActor):
    '''Always sends an empty voice command'''
    def in_started(self, message, sender):
        if isinstance(message, ListenForCommand):
            self.send(message.receiver or sender,
                      VoiceCommand(bytes()))

# -----------------------------------------------------------------------------
# webrtcvad based voice command listener
# https://github.com/wiseman/py-webrtcvad
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

        self.settings = self.profile.get('command.webrtcvad')
        self.sample_rate = self.settings['sample_rate']  # 16Khz
        self.chunk_size = self.settings['chunk_size']  # 10,20,30 ms
        self.vad_mode = self.settings['vad_mode'] # 0-3 (aggressiveness)
        self.min_sec = self.settings['min_sec']  # min seconds that command must last
        self.silence_sec = self.settings['silence_sec']  # min seconds of silence after command
        self.timeout_sec = self.settings['timeout_sec']  # max seconds that command can last
        self.throwaway_buffers = self.settings['throwaway_buffers']
        self.speech_buffers = self.settings['speech_buffers']

        self.seconds_per_buffer = self.chunk_size / self.sample_rate
        self.max_buffers = int(math.ceil(self.timeout_sec / self.seconds_per_buffer))

        self.vad = None
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(self.vad_mode)

        self.handle = True

        self.transition('loaded')

    # -------------------------------------------------------------------------

    def to_loaded(self, from_state):
        # Recording state
        self.chunk = bytes()
        self.silence_buffers = int(math.ceil(self.silence_sec / self.seconds_per_buffer))
        self.min_phrase_buffers = int(math.ceil(self.min_sec / self.seconds_per_buffer))
        self.throwaway_buffers_left = self.throwaway_buffers
        self.speech_buffers_left = self.speech_buffers
        self.in_phrase = False
        self.after_phrase = False
        self.buffer_count = 0

    def in_loaded(self, message, sender):
        if isinstance(message, ListenForCommand):
            if message.timeout is not None:
                # Use message timeout
                self.timeout_sec = message.timeout
            else:
                # Use default timeout
                self.timeout_sec = self.settings['timeout_sec']

            self.max_buffers = int(math.ceil(self.timeout_sec / self.seconds_per_buffer))
            self.receiver = message.receiver or sender
            self.transition('listening')
            self.handle = message.handle
            self.send(self.recorder, StartStreaming(self.myAddress))

    def to_listening(self, from_state):
        self.wakeupAfter(timedelta(seconds=self.timeout_sec))

    def in_listening(self, message, sender):
        if isinstance(message, WakeupMessage):
            # Timeout
            self._logger.warn('Timeout')
            self.send(self.recorder, StopStreaming(self.myAddress))
            self.send(self.receiver,
                      VoiceCommand(self.buffer, timeout=True, handle=self.handle))

            self.buffer = None
            self.transition('loaded')
        elif isinstance(message, AudioData):
            self.chunk += message.data
            if len(self.chunk) >= self.chunk_size:
                # Ensure audio data is properly chunked (for webrtcvad)
                data = self.chunk[:self.chunk_size]
                self.chunk = self.chunk[self.chunk_size:]

                # Process chunk
                finished, timeout = self.process_data(data)

                if finished:
                    # Stop recording
                    self.send(self.recorder, StopStreaming(self.myAddress))

                    # Response
                    self.send(self.receiver,
                              VoiceCommand(self.buffer, timeout, self.handle))

                    self.buffer = None
                    self.transition('loaded')

    def to_stopped(self, from_state):
        # Stop recording
        self.send(self.recorder, StopStreaming(self.myAddress))

    # -------------------------------------------------------------------------

    def process_data(self, data):
        finished = False
        timeout = False

        self.buffer_count += 1

        # Check maximum number of seconds to record
        self.max_buffers -= 1
        if self.max_buffers <= 0:
            # Timeout
            finished = True
            timeout = True
            self._logger.warn('Timeout')

        # Throw away first N buffers (noise)
        if self.throwaway_buffers_left > 0:
            self.throwaway_buffers_left -= 1
            return False, False

        # Detect speech in chunk
        is_speech = self.vad.is_speech(data, self.sample_rate)

        if is_speech and self.speech_buffers_left > 0:
            self.speech_buffers_left -= 1
        elif is_speech and not self.in_phrase:
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
            if not self.in_phrase:
                # Reset
                self.speech_buffers_left = self.speech_buffers
            elif self.after_phrase and (self.silence_buffers > 0):
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

        return finished, timeout
