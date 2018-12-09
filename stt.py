import os
import io
import time
import wave
import logging
from urllib.parse import urljoin

import requests

import pocketsphinx

from utils import convert_wav

def transcribe_wav(profile, wav_data, decoder=None):
    request_start_time = time.time()
    system = profile.speech_to_text['system']

    if system == 'remote':
        remote_url = profile.speech_to_text[system]['url']
        headers = { 'Content-Type': 'audio/wav' }
        logging.debug('POSTing %d byte(s) of WAV data to %s' % (len(wav_data), remote_url))
        # Pass profile name through
        params = { 'profile': profile.name }
        response = requests.post(remote_url, headers=headers,
                                 data=wav_data, params=params)

        response.raise_for_status()

        # Return fake decoder with remote transcription
        decoder = RemoteDecoder(response.text)
    else:
        # Ensure 16-bit 16Khz mono
        data_size = len(wav_data)
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, 'rb') as wav_file:
                rate, width, channels = wav_file.getframerate(), wav_file.getsampwidth(), wav_file.getnchannels()
                logging.debug('rate=%s, width=%s, channels=%s.' % (rate, width, channels))

                if (rate != 16000) or (width != 2) or (channels != 1):
                    logging.info('Need to convert to 16-bit 16Khz mono.')
                    # Use converted data
                    wav_data = convert_wav(wav_data)
                else:
                    # Use original data
                    wav_data = wav_file.readframes(wav_file.getnframes())

        # Load pocketsphinx decoder
        decoder = maybe_load_decoder(profile, decoder)

        # Process data as an entire utterance
        decode_start_time = time.time()
        decoder.start_utt()
        decoder.process_raw(wav_data, False, True)
        decoder.end_utt()
        end_time = time.time()

    return decoder

def maybe_load_decoder(profile, decoder=None):
    if (decoder is None) or isinstance(decoder, RemoteDecoder):
        ps_config = profile.speech_to_text['pocketsphinx']

        # Load decoder settings
        hmm_path = profile.read_path(ps_config['acoustic_model'])
        dict_path = profile.read_path(ps_config['dictionary'])
        lm_path = profile.read_path(ps_config['language_model'])

        logging.info('Loading decoder with hmm=%s, dict=%s, lm=%s' % (hmm_path, dict_path, lm_path))

        decoder_config = pocketsphinx.Decoder.default_config()
        decoder_config.set_string('-hmm', hmm_path)
        decoder_config.set_string('-dict', dict_path)
        decoder_config.set_string('-lm', lm_path)

        decoder = pocketsphinx.Decoder(decoder_config)

    return decoder

# -----------------------------------------------------------------------------

class RemoteDecoder:
    def __init__(self, text):
        self._hyp = RemoteHyp(text)

    def hyp(self):
        return self._hyp

class RemoteHyp:
    def __init__(self, hypstr):
        self.hypstr = hypstr
