#!/usr/bin/env python3
import os
import threading
import logging
from uuid import uuid4
from typing import Callable

from .actor import RhasspyActor
from .profiles import Profile
from .audio_recorder import StartStreaming, StopStreaming, AudioData

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# class WakeListener:
#     '''Base class for all wake/hot word listeners.'''

#     def __init__(self, core, audio_recorder: AudioRecorder, profile: Profile) -> None:
#         self.audio_recorder = audio_recorder
#         self.profile = profile
#         self.core = core
#         self._is_listening = False

#     def preload(self):
#         '''Cache important stuff up front.'''
#         pass

#     @property
#     def is_listening(self) -> bool:
#         '''True if wake system is currently recording.'''
#         return self._is_listening

#     def start_listening(self, **kwargs) -> None:
#         '''Start wake system listening in the background and return immedately.'''
#         pass

#     def stop_listening(self) -> None:
#         '''Stop wake system from listening'''
#         pass

# -----------------------------------------------------------------------------
# Pocketsphinx based wake word listener
# https://github.com/cmusphinx/pocketsphinx
# -----------------------------------------------------------------------------

# class PocketsphinxWakeListener(WakeListener):
#     def __init__(self, core, audio_recorder: AudioRecorder, profile: Profile,
#                  detected_callback: Callable[[str, str], None]) -> None:
#         '''Listens for a keyphrase using pocketsphinx.
#         Calls detected_callback when keyphrase is detected and stops.'''

#         WakeListener.__init__(self, core, audio_recorder, profile)
#         self.callback = detected_callback
#         self.decoder = None
#         self.keyphrase = ''
#         self.threshold = 0.0
#         self.listen_thread = None

#     def preload(self):
#         self._maybe_load_decoder()

#     # -------------------------------------------------------------------------

#     def start_listening(self, **kwargs):
#         if self.is_listening:
#             logger.warn('Already listening')
#             return

#         self._maybe_load_decoder()

#         def process_data():
#             do_callback = False
#             self.decoder.start_utt()

#             try:
#                 while True:
#                     # Block until audio data comes in
#                     data = self.audio_recorder.get_queue().get()
#                     if len(data) == 0:
#                         self.decoder.end_utt()
#                         logger.debug('Listening cancelled')
#                         break

#                     self.decoder.process_raw(data, False, False)
#                     hyp = self.decoder.hyp()
#                     if hyp:
#                         self.decoder.end_utt()
#                         logger.debug('Keyphrase detected (%s)!' % self.keyphrase)
#                         do_callback = True
#                         break
#             except Exception as e:
#                 logger.exception('process_data')

#             self._is_listening = False

#             if do_callback:
#                 self.callback(self.profile.name, self.keyphrase, **kwargs)

#         # Start audio recording
#         self.audio_recorder.start_recording(False, True)

#         # Decoder runs in a separate thread
#         listen_thread = threading.Thread(target=process_data, daemon=True)
#         listen_thread.start()
#         self._is_listening = True

#         logging.debug('Listening for wake word with pocketsphinx (keyphrase=%s, threshold=%s)' % (self.keyphrase, self.threshold))

#     # -------------------------------------------------------------------------

#     def _maybe_load_decoder(self):
#         '''Loads speech decoder if not cached.'''
#         if self.decoder is None:
#             import pocketsphinx

#             # Load decoder settings (use speech-to-text configuration as a fallback)
#             hmm_path = self.profile.read_path(
#                 self.profile.get('wake.pocketsphinx.acoustic_model', None) \
#                 or self.profile.get('speech_to_text.pocketsphinx.acoustic_model'))

#             dict_path = self.profile.read_path(
#                 self.profile.get('wake.pocketsphinx.dictionary', None) \
#                 or self.profile.get('speech_to_text.pocketsphinx.dictionary'))

#             self.threshold = float(self.profile.get('wake.pocketsphinx.threshold', 1e-40))
#             self.keyphrase = self.profile.get('wake.pocketsphinx.keyphrase', '')
#             assert len(self.keyphrase) > 0, 'No wake keyphrase'

#             logger.debug('Loading wake decoder with hmm=%s, dict=%s' % (hmm_path, dict_path))

#             decoder_config = pocketsphinx.Decoder.default_config()
#             decoder_config.set_string('-hmm', hmm_path)
#             decoder_config.set_string('-dict', dict_path)
#             decoder_config.set_string('-keyphrase', self.keyphrase)
#             decoder_config.set_string('-logfn', '/dev/null')
#             decoder_config.set_float('-kws_threshold', self.threshold)

#             mllr_path = self.profile.read_path(
#                 self.profile.get('wake.pocketsphinx.mllr_matrix'))

#             if os.path.exists(mllr_path):
#                 logger.debug('Using tuned MLLR matrix for acoustic model: %s' % mllr_path)
#                 decoder_config.set_string('-mllr', mllr_path)

#             self.decoder = pocketsphinx.Decoder(decoder_config)


