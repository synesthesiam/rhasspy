import os
import io
import time
import wave
import logging
import tempfile
import subprocess
from urllib.parse import urljoin

from .actor import RhasspyActor
from .profiles import Profile

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class SpeechDecoder:
    '''Base class for WAV to text speech transcribers.'''

    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def preload(self):
        '''Cache important stuff upfront.'''
        pass

    def transcribe_wav(self, wav_data: bytes) -> str:
        '''Transcribes WAV audio data to text string.
        The hard part.'''
        pass

    @classmethod
    def convert_wav(cls, wav_data: bytes) -> bytes:
        '''Converts WAV data to 16-bit, 16Khz mono with sox.'''
        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as out_wav_file:
            with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb') as in_wav_file:
                in_wav_file.write(wav_data)
                in_wav_file.seek(0)
                subprocess.check_call(['sox',
                                        in_wav_file.name,
                                        '-r', '16000',
                                        '-e', 'signed-integer',
                                        '-b', '16',
                                        '-c', '1',
                                        out_wav_file.name])

                out_wav_file.seek(0)

                # Return converted data
                with wave.open(out_wav_file.name, 'rb') as wav_file:
                    return wav_file.readframes(wav_file.getnframes())

# -----------------------------------------------------------------------------
# Pocketsphinx based WAV to text decoder
# https://github.com/cmusphinx/pocketsphinx
# -----------------------------------------------------------------------------

class TranscribeWav:
    def __init__(self, wav_data: bytes, receiver = None):
        self.wav_data = wav_data
        self.receiver = receiver

class WavTranscription:
    def __init__(self, text: str):
        self.text = text

class PocketsphinxDecoder(RhasspyActor):
    '''Pocketsphinx based WAV to text decoder.'''
    def __init__(self):
        RhasspyActor.__init__(self)
        self.decoder = None

    def to_started(self, from_state):
        self.load_decoder()
        self.transition('loaded')

    def in_loaded(self, message, sender):
        if isinstance(message, TranscribeWav):
            text = self.transcribe_wav(message.wav_data)
            self.send(message.receiver or sender,
                      WavTranscription(text))

    # -------------------------------------------------------------------------

    def load_decoder(self):
        # Load decoder
        import pocketsphinx
        ps_config = self.profile.get('speech_to_text.pocketsphinx')

        # Load decoder settings
        hmm_path = self.profile.read_path(ps_config['acoustic_model'])
        dict_path = self.profile.read_path(ps_config['dictionary'])
        lm_path = self.profile.read_path(ps_config['language_model'])

        logger.info('Loading decoder with hmm=%s, dict=%s, lm=%s' % (hmm_path, dict_path, lm_path))

        decoder_config = pocketsphinx.Decoder.default_config()
        decoder_config.set_string('-hmm', hmm_path)
        decoder_config.set_string('-dict', dict_path)
        decoder_config.set_string('-lm', lm_path)
        decoder_config.set_string('-logfn', '/dev/null')

        mllr_path = self.profile.read_path(ps_config['mllr_matrix'])
        if os.path.exists(mllr_path):
            logger.debug('Using tuned MLLR matrix for acoustic model: %s' % mllr_path)
            decoder_config.set_string('-mllr', mllr_path)

        self.decoder = pocketsphinx.Decoder(decoder_config)

    def transcribe_wav(self, wav_data: bytes) -> str:
        # Ensure 16-bit 16Khz mono
        data_size = len(wav_data)
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, 'rb') as wav_file:
                rate, width, channels = wav_file.getframerate(), wav_file.getsampwidth(), wav_file.getnchannels()
                logger.debug('rate=%s, width=%s, channels=%s.' % (rate, width, channels))

                if (rate != 16000) or (width != 2) or (channels != 1):
                    logger.info('Need to convert to 16-bit 16Khz mono.')
                    # Use converted data
                    audio_data = SpeechDecoder.convert_wav(wav_data)
                else:
                    # Use original data
                    audio_data = wav_file.readframes(wav_file.getnframes())

        # Process data as an entire utterance
        start_time = time.time()
        self.decoder.start_utt()
        self.decoder.process_raw(audio_data, False, True)
        self.decoder.end_utt()
        end_time = time.time()

        logger.debug('Decoded WAV in %s second(s)' % (end_time - start_time))

        if self.decoder.hyp() is not None:
            # Return best transcription
            return self.decoder.hyp().hypstr

        # No transcription
        return ''

# -----------------------------------------------------------------------------
# HTTP based decoder on remote rhasspy server
# -----------------------------------------------------------------------------

class RemoteDecoder(SpeechDecoder):

    def transcribe_wav(self, wav_data: bytes) -> str:
        import requests

        remote_url = self.profile.get('speech_to_text.remote.url')
        headers = { 'Content-Type': 'audio/wav' }
        logger.debug('POSTing %d byte(s) of WAV data to %s' % (len(wav_data), remote_url))
        # Pass profile name through
        params = { 'profile': self.profile.name }
        response = requests.post(remote_url, headers=headers,
                                 data=wav_data, params=params)

        response.raise_for_status()
        return response.text
