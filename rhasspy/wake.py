#!/usr/bin/env python3
import os
import threading
import logging
import json
import re
import subprocess
from uuid import uuid4
from typing import Optional, Any, List, Dict

from thespian.actors import ActorAddress

from .actor import RhasspyActor
from .profiles import Profile
from .audio_recorder import StartStreaming, StopStreaming, AudioData
from .mqtt import MqttSubscribe, MqttMessage
from .utils import ByteStream, read_dict

# -----------------------------------------------------------------------------

class ListenForWakeWord:
    def __init__(self, receiver:Optional[ActorAddress]=None, record=True) -> None:
        self.receiver = receiver
        self.record = record

class StopListeningForWakeWord:
    def __init__(self, receiver:Optional[ActorAddress]=None, record=True) -> None:
        self.receiver = receiver
        self.record = record

class WakeWordDetected:
    def __init__(self, name: str, audio_data_info:Dict[Any, Any]={}) -> None:
        self.name = name
        self.audio_data_info = audio_data_info

class WakeWordNotDetected:
    def __init__(self, name: str, audio_data_info:Dict[Any, Any]={}) -> None:
        self.name = name
        self.audio_data_info = audio_data_info

# -----------------------------------------------------------------------------

class DummyWakeListener(RhasspyActor):
    '''Does nothing'''
    def in_started(self, message: Any, sender: ActorAddress) -> None:
        pass

# -----------------------------------------------------------------------------
# Pocketsphinx based wake word listener
# https://github.com/cmusphinx/pocketsphinx
# -----------------------------------------------------------------------------

class PocketsphinxWakeListener(RhasspyActor):
    '''Listens for a wake word with pocketsphinx.'''
    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[ActorAddress] = []
        self.decoder = None
        self.decoder_started:bool = False

    def to_started(self, from_state:str) -> None:
        self.recorder = self.config['recorder']
        self.preload:bool = self.config.get('preload', False)
        self.not_detected:bool = self.config.get('not_detected', False)
        self.chunk_size:int = self.profile.get('wake.pocketsphinx.chunk_size', 960)
        if self.preload:
            self.load_decoder()

        self.transition('loaded')

    def in_loaded(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, ListenForWakeWord):
            self.load_decoder()
            self.receivers.append(message.receiver or sender)
            self.transition('listening')

            if message.record:
                self.send(self.recorder, StartStreaming(self.myAddress))

    def in_listening(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, AudioData):
            if not self.decoder_started:
                assert self.decoder is not None
                self.decoder.start_utt()
                self.decoder_started = True

            audio_data = message.data
            chunk = audio_data[:self.chunk_size]
            detected = False
            while len(chunk) > 0:
                result = self.process_data(chunk)
                if result is not None:
                    detected = True
                    self._logger.debug('Hotword detected (%s)' % self.keyphrase)
                    output = WakeWordDetected(self.keyphrase,
                                              audio_data_info=message.info)
                    for receiver in self.receivers:
                        self.send(receiver, output)

                    break

                audio_data = audio_data[self.chunk_size:]
                chunk = audio_data[:self.chunk_size]

            # End utterance
            if detected and self.decoder_started:
                assert self.decoder is not None
                self.decoder.end_utt()
                self.decoder_started = False

            if not detected and self.not_detected:
                # Report non-detection
                output = WakeWordNotDetected(self.keyphrase,
                                             audio_data_info=message.info)
                for receiver in self.receivers:
                    self.send(receiver, output)
        elif isinstance(message, StopListeningForWakeWord):
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                # End utterance
                if self.decoder_started:
                    assert self.decoder is not None
                    self.decoder.end_utt()
                    self.decoder_started = False

                if message.record:
                    self.send(self.recorder, StopStreaming(self.myAddress))

                self.transition('loaded')

    # -------------------------------------------------------------------------

    def process_data(self, data:bytes) -> Optional[str]:
        assert self.decoder is not None
        self.decoder.process_raw(data, False, False)
        hyp = self.decoder.hyp()
        if hyp:
            if self.decoder_started:
                self.decoder.end_utt()
                self.decoder_started = False

            return hyp.hypstr

        return None

    # -------------------------------------------------------------------------

    def load_decoder(self) -> None:
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

            # Verify that keyphrase words are in dictionary
            keyphrase_words = re.split(r'\s+', self.keyphrase)
            with open(dict_path, 'r') as dict_file:
                word_dict = read_dict(dict_file)

            dict_upper = self.profile.get('speech_to_text.dictionary_upper', False)
            for word in keyphrase_words:
                if dict_upper:
                    word = word.upper()
                else:
                    word = word.lower()

                if not word in word_dict:
                    self._logger.warn('%s not in dictionary' % word)

            self._logger.debug('Loading wake decoder with hmm=%s, dict=%s' % (hmm_path, dict_path))

            decoder_config = pocketsphinx.Decoder.default_config()
            decoder_config.set_string('-hmm', hmm_path)
            decoder_config.set_string('-dict', dict_path)
            decoder_config.set_string('-keyphrase', self.keyphrase)
            decoder_config.set_string('-logfn', '/dev/null')
            decoder_config.set_float('-kws_threshold', self.threshold)

            mllr_path = self.profile.read_path(
                self.profile.get('wake.pocketsphinx.mllr_matrix'))

            if os.path.exists(mllr_path):
                self._logger.debug('Using tuned MLLR matrix for acoustic model: %s' % mllr_path)
                decoder_config.set_string('-mllr', mllr_path)

            self.decoder = pocketsphinx.Decoder(decoder_config)
            self.decoder_started = False

