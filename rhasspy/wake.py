#!/usr/bin/env python3
import os
import threading
import logging
from typing import Callable

from profiles import Profile
from audio_recorder import AudioRecorder

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class WakeListener:
    '''Base class for all wake/hot word listeners.'''

    def __init__(self, core, audio_recorder: AudioRecorder, profile: Profile) -> None:
        self.audio_recorder = audio_recorder
        self.profile = profile
        self.core = core
        self._is_listening = False

    def preload(self):
        '''Cache important stuff up front.'''
        pass

    @property
    def is_listening(self) -> bool:
        '''True if wake system is currently recording.'''
        return self._is_listening

    def start_listening(self, **kwargs) -> None:
        '''Start wake system listening in the background and return immedately.'''
        pass

    def stop_listening(self) -> None:
        '''Stop wake system from listening'''
        pass

# -----------------------------------------------------------------------------
# Pocketsphinx based wake word listener
# https://github.com/cmusphinx/pocketsphinx
# -----------------------------------------------------------------------------

class PocketsphinxWakeListener(WakeListener):
    def __init__(self, core, audio_recorder: AudioRecorder, profile: Profile,
                 detected_callback: Callable[[str, str], None]) -> None:
        '''Listens for a keyphrase using pocketsphinx.
        Calls detected_callback when keyphrase is detected and stops.'''

        WakeListener.__init__(self, core, audio_recorder, profile)
        self.callback = detected_callback
        self.decoder = None
        self.keyphrase = ''
        self.threshold = 0.0
        self.listen_thread = None

    def preload(self):
        self._maybe_load_decoder()

    # -------------------------------------------------------------------------

    def start_listening(self, **kwargs):
        if self.is_listening:
            logger.warn('Already listening')
            return

        self._maybe_load_decoder()

        def process_data():
            do_callback = False
            self.decoder.start_utt()

            try:
                while True:
                    # Block until audio data comes in
                    data = self.audio_recorder.get_queue().get()
                    if len(data) == 0:
                        self.decoder.end_utt()
                        logger.debug('Listening cancelled')
                        break

                    self.decoder.process_raw(data, False, False)
                    hyp = self.decoder.hyp()
                    if hyp:
                        self.decoder.end_utt()
                        logger.debug('Keyphrase detected (%s)!' % self.keyphrase)
                        do_callback = True
                        break
            except Exception as e:
                logger.exception('process_data')

            self._is_listening = False

            if do_callback:
                self.callback(self.profile.name, self.keyphrase, **kwargs)

        # Start audio recording
        self.audio_recorder.start_recording(False, True)

        # Decoder runs in a separate thread
        listen_thread = threading.Thread(target=process_data, daemon=True)
        listen_thread.start()
        self._is_listening = True

        logging.debug('Listening for wake word with pocketsphinx (keyphrase=%s, threshold=%s)' % (self.keyphrase, self.threshold))

    # -------------------------------------------------------------------------

    def _maybe_load_decoder(self):
        '''Loads speech decoder if not cached.'''
        if self.decoder is None:
            import pocketsphinx

            # Load decoder settings (use speech-to-text configuration as a fallback)
            hmm_path = self.profile.read_path(
                self.profile.get('wake.pocketsphinx.acoustic_model', None) \
                or self.profile.get('speech_to_text.pocketsphinx.acoustic_model'))

            dict_path = self.profile.read_path(
                self.profile.get('wake.pocketsphinx.dictionary', None) \
                or self.profile.get('speech_to_text.pocketsphinx.dictionary'))

            self.threshold = float(self.profile.get('wake.pocketsphinx.threshold', 1e-40))
            self.keyphrase = self.profile.get('wake.pocketsphinx.keyphrase', '')
            assert len(self.keyphrase) > 0, 'No wake keyphrase'

            logger.debug('Loading wake decoder with hmm=%s, dict=%s' % (hmm_path, dict_path))

            decoder_config = pocketsphinx.Decoder.default_config()
            decoder_config.set_string('-hmm', hmm_path)
            decoder_config.set_string('-dict', dict_path)
            decoder_config.set_string('-keyphrase', self.keyphrase)
            decoder_config.set_string('-logfn', '/dev/null')
            decoder_config.set_float('-kws_threshold', self.threshold)

            mllr_path = self.profile.read_path(
                self.profile.get('wake.pocketsphinx.mllr_matrix'))

            if os.path.exists(mllr_path):
                logger.debug('Using tuned MLLR matrix for acoustic model: %s' % mllr_path)
                decoder_config.set_string('-mllr', mllr_path)

            self.decoder = pocketsphinx.Decoder(decoder_config)


