import os
import io
import time
import wave
import logging

import pocketsphinx

from utils import convert_wav

def transcribe_wav(profile, wav_data, decoder=None):
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

    # Load decoder
    decoder = maybe_load_decoder(profile, decoder)

    # Process data as an entire utterance
    decode_start_time = time.time()
    decoder.start_utt()
    decoder.process_raw(wav_data, False, True)
    decoder.end_utt()
    end_time = time.time()

    return decoder

def maybe_load_decoder(profile, decoder=None):
    if decoder is None:
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
