#!/usr/bin/env python3
import os
import logging
import subprocess
import threading
import time
import wave
import io
import re
from queue import Queue
from typing import Dict, Any, Callable, Optional

from stt import SpeechDecoder

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class AudioRecorder:
    '''Base class for microphone audio recorders'''
    def __init__(self, core, device=None):
        self.core = core
        self.device = device
        self._is_recording = False

    def start_recording(self, start_buffer: bool, start_queue: bool, device: Any=None):
        '''Starts recording from the microphone.

        If start_buffer is True, record audio data to an internal buffer.
        If start_queue is True, publish audio data to the queue returned by get_queue().

        Optional device is handled by specific sub-class.
        '''
        pass

    def stop_recording(self, stop_buffer: bool, stop_queue: bool) -> bytes:
        '''Stops recording from the microphone.

        If stop_buffer is True, stop recording to internal buffer and return buffer contents.
        If stop_queue is True, stop publishing data to queue.

        Returns internal audio buffer as WAV if stop_buffer is True.
        '''
        return bytes()

    def stop_all(self) -> None:
        '''Immediately stop all recording.'''
        pass

    def get_queue(self) -> Queue:
        '''Returns the queue where audio data is published.'''
        return Queue()

    def get_microphones(self) -> Dict[Any, Any]:
        '''Returns a dictionary of microphone names/descriptions.'''
        return {}

    @property
    def is_recording(self):
        '''True if currently recording from microphone.'''
        return self._is_recording

# -----------------------------------------------------------------------------
# PyAudio based audio recorder
# https://people.csail.mit.edu/hubert/pyaudio/
# -----------------------------------------------------------------------------

class PyAudioRecorder(AudioRecorder):
    '''Records from microphone using pyaudio'''
    def __init__(self, core, device=None, frames_per_buffer=480):
        # Frames per buffer is set to 30 ms for webrtcvad
        AudioRecorder.__init__(self, core, device)
        self.audio = None
        self.mic = None
        self.frames_per_buffer = frames_per_buffer

        self.buffer = bytes()
        self.buffer_users = 0

        self.queue = Queue()
        self.queue_users = 0

    def start_recording(self, start_buffer: bool, start_queue: bool, device: Any=None):
        import pyaudio

        device_index = device or self.device
        if device_index is not None:
            device_index = int(device_index)
            if device_index < -1:
                # Default device
                device_index = None

        # Allow for multiple "users" to receive audio data
        if start_buffer:
            self.buffer_users += 1

        if start_queue:
            self.queue_users += 1

        if not self.is_recording:
            # Reset
            self.buffer = bytes()

            # Clear queue
            while not self.queue.empty():
                self.queue.get_nowait()

            # Start audio system
            def stream_callback(data, frame_count, time_info, status):
                if self.buffer_users > 0:
                    self.buffer += data

                if self.queue_users > 0:
                    self.queue.put(data)

                return (data, pyaudio.paContinue)

            self.audio = pyaudio.PyAudio()
            data_format = self.audio.get_format_from_width(2)  # 16-bit
            self.mic = self.audio.open(format=data_format,
                                       channels=1,
                                       rate=16000,
                                       input_device_index=device_index,
                                       input=True,
                                       stream_callback=stream_callback,
                                       frames_per_buffer=self.frames_per_buffer)

            self.mic.start_stream()
            self._is_recording = True
            logger.debug('Recording from microphone')

    # -------------------------------------------------------------------------

    def stop_recording(self, stop_buffer: bool, stop_queue: bool) -> bytes:
        if stop_buffer:
            self.buffer_users = max(0, self.buffer_users - 1)

        if stop_queue:
            self.queue_users = max(0, self.queue_users - 1)

        # Don't stop until all "users" have disconnected
        if self.is_recording and (self.buffer_users <= 0) and (self.queue_users <= 0):
            # Shut down audio system
            self._is_recording = False
            self.mic.stop_stream()
            self.audio.terminate()
            logger.debug('Stopped recording from microphone')

            # Write final empty buffer
            self.queue.put(bytes())

        if stop_buffer:
            # Return WAV data
            with io.BytesIO() as wav_buffer:
                with wave.open(wav_buffer, mode='wb') as wav_file:
                    wav_file.setframerate(16000)
                    wav_file.setsampwidth(2)
                    wav_file.setnchannels(1)
                    wav_file.writeframesraw(self.buffer)

                return wav_buffer.getvalue()

        # Empty buffer
        return bytes()

    # -------------------------------------------------------------------------

    def stop_all(self) -> None:
        if self.is_recording:
            self._is_recording = False
            self.mic.stop_stream()
            self.audio.terminate()

            if self.queue_users > 0:
                # Write final empty buffer
                self.queue.put(bytes())

            self.buffer_users = 0
            self.queue_users = 0

    # -------------------------------------------------------------------------

    def get_queue(self) -> Queue:
        return self.queue

    # -------------------------------------------------------------------------

    def get_microphones(self) -> Dict[Any, Any]:
        import pyaudio

        mics: Dict[Any, Any] = {}
        audio = pyaudio.PyAudio()
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            mics[i] = info['name']

        audio.terminate()

        return mics


