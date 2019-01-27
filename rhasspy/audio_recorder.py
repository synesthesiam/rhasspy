#!/usr/bin/env python3
import os
import logging
import subprocess
import threading
import time
import wave
import io
import re
import audioop
from queue import Queue
from typing import Dict, Any, Callable, Optional
from collections import defaultdict

from .actor import RhasspyActor

# -----------------------------------------------------------------------------

class AudioData:
    def __init__(self, data: bytes):
        self.data = data

class StartStreaming:
    def __init__(self, receiver):
        self.receiver = receiver

class StopStreaming:
    def __init__(self, receiver):
        self.receiver = receiver

class StartRecordingToBuffer:
    def __init__(self, buffer_name):
        self.buffer_name = buffer_name

class StopRecordingToBuffer:
    def __init__(self, buffer_name, receiver=None):
        self.buffer_name = buffer_name
        self.receiver = receiver

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

    def test_microphones(self, chunk_size:int) -> Dict[Any, Any]:
        '''Listen to each microphone and return a relevant description'''
        return {}

    @property
    def is_recording(self):
        '''True if currently recording from microphone.'''
        return self._is_recording

# -----------------------------------------------------------------------------
# PyAudio based audio recorder
# https://people.csail.mit.edu/hubert/pyaudio/
# -----------------------------------------------------------------------------