# -----------------------------------------------------------------------------
# Remote wake word detection with audio data streamed via nanomsg
# https://nanomsg.org
# -----------------------------------------------------------------------------

# class NanomsgWakeListener(WakeListener):
#     def __init__(self, core, audio_recorder: AudioRecorder, profile: Profile,
#                  detected_callback: Callable[[str, str], None]) -> None:
#         '''Streams audio data via nanomsg PUB socket.
#         Listens for reply on PULL socket.
#         Calls detected_callback when keyphrase is detected and stops.'''

#         WakeListener.__init__(self, core, audio_recorder, profile)
#         self.callback = detected_callback
#         self.pub_socket = None
#         self.pull_socket = None

#     def preload(self):
#         self._maybe_create_sockets()

#     # -------------------------------------------------------------------------

#     def start_listening(self, **kwargs):
#         from nanomsg import poll

#         if self.is_listening:
#             logger.warn('Already listening')
#             return

#         self._maybe_create_sockets()

#         def process_data():
#             do_callback = False

#             try:
#                 while True:
#                     # Block until audio data comes in
#                     data = self.audio_recorder.get_queue().get()
#                     if len(data) == 0:
#                         self.decoder.end_utt()
#                         logger.debug('Listening cancelled')
#                         break

#                     # Stream audio data out via nanomsg
#                     self.pub_socket.send(data)

#                     # Check for reply
#                     result, _ = poll([self.pull_socket], [], 0)
#                     if self.pull_socket in result:
#                         response = self.pull_socket.recv().decode()
#                         logger.debug('Wake word detected: %s' % response)
#                         do_callback = True
#                         break
#             except Exception as e:
#                 logger.exception('process_data')

#             self._is_listening = False

#             if do_callback and self.callback is not None:
#                 self.callback(self.profile.name, response, **kwargs)

#         # Start audio recording
#         self.audio_recorder.start_recording(False, True)

#         # Decoder runs in a separate thread
#         thread = threading.Thread(target=process_data, daemon=True)
#         thread.start()
#         self._is_listening = True

#         logging.debug('Listening for wake word remotely with nanomsg')

#     # -------------------------------------------------------------------------

#     def stop_listening(self) -> None:
#         if self.pub_socket is not None:
#             self.pub_socket.close()
#             self.pub_socket = None

#         if self.pull_socket is not None:
#             self.pull_socket.close()
#             self.pull_socket = None

#         logger.debug('Stopped wake listener')

#     # -------------------------------------------------------------------------

#     def _maybe_create_sockets(self):
#         from nanomsg import Socket, PUB, PULL

#         if self.pub_socket is None:
#             pub_address = self.profile.get('wake.nanomsg.pub_address')
#             logger.debug('Binding PUB socket to %s' % pub_address)

#             self.pub_socket = Socket(PUB)
#             self.pub_socket.bind(pub_address)

#         if self.pull_socket is None:
#             pull_address = self.profile.get('wake.nanomsg.pull_address')
#             logger.debug('Binding PULL socket to %s' % pull_address)

#             self.pull_socket = Socket(PULL)
#             self.pull_socket.bind(pull_address)

# -----------------------------------------------------------------------------
# MQTT based wake word detection via Snips.AI Hermes protocol
# https://docs.snips.ai/ressources/hermes-protocol
# -----------------------------------------------------------------------------

# class HermesWakeListener(WakeListener):
#     '''Streams audio data out via MQTT.'''

#     def start_listening(self, **kwargs):
#         if self.is_listening:
#             logger.warn('Already listening')
#             return

#         def process_data():
#             try:
#                 while True:
#                     # Block until audio data comes in
#                     data = self.audio_recorder.get_queue().get()
#                     if len(data) == 0:
#                         logger.debug('Listening cancelled')
#                         break

#                     # Stream audio data out via mqtt
#                     self.core.get_mqtt_client().audio_frame(data)
#             except Exception as e:
#                 logger.exception('process_data')

#             self._is_listening = False

#         # Start audio recording
#         self.audio_recorder.start_recording(False, True)

#         # Decoder runs in a separate thread
#         thread = threading.Thread(target=process_data, daemon=True)
#         thread.start()
#         self._is_listening = True

#         logging.debug('Listening for wake word remotely with MQTT')

# -----------------------------------------------------------------------------
# Snowboy wake listener
# https://snowboy.kitt.ai
# -----------------------------------------------------------------------------

class ListenForWakeWord:
    def __init__(self, receiver=None):
        self.receiver = receiver

class StopListeningForWakeWord:
    def __init__(self, receiver=None):
        self.receiver = receiver

class WakeWordDetected:
    def __init__(self, name: str):
        self.name = name