# -----------------------------------------------------------------------------
# ARecord based audio recorder
# -----------------------------------------------------------------------------

class ARecordAudioRecorder(AudioRecorder):
    '''Records from microphone using arecord'''

    def __init__(self, core, device=None, chunk_size=480*2):
        # Chunk size is set to 30 ms for webrtcvad
        AudioRecorder.__init__(self, core, device)

        self.record_proc = None
        self.chunk_size = chunk_size

        self.buffer = bytes()
        self.buffer_users = 0

        self.queue = Queue()
        self.queue_users = 0

    # -------------------------------------------------------------------------

    def start_recording(self, start_buffer: bool, start_queue: bool, device: Any=None):
        # Allow multiple "users" to listen for audio data
        if start_buffer:
            self.buffer_users += 1

        if start_queue:
            self.queue_users += 1

        if not self.is_recording:
            # Reset
            self.buffer = bytes()

            # Clear queue
            while not self.queue.empty():
                self.queue.get_nowait()

            # 16-bit 16Khz mono WAV
            arecord_cmd = ['arecord',
                          '-q',
                          '-r', '16000',
                          '-f', 'S16_LE',
                          '-c', '1',
                          '-t', 'raw']

            device_name = device or self.device
            if device_name is not None:
                # Use specific ALSA device
                device_name = str(device_name)
                arecord_cmd.extend(['-D', device_name])

            logger.debug(arecord_cmd)

            def process_data():
                proc = subprocess.Popen(arecord_cmd, stdout=subprocess.PIPE)
                while self.is_recording:
                    # Pull from process STDOUT
                    data = proc.stdout.read(self.chunk_size)

                    if self.buffer_users > 0:
                        self.buffer += data

                    if self.queue_users > 0:
                        self.queue.put(data)

                proc.terminate()

            # Start recording
            self._is_recording = True
            self.record_thread = threading.Thread(target=process_data, daemon=True)
            self.record_thread.start()

            logger.debug('Recording from microphone')

    # -------------------------------------------------------------------------

    def stop_recording(self, stop_buffer: bool, stop_queue: bool) -> bytes:
        if stop_buffer:
            self.buffer_users = max(0, self.buffer_users - 1)

        if stop_queue:
            self.queue_users = max(0, self.queue_users - 1)

        # Only stop if all "users" have disconnected
        if self.is_recording and (self.buffer_users <= 0) and (self.queue_users <= 0):
            # Shut down audio system
            self._is_recording = False
            self.record_thread.join()

            logger.debug('Stopped recording from microphone')

            # Write final empty buffer
            self.queue.put(bytes())

        if stop_buffer:
            # Return WAV data
            with io.BytesIO() as wav_buffer:
                with wave.open(wav_buffer, mode='wb') as wav_file:
                    wav_file.setframerate(16000)
                    wav_file.setsampwidth(2)
                    wav_file.setnchannels(1)
                    wav_file.writeframesraw(self.buffer)

                return wav_buffer.getvalue()

        # Empty buffer
        return bytes()

    # -------------------------------------------------------------------------

    def stop_all(self) -> None:
        if self.is_recording:
            self._is_recording = False
            self.record_thread.join()

            if self.queue_users > 0:
                # Write final empty buffer
                self.queue.put(bytes())

            self.buffer_users = 0
            self.queue_users = 0

    # -------------------------------------------------------------------------

    def get_queue(self) -> Queue:
        return self.queue

    # -------------------------------------------------------------------------

    def get_microphones(self) -> Dict[Any, Any]:
        output = subprocess.check_output(['arecord', '-L'])\
                           .decode().splitlines()

        mics: Dict[Any, Any] = {}
        name, description = None, None

        # Parse output of arecord -L
        for line in output:
            line = line.rstrip()
            if re.match(r'^\s', line):
                description = line.strip()
            else:
                if name is not None:
                    mics[name] = description

                name = line.strip()

        return mics

