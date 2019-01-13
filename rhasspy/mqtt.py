import json
import logging
import uuid
import wave

import paho.mqtt.client as mqtt

# -----------------------------------------------------------------------------
# Interoperability with Snips.AI Hermes protocol
# https://docs.snips.ai/ressources/hermes-protocol
# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class HermesMqtt:
    def __init__(self, core):
        self.core = core
        self.site_id = self.core.get_default('mqtt.siteId', 'default')
        self.client = None

        self.topic_hotword_detected = 'hermes/hotword/%s/detected' % self.site_id
        self.topic_audio_frame = 'hermes/audioServer/%s/audioFrame' % self.site_id
        self.sub_topics = [self.topic_hotword_detected,
                           self.topic_audio_frame]

        self.on_audio_frame = None


    # -------------------------------------------------------------------------

    def start_client(self):
        if self.client is None:
            self.client = mqtt.Client()
            # self.client.enable_logger(logger)
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message

            host = self.core.get_default('mqtt.host', 'localhost')
            port = self.core.get_default('mqtt.port', 1883)
            logger.debug('Connecting to MQTT broker %s:%s' % (host, port))


            username = self.core.get_default('mqtt.username', '')
            password = self.core.get_default('mqtt.password', None)

            if len(username) > 0:
                logger.debug('Logging in as %s' % username)
                self.client.username_pw_set(username, password)

            self.client.connect_async(host, port)
            self.client.loop_start()

    def stop_client(self):
        if self.client is not None:
            logger.debug('Stopping MQTT client')
            self.client.loop_stop()
            self.client = None

    # -------------------------------------------------------------------------

    def on_connect(self, client, userdata, flags, rc):
        logger.info('Connected to MQTT server')

        for topic in self.sub_topics:
            self.client.subscribe(topic)
            logger.debug('Subscribed to %s' % topic)


    def on_message(self, client, userdata, msg):
        try:
            if msg.topic == self.topic_hotword_detected:
                logger.debug('Hotword detected')
                payload = json.loads(msg.payload.decode())
                keyphrase = payload.get('modelId', '')
                self.core._handle_wake(self.core.default_profile_name, keyphrase)
            elif msg.topic == self.topic_audio_frame:
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