class PyAudioRecorder(RhasspyActor):
    '''Records from microphone using pyaudio'''
    def __init__(self):
        RhasspyActor.__init__(self)
        self.mic = None
        self.audio = None
        self.receivers = []
        self.buffers = defaultdict(bytes)

    def to_started(self, from_state):
        self.device_index = self.config.get('device') \
            or self.profile.get('microphone.pyaudio.device')

        if self.device_index is not None:
            self.device_index = int(self.device_index)
            if self.device_index < -1:
                # Default device
                self.device_index = None

        self.frames_per_buffer = int(self.profile.get(
            'microphone.pyaudio.frames_per_buffer', 480))

    def in_started(self, message, sender):
        if isinstance(message, StartStreaming):
            self.receivers.append(message.receiver)
            self.transition('recording')
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
            self.transition('recording')

    def to_recording(self, from_state):
        import pyaudio

        # Start audio system
        def stream_callback(data, frame_count, time_info, status):
            # Send to this actor to avoid threading issues
            self.send(self.myAddress, AudioData(data))
            return (data, pyaudio.paContinue)

        self.audio = pyaudio.PyAudio()
        data_format = self.audio.get_format_from_width(2)  # 16-bit
        self.mic = self.audio.open(format=data_format,
                                    channels=1,
                                    rate=16000,
                                    input_device_index=self.device_index,
                                    input=True,
                                    stream_callback=stream_callback,
                                    frames_per_buffer=self.frames_per_buffer)

        self.mic.start_stream()
        logger.debug('Recording from microphone (PyAudio)')

    # -------------------------------------------------------------------------

    def in_recording(self, message, sender):
        if isinstance(message, AudioData):
            # Forward to subscribers
            for receiver in self.receivers:
                self.send(receiver, message)

            # Append to buffers
            for receiver in self.buffers:
                self.buffers[receiver] += message.data
        elif isinstance(message, StartStreaming):
            self.receivers.append(message.receiver)
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
        elif isinstance(message, StopStreaming):
            if message.receiver is None:
                # Clear all receivers
                self.receivers.clear()
            else:
                self.receivers.remove(message.receiver)
        elif isinstance(message, StopRecordingToBuffer):
            if message.buffer_name is None:
                # Clear all buffers
                self.buffers.clear()
            else:
                # Respond with buffer
                buffer = self.buffers.pop(message.buffer_name, bytes())
                self.send(message.receiver or sender, AudioData(buffer))

        # Check to see if anyone is still listening
        if (len(self.receivers) == 0) and (len(self.buffers) == 0):
            # Terminate audio recording
            self.mic.stop_stream()
            self.audio.terminate()
            self.transition('started')
            logger.debug('Stopped recording from microphone (PyAudio)')

    def to_stopped(self, from_state):
        if self.mic is not None:
            self.mic.stop_stream()
            self.mic = None
            logger.debug('Stopped recording from microphone (PyAudio)')

        if self.audio is not None:
            self.audio.terminate()
            self.audio = None

    # -------------------------------------------------------------------------

    @classmethod
    def get_microphones(self) -> Dict[Any, Any]:
        import pyaudio

        mics: Dict[Any, Any] = {}
        audio = pyaudio.PyAudio()
        default_name = audio.get_default_input_device_info().get('name')
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            mics[i] = info['name']

            if mics[i] == default_name:
                mics[i] = mics[i] + '*'

        audio.terminate()

        return mics

    # -------------------------------------------------------------------------

    @classmethod
    def test_microphones(self, chunk_size:int) -> Dict[Any, Any]:
        import pyaudio

        # Thanks to the speech_recognition library!
        # https://github.com/Uberi/speech_recognition/blob/master/speech_recognition/__init__.py
        result = {}
        audio = pyaudio.PyAudio()
        try:
            default_name = audio.get_default_input_device_info().get('name')
            for device_index in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(device_index)
                device_name = device_info.get("name")
                if device_name == default_name:
                    device_name = device_name + '*'

                try:
                    # read audio
                    data_format = audio.get_format_from_width(2)  # 16-bit
                    pyaudio_stream = audio.open(
                        input_device_index=device_index,
                        channels=1,
                        format=pyaudio.paInt16,
                        rate=16000,
                        input=True)
                    try:
                        buffer = pyaudio_stream.read(chunk_size)
                        if not pyaudio_stream.is_stopped():
                            pyaudio_stream.stop_stream()
                    finally:
                        pyaudio_stream.close()
                except:
                    result[device_index] = '%s (error)' % device_name
                    continue

                # compute RMS of debiased audio
                energy = -audioop.rms(buffer, 2)
                energy_bytes = bytes([energy & 0xFF, (energy >> 8) & 0xFF])
                debiased_energy = audioop.rms(
                    audioop.add(buffer, energy_bytes * (len(buffer) // 2), 2), 2)

                if debiased_energy > 30:  # probably actually audio
                    result[device_index] = '%s (working!)' % device_name
                else:
                    result[device_index] = '%s (no sound)' % device_name
        finally:
            audio.terminate()

        return result

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

            logger.debug('Recording from microphone (arecord)')

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
        first_mic = True
        for line in output:
            line = line.rstrip()
            if re.match(r'^\s', line):
                description = line.strip()
                if first_mic:
                    description = description + '*'
                    first_mic = False
            else:
                if name is not None:
                    mics[name] = description

                name = line.strip()

        return mics

    # -------------------------------------------------------------------------

    def test_microphones(self, chunk_size:int) -> Dict[Any, Any]:
        # Thanks to the speech_recognition library!
        # https://github.com/Uberi/speech_recognition/blob/master/speech_recognition/__init__.py
        mics = self.get_microphones()
        result = {}
        for device_id, device_name in mics.items():
            try:
                # read audio
                arecord_cmd = ['arecord',
                              '-q',
                              '-D', device_id,
                              '-r', '16000',
                              '-f', 'S16_LE',
                              '-c', '1',
                              '-t', 'raw']

                proc = subprocess.Popen(arecord_cmd, stdout=subprocess.PIPE)
                buffer = proc.stdout.read(chunk_size * 2)
                proc.terminate()
            except:
                result[device_id] = '%s (error)' % device_name
                continue

            # compute RMS of debiased audio
            energy = -audioop.rms(buffer, 2)
            energy_bytes = bytes([energy & 0xFF, (energy >> 8) & 0xFF])
            debiased_energy = audioop.rms(
                audioop.add(buffer, energy_bytes * (len(buffer) // 2), 2), 2)

            if debiased_energy > 30:  # probably actually audio
                result[device_id] = '%s (working!)' % device_name
            else:
                result[device_id] = '%s (no sound)' % device_name

        return result

# -----------------------------------------------------------------------------
# WAV based audio "recorder"
# -----------------------------------------------------------------------------

class WavAudioRecorder(AudioRecorder):
    '''Pushes WAV data out instead of data from a microphone.'''

    def __init__(self,
                 core,
                 wav_path: str,
                 end_of_file_callback: Optional[Callable[[str], None]]=None,
                 chunk_size:int=480) -> None:

        # Chunk size set to 30 ms for webrtcvad
        AudioRecorder.__init__(self, core, device=None)
        self.wav_path = wav_path
        self.chunk_size = chunk_size
        self.end_of_file_callback = end_of_file_callback

        self.buffer = bytes()
        self.buffer_users = 0

        self.queue:Queue = Queue()
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

            logger.debug('Reading from WAV file')

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

            logger.debug('Stopped reading from WAV file')

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

        self.chunk = bytes()

        self.buffer = bytes()
        self.buffer_users = 0

        self.queue = Queue()
        self.queue_users = 0

    # -------------------------------------------------------------------------

    def on_audio_frame(self, audio_data):
        if not self.is_recording:
            return

        # Accumulate in a chunk
        self.chunk += audio_data

        while len(self.chunk) >= self.chunk_size:
            # Pull out a chunk
            data = self.chunk[:self.chunk_size]
            self.chunk = self.chunk[self.chunk_size:]

            # Distribute
            if self.buffer_users > 0:
                self.buffer += data

            if self.queue_users > 0:
                self.queue.put(data)

    # -------------------------------------------------------------------------

    def start_recording(self, start_buffer: bool, start_queue: bool, device: Any=None):
        # Allow multiple "users" to listen for audio data
        if start_buffer:
            self.buffer_users += 1

        if start_queue:
            self.queue_users += 1

        if not self.is_recording:
            # Reset
            self.chunk = bytes()
            self.buffer = bytes()

            # Clear queue
            while not self.queue.empty():
                self.queue.get_nowait()

            # Set callback
            self.core.get_mqtt_client().on_audio_frame = self.on_audio_frame

            # Start recording
            self._is_recording = True

            logger.debug('Listening for audio frames')

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

            # Remove callback
            self.core.get_mqtt_client().on_audio_frame = None

            logger.debug('Stopped listening for audio frames')

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
            self.core.get_mqtt_client().on_audio_frame = None

            if self.queue_users > 0:
                # Write final empty buffer
                self.queue.put(bytes())

            self.buffer_users = 0
            self.queue_users = 0

    # -------------------------------------------------------------------------

    def get_queue(self) -> Queue:
        return self.queue