# -----------------------------------------------------------------------------
# WAV based audio "recorder"
# -----------------------------------------------------------------------------

class WavAudioRecorder(AudioRecorder):
    '''Pushes WAV data out instead of data from a microphone.'''

    def __init__(self,
                 core,
                 wav_path: str,
                 end_of_file_callback: Optional[Callable[[str], None]]=None,
                 chunk_size=480):

        # Chunk size set to 30 ms for webrtcvad
        AudioRecorder.__init__(self, core, device=None)
        self.wav_path = wav_path
        self.chunk_size = chunk_size
        self.end_of_file_callback = end_of_file_callback

        self.buffer = bytes()
        self.buffer_users = 0

        self.queue = Queue()
        self.queue_users = 0

    # -------------------------------------------------------------------------

    def start_recording(self, start_buffer: bool, start_queue: bool, device: Any=None):
        # Allow multiple "users" to listen for audio data
        if start_buffer:
            self.buffer_users += 1

        if start_queue:
            self.queue_users += 1

        if not self.is_recording:
            # Reset
            self.buffer = bytes()

            # Clear queue
            while not self.queue.empty():
                self.queue.get_nowait()

            def process_data():
                with wave.open(self.wav_path, 'rb') as wav_file:
                    rate, width, channels = wav_file.getframerate(), wav_file.getsampwidth(), wav_file.getnchannels()
                    if (rate != 16000) or (width != 2) or (channels != 1):
                        audio_data = SpeechDecoder.convert_wav(wav_file.read())
                    else:
                        # Use original data
                        audio_data = wav_file.readframes(wav_file.getnframes())

                i = 0
                while (i+self.chunk_size) < len(audio_data):
                    data = audio_data[i:i+self.chunk_size]
                    i += self.chunk_size

                    if self.buffer_users > 0:
                        self.buffer += data

                    if self.queue_users > 0:
                        self.queue.put(data)

                if self.end_of_file_callback is not None:
                    self.end_of_file_callback(self.wav_path)

            # Start recording
            self._is_recording = True
            self.record_thread = threading.Thread(target=process_data, daemon=True)
            self.record_thread.start()

            logger.debug('Recording from microphone')

    # -------------------------------------------------------------------------

    def stop_recording(self, stop_buffer: bool, stop_queue: bool) -> bytes:
        if stop_buffer:
            self.buffer_users = max(0, self.buffer_users - 1)

        if stop_queue:
            self.queue_users = max(0, self.queue_users - 1)

        # Only stop if all "users" have disconnected
        if self.is_recording and (self.buffer_users <= 0) and (self.queue_users <= 0):
            # Shut down audio system
            self._is_recording = False
            self.record_thread.join()

            logger.debug('Stopped recording from microphone')

            # Write final empty buffer
            self.queue.put(bytes())

        if stop_buffer:
            # Return WAV data
            with io.BytesIO() as wav_buffer:
                with wave.open(wav_buffer, mode='wb') as wav_file:
                    wav_file.setframerate(16000)
                    wav_file.setsampwidth(2)
                    wav_file.setnchannels(1)
                    wav_file.writeframesraw(self.buffer)

                return wav_buffer.getvalue()

        # Empty buffer
        return bytes()

    # -------------------------------------------------------------------------

    def stop_all(self) -> None:
        if self.is_recording:
            self._is_recording = False
            self.record_thread.join()

            if self.queue_users > 0:
                # Write final empty buffer
                self.queue.put(bytes())

            self.buffer_users = 0
            self.queue_users = 0

    # -------------------------------------------------------------------------

    def get_queue(self) -> Queue:
        return self.queue

