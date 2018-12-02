#!/usr/bin/env python3
import os
import threading
import logging

def pocketsphinx_wake(profile, wake_decoders, wake_word_detected, device_index=None):
    import pocketsphinx
    import pyaudio

    wake_config = profile.wake['pocketsphinx']
    ps_config = profile.speech_to_text.get('pocketsphinx', {})

    # Load decoder settings (use speech-to-text configuration as a fallback)
    hmm_path = profile.read_path(
        wake_config.get('acoustic_model', None) \
        or ps_config['acoustic_model'])

    dict_path = profile.read_path(
        wake_config.get('dictionary', None) \
        or ps_config['dictionary'])

    kws_threshold = wake_config.get('threshold', 1e-40)
    keyphrase = wake_config['keyphrase']

    def listen_pocketsphinx():
        def run_decoder():
            decoder = wake_decoders.get(profile.name)

            if decoder is None:
                logging.info('Loading wake decoder with hmm=%s, dict=%s' % (hmm_path, dict_path))

                decoder_config = pocketsphinx.Decoder.default_config()
                decoder_config.set_string('-hmm', hmm_path)
                decoder_config.set_string('-dict', dict_path)
                decoder_config.set_string('-keyphrase', keyphrase)
                decoder_config.set_float('-kws_threshold', kws_threshold)

                decoder = pocketsphinx.Decoder(decoder_config)
                wake_decoders[profile.name] = decoder

            decoder.start_utt()
            finished_event = threading.Event()

            def stream_callback(data, frame_count, time_info, status):
                decoder.process_raw(data, False, False)
                hyp = decoder.hyp()
                if hyp:
                    decoder.end_utt()
                    logging.debug('Keyphrase detected')
                    finished_event.set()
                    return (data, pyaudio.paComplete)

                return (data, pyaudio.paContinue)

            audio = pyaudio.PyAudio()
            data_format = pyaudio.get_format_from_width(2)
            mic = audio.open(format=data_format, channels=1, rate=16000,
                            input=True, input_device_index=device_index,
                             stream_callback=stream_callback)

            # Block until wake word is detected
            mic.start_stream()
            finished_event.wait()

            # Shut down audio input
            mic.stop_stream()
            mic.close()
            audio.terminate()

            # Pass to next stage
            wake_word_detected()

        # Decoder runs in a separate thread
        thread = threading.Thread(target=run_decoder, daemon=True)
        thread.start()
        logging.debug('Listening for wake word with pocketsphinx (keyphrase=%s)' % keyphrase)

    return listen_pocketsphinx
