import os
import io
import time
import wave
import logging
import tempfile
import subprocess
from urllib.parse import urljoin
from typing import Any, Optional

from thespian.actors import ActorAddress

from .actor import RhasspyActor
from .profiles import Profile
from .utils import convert_wav

# -----------------------------------------------------------------------------

class TranscribeWav:
    def __init__(self,
                 wav_data: bytes,
                 receiver:Optional[ActorAddress]=None,
                 handle:bool=True) -> None:
        self.wav_data = wav_data
        self.receiver = receiver
        self.handle = handle

class WavTranscription:
    def __init__(self, text: str, handle:bool=True) -> None:
        self.text = text
        self.handle = handle

# -----------------------------------------------------------------------------

class DummyDecoder(RhasspyActor):
    '''Always returns an emptry transcription'''
    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, TranscribeWav):
            self.send(message.receiver or sender,
                      WavTranscription(''))

# -----------------------------------------------------------------------------
# Pocketsphinx based WAV to text decoder
# https://github.com/cmusphinx/pocketsphinx
# -----------------------------------------------------------------------------

class PocketsphinxDecoder(RhasspyActor):
    '''Pocketsphinx based WAV to text decoder.'''
    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.decoder = None

    def to_started(self, from_state:str) -> None:
        self.preload = self.config.get('preload', False)
        if self.preload:
            self.load_decoder()

        self.transition('loaded')

    def in_loaded(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, TranscribeWav):
            self.load_decoder()
            text = self.transcribe_wav(message.wav_data)
            self.send(message.receiver or sender,
                      WavTranscription(text, handle=message.handle))

    # -------------------------------------------------------------------------

    def load_decoder(self) -> None:
        if self.decoder is None:
            # Load decoder
            import pocketsphinx
            ps_config = self.profile.get('speech_to_text.pocketsphinx')

            # Load decoder settings
            hmm_path = self.profile.read_path(ps_config['acoustic_model'])
            dict_path = self.profile.read_path(ps_config['dictionary'])
            lm_path = self.profile.read_path(ps_config['language_model'])

            self._logger.info('Loading decoder with hmm=%s, dict=%s, lm=%s' % (hmm_path, dict_path, lm_path))

            decoder_config = pocketsphinx.Decoder.default_config()
            decoder_config.set_string('-hmm', hmm_path)
            decoder_config.set_string('-dict', dict_path)
            decoder_config.set_string('-lm', lm_path)
            decoder_config.set_string('-logfn', '/dev/null')

            mllr_path = self.profile.read_path(ps_config['mllr_matrix'])
            if os.path.exists(mllr_path):
                self._logger.debug('Using tuned MLLR matrix for acoustic model: %s' % mllr_path)
                decoder_config.set_string('-mllr', mllr_path)

            self.decoder = pocketsphinx.Decoder(decoder_config)

    def transcribe_wav(self, wav_data: bytes) -> str:
        # Ensure 16-bit 16Khz mono
        assert self.decoder is not None
        data_size = len(wav_data)
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, 'rb') as wav_file:
                rate, width, channels = wav_file.getframerate(), wav_file.getsampwidth(), wav_file.getnchannels()
                self._logger.debug('rate=%s, width=%s, channels=%s.' % (rate, width, channels))

                if (rate != 16000) or (width != 2) or (channels != 1):
                    self._logger.info('Need to convert to 16-bit 16Khz mono.')
                    # Use converted data
                    audio_data = convert_wav(wav_data)
                else:
                    # Use original data
                    audio_data = wav_file.readframes(wav_file.getnframes())

        # Process data as an entire utterance
        start_time = time.time()
        self.decoder.start_utt()
        self.decoder.process_raw(audio_data, False, True)
        self.decoder.end_utt()
        end_time = time.time()

        self._logger.debug('Decoded WAV in %s second(s)' % (end_time - start_time))

        if self.decoder.hyp() is not None:
            # Return best transcription
            return self.decoder.hyp().hypstr

        # No transcription
        return ''

# -----------------------------------------------------------------------------
# HTTP based decoder on remote Rhasspy server
# -----------------------------------------------------------------------------

class RemoteDecoder(RhasspyActor):
    '''Forwards speech to text request to a rmemote Rhasspy server'''
    def to_started(self, from_state:str) -> None:
        self.remote_url = self.profile.get('speech_to_text.remote.url')

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, TranscribeWav):
            text = self.transcribe_wav(message.wav_data)
            self.send(message.receiver or sender,
                      WavTranscription(text))

    def transcribe_wav(self, wav_data: bytes) -> str:
        import requests

        headers = { 'Content-Type': 'audio/wav' }
        self._logger.debug('POSTing %d byte(s) of WAV data to %s' % (len(wav_data), self.remote_url))
        # Pass profile name through
        params = { 'profile': self.profile.name }
        response = requests.post(self.remote_url, headers=headers,
                                 data=wav_data, params=params)

        try:
            response.raise_for_status()
        except Exception as e:
            self._logger.exception('transcribe_wav')
            return ''

        return response.text

# -----------------------------------------------------------------------------
# Command Decoder
# -----------------------------------------------------------------------------

class CommandDecoder(RhasspyActor):
    '''Command-line based decoder'''
    def to_started(self, from_state:str) -> None:
        program = os.path.expandvars(self.profile.get('speech_to_text.command.program'))
        arguments = [os.path.expandvars(str(a))
                     for a in self.profile.get('speech_to_text.command.arguments', [])]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, TranscribeWav):
            text = self.transcribe_wav(message.wav_data)
            self.send(message.receiver or sender,
                      WavTranscription(text))

    def transcribe_wav(self, wav_data: bytes) -> str:
        try:
            self._logger.debug(self.command)

            # WAV -> STDIN -> STDOUT -> text
            return subprocess.check_output(
                self.command, input=wav_data).decode().strip()

        except Exception as e:
            self._logger.exception('transcribe_wav')
            return ''