# -----------------------------------------------------------------------------
# Snowboy wake listener
# https://snowboy.kitt.ai
# -----------------------------------------------------------------------------

class SnowboyWakeListener(RhasspyActor):
    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers:List[ActorAddress] = []
        self.detector = None

    def to_started(self, from_state:str) -> None:
        self.recorder = self.config['recorder']
        self.preload = self.config.get('preload', False)
        self.not_detected:bool = self.config.get('not_detected', False)
        self.chunk_size:int = self.profile.get('wake.snowboy.chunk_size', 960)
        if self.preload:
            self.load_detector()

        self.transition('loaded')

    def in_loaded(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, ListenForWakeWord):
            self.load_detector()
            self.receivers.append(message.receiver or sender)
            self.transition('listening')
            if message.record:
                self.send(self.recorder, StartStreaming(self.myAddress))

    def in_listening(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, AudioData):
            audio_data = message.data
            chunk = audio_data[:self.chunk_size]
            detected = False
            while len(chunk) > 0:
                index = self.process_data(chunk)
                if index > 0:
                    detected = True
                    break

                audio_data = audio_data[self.chunk_size:]
                chunk = audio_data[:self.chunk_size]

            if detected:
                # Detected
                self._logger.debug('Hotword detected (%s)' % self.model_name)
                result = WakeWordDetected(self.model_name,
                                          audio_data_info=message.info)
                for receiver in self.receivers:
                    self.send(receiver, result)
            elif self.not_detected:
                # Not detected
                result = WakeWordNotDetected(self.model_name,
                                             audio_data_info=message.info)
                for receiver in self.receivers:
                    self.send(receiver, result)
        elif isinstance(message, StopListeningForWakeWord):
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                if message.record:
                    self.send(self.recorder, StopStreaming(self.myAddress))
                self.transition('loaded')

    # -------------------------------------------------------------------------

    def process_data(self, data: bytes) -> int:
        assert self.detector is not None
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

    def load_detector(self) -> None:
        if self.detector is None:
            from snowboy import snowboydetect, snowboydecoder

            self.model_name = self.profile.get('wake.snowboy.model')
            model_path = self.profile.read_path(self.model_name)

            sensitivity = float(self.profile.get('wake.snowboy.sensitivity', 0.5))
            audio_gain = float(self.profile.get('wake.snowboy.audio_gain', 1.0))

            self.detector = snowboydetect.SnowboyDetect(
                snowboydecoder.RESOURCE_FILE.encode(), model_path.encode())

            assert self.detector is not None

            sensitivity_str = str(sensitivity).encode()
            self.detector.SetSensitivity(sensitivity_str)
            self.detector.SetAudioGain(audio_gain)

            self._logger.debug('Loaded snowboy (model=%s, sensitivity=%s, audio_gain=%s)' \
                              % (model_path, sensitivity, audio_gain))

