import math
import logging
import threading

import pyaudio
import webrtcvad

# Default settings for command listener
DEFAULT_DEVICE_INDEX = -1    # default microphone
DEFAULT_SAMPLE_RATE = 16000  # 16Khz
DEFAULT_SAMPLE_WIDTH = 2     # 16-bit
DEFAULT_CHANNELS = 1         # mono
DEFAULT_CHUNK_SIZE = 480     # 30 ms

DEFAULT_VAD_MODE = 0         # 0-3 (aggressiveness)

DEFAULT_MIN_SEC = 2.0        # min seconds that command must last
DEFAULT_SILENCE_SEC = 0.5    # min seconds of silence after command
DEFAULT_TIMEOUT_SEC = 30.0   # max seconds that command can last

class CommandListener(object):
    def __init__(self,
                 device_index=DEFAULT_DEVICE_INDEX,
                 sample_rate=DEFAULT_SAMPLE_RATE,
                 sample_width=DEFAULT_SAMPLE_WIDTH,
                 channels=DEFAULT_CHANNELS,
                 chunk_size=DEFAULT_CHUNK_SIZE,
                 vad_mode=DEFAULT_VAD_MODE,
                 min_sec=DEFAULT_MIN_SEC,
                 silence_sec=DEFAULT_SILENCE_SEC,
                 timeout_sec=DEFAULT_TIMEOUT_SEC):

        self.logger = logging.getLogger(__name__)

        self.device_index = device_index
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels
        self.chunk_size = chunk_size

        self.vad_mode = vad_mode
        self.min_sec = min_sec
        self.silence_sec = silence_sec
        self.timeout_sec = timeout_sec

        self.seconds_per_buffer = self.chunk_size / self.sample_rate
        self.max_buffers = int(math.ceil(self.timeout_sec / self.seconds_per_buffer))

        self.vad = None
        self.audio = None

    def listen(self, filename=None, url=None):
        if self.vad is None:
            self.vad = webrtcvad.Vad()
            self.vad.set_mode(self.vad_mode)

        recorded_data = []
        finished_event = threading.Event()

        # Recording state
        max_buffers = int(math.ceil(self.timeout_sec / self.seconds_per_buffer))
        silence_buffers = int(math.ceil(self.silence_sec / self.seconds_per_buffer))
        min_phrase_buffers = int(math.ceil(self.min_sec / self.seconds_per_buffer))
        in_phrase = False
        after_phrase = False
        finished = False

        # PyAudio callback function
        def stream_callback(data, frame_count, time_info, status):
            nonlocal max_buffers, silence_buffers, min_phrase_buffers
            nonlocal in_phrase, after_phrase
            nonlocal recorded_data, finished

            # Check maximum number of seconds to record
            max_buffers -= 1
            if max_buffers <= 0:
                # Timeout
                finished = True

                # Reset
                in_phrase = False
                after_phrase = False

            # Detect speech in chunk
            is_speech = self.vad.is_speech(data, self.sample_rate)
            if is_speech and not in_phrase:
                # Start of phrase
                in_phrase = True
                after_phrase = False
                recorded_data = data
                min_phrase_buffers = int(math.ceil(self.min_sec / self.seconds_per_buffer))
            elif in_phrase and (min_phrase_buffers > 0):
                # In phrase, before minimum seconds
                recorded_data += data
                min_phrase_buffers -= 1
            elif in_phrase and is_speech:
                # In phrase, after minimum seconds
                recorded_data += data
            elif not is_speech:
                # Outside of speech
                if after_phrase and (silence_buffers > 0):
                    # After phrase, before stop
                    recorded_data += data
                    silence_buffers -= 1
                elif after_phrase and (silence_buffers <= 0):
                    # Phrase complete
                    recorded_data += data
                    finished = True

                    # Reset
                    in_phrase = False
                    after_phrase = False
                elif in_phrase and (min_phrase_buffers <= 0):
                    # Transition to after phrase
                    after_phrase = True
                    silence_buffers = int(math.ceil(self.silence_sec / self.seconds_per_buffer))

            if finished:
                finished_event.set()

            return (data, pyaudio.paContinue)

        # -----------------------------------------------------------------

        # Open microphone device
        audio = pyaudio.PyAudio()
        device_index = None
        if self.device_index >= 0:
            device_index = self.device_index

        data_format = pyaudio.get_format_from_width(self.sample_width)

        mic = audio.open(format=data_format,
                         channels=self.channels,
                         rate=self.sample_rate,
                         input_device_index=device_index,
                         input=True,
                         stream_callback=stream_callback,
                         frames_per_buffer=self.chunk_size)

        # Start listening
        self.logger.debug('Listening')
        mic.start_stream()

        # Block until command is finished
        finished_event.wait()

        # Stop listening and clean up
        mic.stop_stream()
        mic.close()
        audio.terminate()

        self.logger.debug('Stopped listening')
        self.logger.info('Recorded %s byte(s) of audio' % len(recorded_data))

        return recorded_data
