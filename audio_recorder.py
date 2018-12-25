#!/usr/bin/env python3
import os
import logging
import subprocess
import threading
import time
import wave
import io

from thespian.actors import Actor, ActorSystem

# -----------------------------------------------------------------------------

class AudioRecorder:
    def start_recording(self):
        pass

    def stop_recording(self):
        return []

    def get_microphones(self):
        return {}

# -----------------------------------------------------------------------------

class PyAudioRecorder(AudioRecorder):
    def __init__(self):
        self.audio = None
        self.mic = None
        self.buffer = None

    def start_recording(self, device_index=None):
        import pyaudio

        def stream_callback(data, frame_count, time_info, status):
            if self.buffer is None:
                self.buffer = data
            else:
                self.buffer += data

            return (data, pyaudio.paContinue)

        self.audio = pyaudio.PyAudio()
        data_format = self.audio.get_format_from_width(2)  # 16-bit
        self.mic = self.audio.open(format=data_format,
                                   channels=1,
                                   rate=16000,
                                   input_device_index=device_index,
                                   input=True,
                                   stream_callback=stream_callback)

        self.mic.start_stream()

    def stop_recording(self):
        self.mic.stop_stream()
        self.audio.terminate()

        return self.buffer

    def get_microphones(self):
        import pyaudio

        mics = {}
        audio = pyaudio.PyAudio()
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            mics[i] = info['name']

        audio.terminate()

        return mics

# -----------------------------------------------------------------------------

class ARecordAudioRecorder(AudioRecorder):
    def start_recording(self):
        self.record_file = tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+')
        self.record_proc = subprocess.Popen(['arecord',
                                             '-r', '16000',
                                             '-f', 'S16_LE',
                                             '-c', '1',
                                             '-t', 'wav',
                                             self.record_file.name],
                                            close_fds=True)

    def stop_recording(self):
        self.record_proc.terminate()
        self.record_file.seek(0)
        data = open(self.record_file.name, 'rb').read()
        try:
            os.unlink(self.record_file.name)
        except:
            pass

        return data

    def get_microphones(self):
        output = subprocess.check_output(['arecord', '-L'])\
                           .decode().splitlines()

        mics = {}
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
# Events
# -----------------------------------------------------------------------------

class RecordingSettings:
    def __init__(self, rate, width, channels, buffer_size):
        self.rate = rate
        self.width = width
        self.channels = channels
        self.buffer_size = buffer_size

class StartRecording:
    pass

class StopRecording:
    pass

class StartStreaming:
    pass

class StopStreaming:
    pass

class AudioData:
    def __init__(self, data, settings):
        self.data = data
        self.settings = settings

    def to_wav(self):
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, mode='wb') as wav_file:
                wav_file.setframerate(self.settings.rate)
                wav_file.setsampwidth(self.settings.width)
                wav_file.setnchannels(self.settings.channels)
                wav_file.writeframesraw(self.data)

            return wav_buffer.getvalue()

# -----------------------------------------------------------------------------
# arecord Based Actor
# -----------------------------------------------------------------------------

class ARecordActor(Actor):
    FORMATS = { 8: 'S8', 16: 'S16_LE', 24: 'S24_LE', 32: 'S32_LE' }

    def __init__(self):
        # Defaults to 16-bit 16Khz mono
        self.settings = RecordingSettings(16000, 2, 1, 2048)

        self.proc = None
        self.thread = None
        self.subscribers = []
        self.record_buffer = None

    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, RecordingSettings):
                self.settings = message
            elif isinstance(message, StartStreaming):
                # Start streaming audio data to an actor
                self.subscribers.append(sender)
                self.maybe_start_proc()
            elif isinstance(message, StopStreaming):
                # Stop streaming
                self.subscribers.remove(sender)
                self.maybe_stop_proc()
            elif isinstance(message, StartRecording):
                # Start recording audio data to a buffer
                self.record_buffer = bytes()
                self.maybe_start_proc()
            elif isinstance(message, StopRecording):
                # Stop recording (return data)
                self.send(sender, AudioData(self.record_buffer, self.settings))
                self.record_buffer = None
                self.maybe_stop_proc()
        except Exception as e:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def maybe_start_proc(self):
        if self.proc is None:
            bits = self.settings.width * 8
            record_format = ARecordActor.FORMATS.get(bits, 'S16_LE')
            self.proc = subprocess.Popen([
                'arecord',
                '-q',
                '-f', str(record_format),
                '-r', str(self.settings.rate),
                '-c', str(self.settings.channels),
                '-t', 'raw'
            ],
            stdout=subprocess.PIPE)

            self.thread = threading.Thread(target=self.read_data, daemon=True)
            self.thread.start()

    def read_data(self):
        try:
            while self.proc is not None:
                data = self.proc.stdout.read(self.settings.buffer_size)

                # Add to recording buffer
                if self.record_buffer is not None:
                    self.record_buffer += data

                # Forward to subscribers
                if len(self.subscribers) > 0:
                    msg = AudioData(data, self.settings)
                    for actor in self.subscribers:
                        self.send(actor, msg)
        except Exception as e:
            logging.exception('read_data')

    # -------------------------------------------------------------------------

    def maybe_stop_proc(self):
        if self.proc is not None:
            if (len(self.subscribers) == 0) and (self.record_buffer is None):
                try:
                    self.proc.terminate()
                except:
                    try:
                        self.proc.kill()
                    except:
                        pass
                finally:
                    self.proc = None

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    # Start actor system
    system = ActorSystem('multiprocQueueBase')

    try:
        actor = system.createActor(ARecordActor)

        system.tell(actor, StartRecording())
        time.sleep(2)
        audio_data = system.ask(actor, StopRecording())
        print(len(audio_data.data))

        with open('test.wav', 'wb') as wav_file:
            wav_file.write(audio_data.to_wav())

    finally:
        # Shut down actor system
        system.shutdown()
