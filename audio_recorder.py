import os
import re
import subprocess
import tempfile

class AudioRecorder:
    def start_recording(self, profile):
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
    def start_recording(self, profile):
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
