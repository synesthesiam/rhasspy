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
from typing import Dict, Any

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class AudioRecorder:
    '''Base class for microphone audio recorders'''
    def __init__(self, device=None):
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
    def __init__(self, device=None):
        AudioRecorder.__init__(self, device)
        self.audio = None
        self.mic = None

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
                                       frames_per_buffer=480)

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

    def __init__(self, device=None):
        AudioRecorder.__init__(self, device)

        self.record_proc = None

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
                          '-t', 'wav']

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
                    data = proc.stdout.read(480 * 2)  # 30 ms for webrtcvad

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