# -----------------------------------------------------------------------------
# Remote wake word detection with audio data streamed via nanomsg
# https://nanomsg.org
# -----------------------------------------------------------------------------

class NanomsgWakeListener(WakeListener):
    def __init__(self, core, audio_recorder: AudioRecorder, profile: Profile,
                 detected_callback: Callable[[str, str], None]) -> None:
        '''Streams audio data via nanomsg PUB socket.
        Listens for reply on PULL socket.
        Calls detected_callback when keyphrase is detected and stops.'''

        WakeListener.__init__(self, core, audio_recorder, profile)
        self.callback = detected_callback
        self.pub_socket = None
        self.pull_socket = None

    def preload(self):
        self._maybe_create_sockets()

    # -------------------------------------------------------------------------

    def start_listening(self, **kwargs):
        from nanomsg import poll

        if self.is_listening:
            logger.warn('Already listening')
            return

        self._maybe_create_sockets()

        def process_data():
            do_callback = False

            try:
                while True:
                    # Block until audio data comes in
                    data = self.audio_recorder.get_queue().get()
                    if len(data) == 0:
                        self.decoder.end_utt()
                        logger.debug('Listening cancelled')
                        break

                    # Stream audio data out via nanomsg
                    self.pub_socket.send(data)

                    # Check for reply
                    result, _ = poll([self.pull_socket], [], 0)
                    if self.pull_socket in result:
                        response = self.pull_socket.recv().decode()
                        logger.debug('Wake word detected: %s' % response)
                        do_callback = True
                        break
            except Exception as e:
                logger.exception('process_data')

            self._is_listening = False

            if do_callback and self.callback is not None:
                self.callback(self.profile.name, response, **kwargs)

        # Start audio recording
        self.audio_recorder.start_recording(False, True)

        # Decoder runs in a separate thread
        thread = threading.Thread(target=process_data, daemon=True)
        thread.start()
        self._is_listening = True

        logging.debug('Listening for wake word remotely with nanomsg')

    # -------------------------------------------------------------------------

    def stop_listening(self) -> None:
        if self.pub_socket is not None:
            self.pub_socket.close()
            self.pub_socket = None

        if self.pull_socket is not None:
            self.pull_socket.close()
            self.pull_socket = None

        logger.debug('Stopped wake listener')

    # -------------------------------------------------------------------------

    def _maybe_create_sockets(self):
        from nanomsg import Socket, PUB, PULL

        if self.pub_socket is None:
            pub_address = self.profile.get('wake.nanomsg.pub_address')
            logger.debug('Binding PUB socket to %s' % pub_address)

            self.pub_socket = Socket(PUB)
            self.pub_socket.bind(pub_address)

        if self.pull_socket is None:
            pull_address = self.profile.get('wake.nanomsg.pull_address')
            logger.debug('Binding PULL socket to %s' % pull_address)

            self.pull_socket = Socket(PULL)
            self.pull_socket.bind(pull_address)

# -----------------------------------------------------------------------------
# MQTT based wake word detection via Snips.AI Hermes protocol
# https://docs.snips.ai/ressources/hermes-protocol
# -----------------------------------------------------------------------------

class HermesWakeListener(WakeListener):
    '''Streams audio data out via MQTT.'''

    def start_listening(self, **kwargs):
        if self.is_listening:
            logger.warn('Already listening')
            return

        def process_data():
            try:
                while True:
                    # Block until audio data comes in
                    data = self.audio_recorder.get_queue().get()
                    if len(data) == 0:
                        self.decoder.end_utt()
                        logger.debug('Listening cancelled')
                        break

                    # Stream audio data out via mqtt
                    self.core.get_mqtt_client().audio_frame(data)
            except Exception as e:
                logger.exception('process_data')

            self._is_listening = False

        # Start audio recording
        self.audio_recorder.start_recording(False, True)

        # Decoder runs in a separate thread
        thread = threading.Thread(target=process_data, daemon=True)
        thread.start()
        self._is_listening = True

        logging.debug('Listening for wake word remotely with MQTT')

    # -------------------------------------------------------------------------

    def stop_listening(self) -> None:
        logger.debug('Stopped wake listener')
