import io
import math
import logging
import threading
import wave
import queue

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class CommandListener(object):
    '''Listens to microphone for voice commands bracketed by silence.'''

    def __init__(self,
                 core,
                 sample_rate,
                 chunk_size=480,     # 30 ms
                 vad_mode=0,         # 0-3 (aggressiveness)
                 min_sec=2.0,        # min seconds that command must last
                 silence_sec=0.5,    # min seconds of silence after command
                 timeout_sec=30.0):  # max seconds that command can last

        self.core = core
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        self.vad_mode = vad_mode
        self.min_sec = min_sec
        self.silence_sec = silence_sec
        self.timeout_sec = timeout_sec

        self.seconds_per_buffer = self.chunk_size / self.sample_rate
        self.max_buffers = int(math.ceil(self.timeout_sec / self.seconds_per_buffer))

        self.vad = None

    # -------------------------------------------------------------------------

    def listen_for_command(self) -> bytes:
        '''Listens for a command and returns WAV data once command is finished.'''

        if self.vad is None:
            import webrtcvad
            self.vad = webrtcvad.Vad()
            self.vad.set_mode(self.vad_mode)

        recorded_data = bytes()

        # Process audio data in a separate thread
        def process_data():
            nonlocal recorded_data

            # Recording state
            max_buffers = int(math.ceil(self.timeout_sec / self.seconds_per_buffer))
            silence_buffers = int(math.ceil(self.silence_sec / self.seconds_per_buffer))
            min_phrase_buffers = int(math.ceil(self.min_sec / self.seconds_per_buffer))
            in_phrase = False
            after_phrase = False
            finished = False

            while True:
                # Block until audio data comes in
                try:
                    audio_queue = self.core.get_audio_recorder().get_queue()
                    data = audio_queue.get(True, self.seconds_per_buffer)
                    if len(data) == 0:
                        break
                except queue.Empty:
                    # No data available
                    data = None

                # Check maximum number of seconds to record
                max_buffers -= 1
                if max_buffers <= 0:
                    # Timeout
                    finished = True
                    logger.warn('Timeout')

                    # Reset
                    in_phrase = False
                    after_phrase = False

                # Detect speech in chunk
                if data is not None:
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
                    break

        # -----------------------------------------------------------------

        # Stream data into queue
        self.core.get_audio_recorder().start_recording(False, True)

        # Start listening
        logger.debug('Listening')
        thread = threading.Thread(target=process_data, daemon=True)
        thread.start()

        # Block until command is finished
        thread.join()

        # Stop listening and clean up
        self.core.get_audio_recorder().stop_recording(False, True)

        logger.debug('Stopped listening')
        logger.info('Recorded %s byte(s) of audio data' % len(recorded_data))

        # Return WAV data
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, mode='wb') as wav_file:
                wav_file.setframerate(self.sample_rate)
                wav_file.setsampwidth(2)
                wav_file.setnchannels(1)
                wav_file.writeframesraw(recorded_data)

            return wav_buffer.getvalue()