# -----------------------------------------------------------------------------
# Mycroft Precise wake listener
# https://github.com/MycroftAI/mycroft-precise
# -----------------------------------------------------------------------------

class PreciseWakeListener(RhasspyActor):
    '''Listens for a wake word using Mycroft Precise.'''
    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[ActorAddress] = []
        self.stream:Optional[ByteStream] = None
        self.engine = None
        self.runner = None
        self.prediction_event = threading.Event()
        self.detected:bool = False

    def to_started(self, from_state:str) -> None:
        self.recorder = self.config['recorder']
        self.preload = self.config.get('preload', False)
        self.not_detected:bool = self.config.get('not_detected', False)
        self.chunk_size:int = self.profile.get('wake.precise.chunk_size', 2048)
        if self.preload:
            self.load_runner()

        self.transition('loaded')

    def in_loaded(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, ListenForWakeWord):
            self.load_runner()
            self.receivers.append(message.receiver or sender)
            self.transition('listening')
            if message.record:
                self.send(self.recorder, StartStreaming(self.myAddress))

    def in_listening(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, AudioData):
            audio_data = message.data
            chunk = audio_data[:self.chunk_size]
            detected = False
            while len(chunk) > 0:
                self.process_data(audio_data)
                if self.detected:
                    break

                audio_data = audio_data[self.chunk_size:]
                chunk = audio_data[:self.chunk_size]

            if self.detected:
                # Detected
                self._logger.debug('Hotword detected (%s)' % self.model_name)
                result = WakeWordDetected(self.model_name,
                                          audio_data_info=message.info)
                for receiver in self.receivers:
                    self.send(receiver, result)
                self.detected = False # reset
            elif self.not_detected:
                # Not detected
                result = WakeWordNotDetected(self.model_name,
                                             audio_data_info=message.info)
                for receiver in self.receivers:
                    self.send(receiver, result)
        elif isinstance(message, StopListeningForWakeWord):
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                if message.record:
                    self.send(self.recorder, StopStreaming(self.myAddress))
                self.transition('loaded')

    def to_stopped(self, from_state:str) -> None:
        if self.stream is not None:
            self.stream.close()

        if self.runner is not None:
            self.runner.stop()

    # -------------------------------------------------------------------------

    def process_data(self, data: bytes) -> None:
        assert self.stream is not None
        self.stream.write(data)
        self.prediction_event.wait()

    # -------------------------------------------------------------------------

    def load_runner(self) -> None:
        if self.engine is None:
            from precise_runner import PreciseEngine
            self.model_name = self.profile.get('wake.precise.model')
            self.model_path = self.profile.read_path(self.model_name)
            self.engine = PreciseEngine('precise-engine',
                                        self.model_path,
                                        chunk_size=self.chunk_size)

        if self.runner is None:
            from precise_runner import PreciseRunner

            self.stream = ByteStream()

            sensitivity = float(self.profile.get('wake.precise.sensitivity', 0.5))
            trigger_level = int(self.profile.get('wake.precise.trigger_level', 3))

            def on_prediction(prob:float) -> None:
                self.prediction_event.set()

            def on_activation() -> None:
                self.detected = True

            self.runner = PreciseRunner(self.engine, stream=self.stream,
                                        sensitivity=sensitivity,
                                        trigger_level=trigger_level,
                                        on_prediction=on_prediction,
                                        on_activation=on_activation)

            assert self.runner is not None
            self.runner.start()

            self._logger.debug('Loaded Mycroft Precise (model=%s, sensitivity=%s, trigger_level=%s)' \
                         % (self.model_path, sensitivity, trigger_level))

