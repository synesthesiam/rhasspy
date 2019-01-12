import json
import logging

import paho.mqtt.client as mqtt

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class HermesMqtt:
    HOTWORD_DETECTED = 'hermes/hotword/default/detected'
    TEXT_CAPTURED = 'hermes/asr/textCaptured'

    SUB_TOPICS = [HOTWORD_DETECTED]

    def __init__(self, core):
        self.core = core
        self.siteId = self.core.get_default('mqtt.siteId', 'default')
        self.client = None

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

        for topic in HermesMqtt.SUB_TOPICS:
            self.client.subscribe(topic)
            logger.debug('Subscribed to %s' % topic)


    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())

            if msg.topic == HermesMqtt.HOTWORD_DETECTED:
                logger.debug('Hotword detected')
                keyphrase = payload.get('modelId', '')
                self.core._handle_wake(self.core.default_profile_name, keyphrase)
        except Exception as e:
            logger.exception('on_message')

    # -------------------------------------------------------------------------

    def text_captured(self, text, likelihood=0, seconds=0):
        if self.client is None:
            return

        payload = json.dumps({
            'siteId': self.siteId,
            'text': text,
            'likelihood': likelihood,
            'seconds': seconds
        }).encode()

        self.client.publish(HermesMqtt.TEXT_CAPTURED, payload)
