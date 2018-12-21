#!/usr/bin/env python3
import os
import logging
import subprocess
import threading
import time
import wave
import io

logging.basicConfig(level=logging.DEBUG)

from thespian.actors import Actor, ActorSystem

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