# -----------------------------------------------------------------------------
# MQTT-based wake listener (Hermes protocol)
# https://docs.snips.ai/ressources/hermes-protocol
# -----------------------------------------------------------------------------

class HermesWakeListener(RhasspyActor):
    '''Listens for a wake word using MQTT.'''
    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[ActorAddress] = []

    def to_started(self, from_state:str) -> None:
        self.mqtt = self.config['mqtt']

        # Subscribe to wake topic
        self.site_id:str = self.profile.get('mqtt.site_id', 'default')
        self.wakeword_id:str = self.profile.get('wake.hermes.wakeword_id', 'default')
        self.wake_topic = 'hermes/hotword/%s/detected' % self.wakeword_id
        self.send(self.mqtt, MqttSubscribe(self.wake_topic))

        self.transition('loaded')

    def in_loaded(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, ListenForWakeWord):
            self.receivers.append(message.receiver or sender)
            self.transition('listening')

    def in_listening(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, MqttMessage):
            if message.topic == self.wake_topic:
                # Check site ID
                payload = json.loads(message.payload.decode())
                payload_site_id = payload.get('siteId', '')
                if payload_site_id != self.site_id:
                    self._logger.debug('Got detected message, but wrong site id (%s)' % payload_site_id)
                    return

                # Pass downstream to receivers
                self._logger.debug('Hotword detected (%s)' % self.wakeword_id)
                result = WakeWordDetected(self.wakeword_id)
                for receiver in self.receivers:
                    self.send(receiver, result)
        elif isinstance(message, StopListeningForWakeWord):
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                self.transition('loaded')

# -----------------------------------------------------------------------------
# Command Wake Listener
# -----------------------------------------------------------------------------

class CommandWakeListener(RhasspyActor):
    '''Command-line based wake word listener'''
    def __init__(self):
        RhasspyActor.__init__(self)
        self.receivers: List[ActorAddress] = []
        self.wake_proc = None

    def to_started(self, from_state:str) -> None:
        program = os.path.expandvars(self.profile.get('wake.command.program'))
        arguments = [os.path.expandvars(str(a))
                     for a in self.profile.get('wake.command.arguments', [])]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, ListenForWakeWord):
            self.receivers.append(message.receiver or sender)
            self.wake_proc = subprocess.Popen(self.command, stdout=subprocess.PIPE)

            def post_result() -> None:
                # STDOUT -> text
                try:
                    out, _ = self.wake_proc.communicate()
                    wakeword_id = out.decode().strip()
                except:
                    wakeword_id = ''
                    self._logger.exception('post_result')

                # Actor will forward
                if len(wakeword_id) > 0:
                    self.send(self.myAddress, WakeWordDetected(wakeword_id))
                else:
                    self.send(self.myAddress, WakeWordNotDetected(wakeword_id))

            self.transition('listening')

            # Wait for program in a separate thread
            threading.Thread(target=post_result, daemon=True).start()

    def in_listening(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, WakeWordDetected):
            # Pass downstream to receivers
            self._logger.debug('Hotword detected (%s)' % message.name)
            for receiver in self.receivers:
                self.send(receiver, message)
        elif isinstance(message, WakeWordNotDetected):
            # Pass downstream to receivers
            for receiver in self.receivers:
                self.send(receiver, message)
        elif isinstance(message, StopListeningForWakeWord):
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                if self.wake_proc is not None:
                    self.wake_proc.terminate()

                self.transition('started')
