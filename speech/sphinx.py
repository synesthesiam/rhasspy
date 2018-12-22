#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import io
import json
import wave
import subprocess
import time
import logging
import tempfile

from thespian.actors import Actor

from profiles import Profile
from events import TranscribeWav, WavTranscription

# -----------------------------------------------------------------------------
# Pocketsphinx Speech to Text Decoder
# https://github.com/cmusphinx/pocketsphinx
# -----------------------------------------------------------------------------

class PocketsphinxSpeechActor(Actor):
    def __init__(self):
        self.profile = None
        self.decoder = None

    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, Profile):
                self.profile = profile
            elif isinstance(message, TranscribeWav):
                self.maybe_load_decoder()
                audio_data = self.maybe_convert_wav(message.wav_data)
                text = self.transcribe(audio_data)
                self.send(sender, WavTranscription(text))
        except Exception as e:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def maybe_load_decoder(self):
        assert self.profile is not None, 'No profile'

        if self.decoder is None:
            import pocketsphinx
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
            decoder_config.set_string('-logfn', '/dev/null')

            self.decoder = pocketsphinx.Decoder(decoder_config)

    # -------------------------------------------------------------------------

    def maybe_convert_wav(self, wav_data):
        # Ensure 16-bit 16Khz mono
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, 'rb') as wav_file:
                rate, width, channels = wav_file.getframerate(), wav_file.getsampwidth(), wav_file.getnchannels()
                logging.debug('rate=%s, width=%s, channels=%s.' % (rate, width, channels))

                if (rate != 16000) or (width != 2) or (channels != 1):
                    logging.info('Need to convert to 16-bit 16Khz mono.')
                    # Convert a WAV to 16-bit, 16Khz mono
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
                else:
                    # Return original data
                    return wav_file.readframes(wav_file.getnframes())

    # -------------------------------------------------------------------------

    def transcribe(self, audio_data):
        assert self.decoder is not None, 'No decoder'

        # Process data as an entire utterance
        start_time = time.time()
        self.decoder.start_utt()
        self.decoder.process_raw(audio_data, False, True)
        self.decoder.end_utt()
        end_time = time.time()

        logging.debug('Decoded WAV in %s second(s)' % (end_time - start_time))

        if self.decoder.hyp() is not None:
            # Return best transcription
            return self.decoder.hyp().hypstr

        # No transcription
        return ''

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    from thespian.actors import ActorSystem
    profile = Profile('en', ['profiles'])

    # Start actor system
    system = ActorSystem('multiprocQueueBase')

    try:
        ps_actor = system.createActor(PocketsphinxSpeechActor)

        # Load profile
        system.tell(ps_actor, profile)

        # Decode
        with open('etc/test/what_time_is_it.wav', 'rb') as wav_file:
            result = system.ask(ps_actor, TranscribeWav(wav_file.read()))
            print(result.text)
            assert result.text == 'what time is it'
    finally:
        # Shut down actor system
        system.shutdown()
