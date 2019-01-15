import io
import json
import logging
import uuid
import wave
import time

import paho.mqtt.client as mqtt

# -----------------------------------------------------------------------------
# Interoperability with Snips.AI Hermes protocol
# https://docs.snips.ai/ressources/hermes-protocol
# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class HermesMqtt:
    def __init__(self, core):
        self.core = core
        self.site_id = self.core.get_default('mqtt.site_id', 'default')
        self.wakeword_id = self.core.get_default('wake.hermes.wakeword_id', 'default')
        self.client = None

        self.host = self.core.get_default('mqtt.host', 'localhost')
        self.port = self.core.get_default('mqtt.port', 1883)
        self.reconnect_sec = self.core.get_default('mqtt.reconnect_sec', 5)

        self.topic_hotword_detected = 'hermes/hotword/%s/detected' % self.wakeword_id
        self.topic_audio_frame = 'hermes/audioServer/%s/audioFrame' % self.site_id
        self.topic_hotword_on = 'hermes/hotword/toggleOn'
        self.topic_hotword_off = 'hermes/hotword/toggleOff'
        self.topic_nlu_query = 'hermes/nlu/query'

        self.sub_topics = [self.topic_hotword_detected,
                           self.topic_audio_frame,
                           self.topic_hotword_on,
                           self.topic_hotword_off,
                           self.topic_nlu_query]

        self.on_audio_frame = None

    # -------------------------------------------------------------------------

    def start_client(self):
        if self.client is None:
            self.client = mqtt.Client()
            # self.client.enable_logger(logger)
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.client.on_disconnect = self.on_disconnect

            username = self.core.get_default('mqtt.username', '')
            password = self.core.get_default('mqtt.password', None)

            if len(username) > 0:
                logger.debug('Logging in as %s' % username)
                self.client.username_pw_set(username, password)

            self.client.connect_async(self.host, self.port)
            self.client.loop_start()

    def stop_client(self):
        if self.client is not None:
            logger.debug('Stopping MQTT client')
            self.client.loop_stop()
            self.client = None

    # -------------------------------------------------------------------------

    def on_connect(self, client, userdata, flags, rc):
        logger.info('Connected to %s:%s' % (self.host, self.port))

        for topic in self.sub_topics:
            self.client.subscribe(topic)
            logger.debug('Subscribed to %s' % topic)

    def on_disconnect(self, client, userdata, flags, rc):
        logger.warn('Disconnected')
        if self.reconnect_sec > 0:
            logger.debug('Reconnecting in %s second(s)' % self.reconnect_sec)
            time.sleep(self.reconnect_sec)
            self.client.connect_async(self.host, self.port)

    def on_message(self, client, userdata, msg):
        try:
            if msg.topic == self.topic_hotword_detected:
                # hermes/hotword/<WAKEWORD_ID>/detected
                payload = json.loads(msg.payload.decode())
                if payload.get('siteId', '') != self.site_id:
                    return

                logger.debug('Hotword detected!')
                keyphrase = payload.get('modelId', '')
                self.core.get_audio_recorder().stop_recording(False, True)
                self.core.get_wake_listener(self.core.default_profile_name).stop_listening()
                self.core._handle_wake(self.core.default_profile_name, keyphrase)
            elif msg.topic == self.topic_hotword_on:
                # hermes/hotword/toggleOn
                payload = json.loads(msg.payload.decode())
                if payload.get('siteId', '') != self.site_id:
                    return

                logger.debug('Hotword on')
                self.core.get_wake_listener(self.core.default_profile_name).start_listening()
            elif msg.topic == self.topic_hotword_off:
                # hermes/hotword/toggleOff
                payload = json.loads(msg.payload.decode())
                if payload.get('siteId', '') != self.site_id:
                    return

                logger.debug('Hotword off')
                self.core.get_wake_listener(self.core.default_profile_name).stop_listening()
            elif msg.topic == self.topic_nlu_query:
                # hermes/nlu/query
                payload = json.loads(msg.payload.decode())
                logger.debug('NLU query')

                # Recognize intent
                text = payload['input']
                intent = self.core.get_intent_recognizer(self.core.default_profile_name).recognize(text)

                logger.debug(intent)

                # Publish intent
                # hermes/intent/<intentName>
                session_id = payload.get('sessionId', '')
                intent_payload = {
                    'sessionId': session_id,
                    'siteId': self.site_id,
                    'input': text,
                    'intent': {
                        'intentName': intent['intent']['name'],
                        'probability': intent['intent']['confidence']
                    },
                    'slots': [
                        { 'slotName': e['entity'],
                          'entity': e['entity'],
                          'value': e['value'],
                          'confidence': 1.0,
                          'raw_value': e['value'] }
                        for e in intent['entities']
                    ]
                }

                topic = 'hermes/intent/%s' % intent['intent']['name']
                self.client.publish(topic, json.dumps(intent_payload).encode())

                # Handle intent
                self.core.get_intent_handler(self.core.default_profile_name).handle_intent(intent)
            elif msg.topic == self.topic_audio_frame:
                # hermes/audioServer/<SITE_ID>/audioFrame/<REQUEST_ID>
                if self.on_audio_frame is not None:
                    # Extract audio data
                    with io.BytesIO() as wav_buffer:
                        with wave.open(wav_buffer, mode='rb') as wav_file:
                            audio_data = wav_file.readframes(wav_file.getnframes())
                            self.on_audio_frame(audio_data)

        except Exception as e:
            logger.exception('on_message')

    # -------------------------------------------------------------------------

    def text_captured(self, text, likelihood=0, seconds=0):
        if self.client is None:
            return

        payload = json.dumps({
            'siteId': self.site_id,
            'text': text,
            'likelihood': likelihood,
            'seconds': seconds
        }).encode()

        topic = 'hermes/asr/textCaptured'
        self.client.publish(topic, payload)

    # -------------------------------------------------------------------------

    def play_bytes(self, wav_data: bytes):
        if self.client is None:
            return

        request_id = str(uuid.uuid4())
        topic = 'hermes/audioServer/%s/playBytes/%s' % (self.site_id, request_id)
        self.client.publish(topic, wav_data)

    # -------------------------------------------------------------------------

    def audio_frame(self, audio_data: bytes):
        if self.client is None:
            return

        # Wrap in WAV
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, mode='wb') as wav_file:
                wav_file.setframerate(16000)
                wav_file.setsampwidth(2)
                wav_file.setnchannels(1)
                wav_file.writeframesraw(audio_data)

            wav_data = wav_buffer.getvalue()
            self.client.publish(self.topic_audio_frame, wav_data)