# -----------------------------------------------------------------------------
# MQTT based audio "recorder" for Snips.AI Hermes Protocol
# https://docs.snips.ai/ressources/hermes-protocol
# -----------------------------------------------------------------------------

class HermesAudioRecorder(AudioRecorder):
    '''Receives audio data from MQTT via Hermes protocol.'''

    def __init__(self, core, chunk_size=480*2):

        # Chunk size set to 30 ms for webrtcvad
        AudioRecorder.__init__(self, core, device=None)
        self.chunk_size = chunk_size

        self.buffer = bytes()
        self.buffer_users = 0

        self.queue = Queue()
        self.queue_users = 0

    # -------------------------------------------------------------------------

    def start_recording(self, start_buffer: bool, start_queue: bool, device: Any=None):
        # Allow multiple "users" to listen for audio data
        if start_buffer:
            self.buffer_users += 1

        if start_queue:
            self.queue_users += 1

        if not self.is_recording:
            # Reset
            self.buffer = bytes()

            # Clear queue
            while not self.queue.empty():
                self.queue.get_nowait()

            def process_data():
                with wave.open(self.wav_path, 'rb') as wav_file:
                    rate, width, channels = wav_file.getframerate(), wav_file.getsampwidth(), wav_file.getnchannels()
                    if (rate != 16000) or (width != 2) or (channels != 1):
                        audio_data = SpeechDecoder.convert_wav(wav_file.read())
                    else:
                        # Use original data
                        audio_data = wav_file.readframes(wav_file.getnframes())

                i = 0
                while (i+self.chunk_size) < len(audio_data):
                    data = audio_data[i:i+self.chunk_size]
                    i += self.chunk_size

                    if self.buffer_users > 0:
                        self.buffer += data

                    if self.queue_users > 0:
                        self.queue.put(data)

                if self.end_of_file_callback is not None:
                    self.end_of_file_callback(self.wav_path)

            # Start recording
            self._is_recording = True
            self.record_thread = threading.Thread(target=process_data, daemon=True)
            self.record_thread.start()

            logger.debug('Recording from microphone')

    # -------------------------------------------------------------------------

    def stop_recording(self, stop_buffer: bool, stop_queue: bool) -> bytes:
        if stop_buffer:
            self.buffer_users = max(0, self.buffer_users - 1)

        if stop_queue:
            self.queue_users = max(0, self.queue_users - 1)

        # Only stop if all "users" have disconnected
        if self.is_recording and (self.buffer_users <= 0) and (self.queue_users <= 0):
            # Shut down audio system
            self._is_recording = False
            self.record_thread.join()

            logger.debug('Stopped recording from microphone')

            # Write final empty buffer
            self.queue.put(bytes())

        if stop_buffer:
            # Return WAV data
            with io.BytesIO() as wav_buffer:
                with wave.open(wav_buffer, mode='wb') as wav_file:
                    wav_file.setframerate(16000)
                    wav_file.setsampwidth(2)
                    wav_file.setnchannels(1)
                    wav_file.writeframesraw(self.buffer)

                return wav_buffer.getvalue()

        # Empty buffer
        return bytes()

    # -------------------------------------------------------------------------

    def stop_all(self) -> None:
        if self.is_recording:
            self._is_recording = False
            self.record_thread.join()

            if self.queue_users > 0:
                # Write final empty buffer
                self.queue.put(bytes())

            self.buffer_users = 0
            self.queue_users = 0

    # -------------------------------------------------------------------------

    def get_queue(self) -> Queue:
        return self.queue
