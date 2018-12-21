import os
import io
import time
import wave
import logging
import tempfile
import subprocess
from urllib.parse import urljoin

import requests
import pocketsphinx
from thespian import Actor

from profile import Profile

# -----------------------------------------------------------------------------

class TranscribeWav:
    def __init__(self, wav_data):
        self.wav_data = wav_data

class LoadDecoder:
    pass

# -----------------------------------------------------------------------------

class DecoderActor(Actor):
    def __init__(self):
        self.profile = None
        self.decoder = None

    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, str):
                # Load profile
                profile_name = message
                self.profile = Profile(profile_name)
                self.system = self.profile.speech_to_text.get('system', 'pocketsphinx')
            elif isinstance(message, LoadDecoder):
                # Pre-load decoder
                if self.system == 'pocketsphinx':
                    self.maybe_load_decoder()
            elif isinstance(message, TranscribeWav):
                # WAV -> text
                if self.system == 'remote':
                    # Use remote server
                    text = self.transcribe_remote(message.wav_data)
                    self.send(sender, text)
                elif self.system == 'pocketsphinx':
                    # Use pocketsphinx locally
                    self.maybe_load_decoder()
                    text = self.transcribe_wav(wav_data)
                    self.send(sender, text)
                else:
                    logging.warning('Invalid speech to text system: %s' % self.system)
                    return ''
        except Exception as ex:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def transcribe_remote(self, wav_data):
        remote_url = self.profile.speech_to_text[self.system]['url']
        headers = { 'Content-Type': 'audio/wav' }
        logging.debug('POSTing %d byte(s) of WAV data to %s' % (len(wav_data), remote_url))
        # Pass profile name through
        params = { 'profile': self.profile.name }
        response = requests.post(remote_url, headers=headers,
                                 data=wav_data, params=params)

        response.raise_for_status()
        return response.text

    # -------------------------------------------------------------------------

    def transcribe_wav(self, wav_data):
        request_start_time = time.time()

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

        # Process data as an entire utterance
        start_time = time.time()
        self.decoder.start_utt()
        self.decoder.process_raw(wav_data, False, True)
        self.decoder.end_utt()
        end_time = time.time()

        logging.debug('Decoded WAV in %s second(s)' % (end_time - start_time))

        if self.decoder.hyp() is not None:
            # Return best transcription
            return self.decoder.hyp().hypstr

        # No transcription
        return ''

    # -------------------------------------------------------------------------

    def maybe_load_decoder(self):
        if self.decoder is None:
            ps_config = self.profile.speech_to_text['pocketsphinx']

            # Load decoder settings
            hmm_path = self.profile.read_path(ps_config['acoustic_model'])
            dict_path = self.profile.read_path(ps_config['dictionary'])
            lm_path = self.profile.read_path(ps_config['language_model'])

            logging.info('Loading decoder with hmm=%s, dict=%s, lm=%s' % (hmm_path, dict_path, lm_path))

            decoder_config = pocketsphinx.Decoder.default_config()
            decoder_config.set_string('-hmm', hmm_path)
            decoder_config.set_string('-dict', dict_path)
            decoder_config.set_string('-lm', lm_path)

            self.decoder = pocketsphinx.Decoder(decoder_config)

# -----------------------------------------------------------------------------

def convert_wav(data):
    # Convert a WAV to 16-bit, 16Khz mono
    with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+', delete=False) as out_wav_file:
        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb', delete=False) as in_wav_file:
            in_wav_file.write(data)
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

            # Needed on Windows
            try:
                in_wav_file.close()
                os.unlink(in_wav_file.name)
            except:
                pass

        # Needed on Windows
        try:
            out_wav_file.close()
            os.unlink(out_wav_file.name)
        except:
            pass