class SnowboyWakeListener(RhasspyActor):
    def __init__(self):
        RhasspyActor.__init__(self)
        self.receivers = []

    def to_started(self, from_state):
        self.recorder = self.config['recorder']
        self.load_detector()
        self.transition('loaded')

    def in_loaded(self, message, sender):
        if isinstance(message, ListenForWakeWord):
            self.receivers.append(message.receiver or sender)
            self.transition('listening')
            self.send(self.recorder, StartStreaming(self.myAddress))

    def in_listening(self, message, sender):
        if isinstance(message, AudioData):
            index = self.process_data(message.data)
            if index > 0:
                self._logger.debug('Hotword detected (%s)' % self.model_name)
                result = WakeWordDetected(self.model_name)
                for receiver in self.receivers:
                    self.send(receiver, result)
        elif isinstance(message, StopListeningForWakeWord):
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                self.send(self.recorder, StopStreaming(self.myAddress))
                self.transition('loaded')

    # -------------------------------------------------------------------------

    def process_data(self, data: bytes):
        try:
            # Return is:
            # -2 silence
            # -1 error
            #  0 voice
            #  n index n-1
            return self.detector.RunDetection(data)
        except Exception as e:
            self._logger.exception('process_data')

        return -2

    # -------------------------------------------------------------------------

    def load_detector(self):
        from snowboy import snowboydetect, snowboydecoder

        self.model_name = self.profile.get('wake.snowboy.model')
        model_path = self.profile.read_path(self.model_name)

        sensitivity = float(self.profile.get('wake.snowboy.sensitivity', 0.5))
        audio_gain = float(self.profile.get('wake.snowboy.audio_gain', 1.0))

        self.detector = snowboydetect.SnowboyDetect(
            snowboydecoder.RESOURCE_FILE.encode(), model_path.encode())

        sensitivity_str = str(sensitivity).encode()
        self.detector.SetSensitivity(sensitivity_str)
        self.detector.SetAudioGain(audio_gain)

        self._logger.debug('Loaded snowboy (model=%s, sensitivity=%s, audio_gain=%s)' \
                           % (model_path, sensitivity, audio_gain))

# -----------------------------------------------------------------------------
# Mycroft Precise wake listener
# https://github.com/MycroftAI/mycroft-precise
# -----------------------------------------------------------------------------

# class PreciseWakeListener(WakeListener):
#     def __init__(self, core, audio_recorder: AudioRecorder, profile: Profile,
#                  detected_callback: Callable[[str, str], None]) -> None:
#         '''Listens for a wake word using Mycroft Precise.
#         Calls detected_callback when wake word is detected and stops.'''

#         WakeListener.__init__(self, core, audio_recorder, profile)
#         self.callback = detected_callback
#         self.engine = None
#         self.runner = None
#         self.stream = None
#         self.listen_thread = None
#         self.detected = False

#     def preload(self):
#         self._maybe_load_runner()

#     # -------------------------------------------------------------------------

#     def start_listening(self, **kwargs):
#         if self.is_listening:
#             logger.warn('Already listening')
#             return

#         self.detected = False
#         self._maybe_load_runner()

#         def process_data():
#             do_callback = False

#             try:
#                 while True:
#                     # Block until audio data comes in
#                     data = self.audio_recorder.get_queue().get()
#                     if len(data) == 0:
#                         logger.debug('Listening cancelled')
#                         break

#                     self.stream.write(data)

#                     if self.detected:
#                         # Hotword detected
#                         logger.debug('Hotword detected (%s)!' % self.model_name)
#                         do_callback = True
#                         break
#             except Exception as e:
#                 logger.exception('process_data')

#             self._is_listening = False

#             try:
#                 self.stream.close()
#                 self.runner.stop()
#             except Exception as e:
#                 logger.exception('precise-detected')

#             if do_callback:
#                 self.callback(self.profile.name, self.model_name, **kwargs)

#         # Start audio recording
#         self.audio_recorder.start_recording(False, True)

#         # Decoder runs in a separate thread
#         listen_thread = threading.Thread(target=process_data, daemon=True)
#         listen_thread.start()
#         self._is_listening = True

#         logging.debug('Listening for wake word with Mycroft Precise (%s)' % self.model_name)

#     # -------------------------------------------------------------------------

#     def _maybe_load_runner(self):
#         if self.engine is None:
#             from precise_runner import PreciseEngine
#             self.model_name = self.profile.get('wake.precise.model')
#             self.model_path = self.profile.read_path(self.model_name)
#             self.engine = PreciseEngine('precise-engine', self.model_path)

#         if self.runner is None:
#             from precise_runner import PreciseRunner
#             from utils import ByteStream

#             self.stream = ByteStream()

#             sensitivity = float(self.profile.get('wake.precise.sensitivity', 0.5))
#             trigger_level = int(self.profile.get('wake.precise.trigger_level', 3))

#             def on_activation():
#                 self.detected = True

#             self.runner = PreciseRunner(self.engine, stream=self.stream,
#                                         sensitivity=sensitivity,
#                                         trigger_level=trigger_level,
#                                         on_activation=on_activation)

#             self.runner.start()

#             logger.debug('Loaded Mycroft Precise (model=%s, sensitivity=%s, trigger_level=%s)' \
#                          % (self.model_path, sensitivity, trigger_level))
