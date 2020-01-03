"""Support for MQTT input/output."""
import json
import socket
import threading
import time
from collections import defaultdict
from queue import Queue
from typing import Any, Dict, List

import pydash

from rhasspy.actor import RhasspyActor
from rhasspy.events import (MqttConnected, MqttDisconnected, MqttMessage,
                            MqttPublish, MqttSubscribe)

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------


class MessageReady:
    """Internal event for actor."""

    pass


# -----------------------------------------------------------------------------
# Interoperability with Snips.AI Hermes protocol
# https://docs.snips.ai/reference/hermes
# -----------------------------------------------------------------------------


class HermesMqtt(RhasspyActor):
    """Communicate with MQTT broker using Hermes protocol."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.client = None
        self.connected = False
        self.subscriptions: Dict[str, List[RhasspyActor]] = defaultdict(list)
        self.publications: Dict[str, List[bytes]] = defaultdict(list)
        self.message_queue: Queue = Queue()
        self.site_ids: List[str] = []
        self.site_id = "default"
        self.host = "localhost"
        self.port = 1883
        self.username = ""
        self.password = None
        self.reconnect_sec = 5
        self.publish_intents = True

    # -------------------------------------------------------------------------

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        # Load settings
        self.site_ids = self.profile.get("mqtt.site_id", "default").split(",")
        if self.site_ids:
            self.site_id = self.site_ids[0]
        else:
            self.site_id = "default"

        self.host = self.profile.get("mqtt.host", "localhost")
        self.port = int(self.profile.get("mqtt.port", 1883))
        self.username = self.profile.get("mqtt.username", "")
        self.password = self.profile.get("mqtt.password", None)
        self.reconnect_sec = self.profile.get("mqtt.reconnect_sec", 5)
        self.publish_intents = self.profile.get("mqtt.publish_intents", True)

        if self.profile.get("mqtt.enabled", False):
            self.transition("connecting")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        self.save_for_later(message, sender)

    def to_connecting(self, from_state: str) -> None:
        """Transition to connecting state."""
        import paho.mqtt.client as mqtt

        self.client = mqtt.Client()
        assert self.client is not None
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        if self.username:
            self._logger.debug("Logging in as %s", self.username)
            self.client.username_pw_set(self.username, self.password)

        self._logger.debug("Connecting to MQTT broker %s:%s", self.host, self.port)

        def do_connect():
            success = False
            while not success:
                try:
                    ret = self.client.connect(self.host, self.port)
                    self.client.loop_start()
                    while (ret != 0) and (self.reconnect_sec > 0):
                        self._logger.warning("Connection failed: %s", ret)
                        self._logger.debug(
                            "Reconnecting in %s second(s)", self.reconnect_sec
                        )
                        time.sleep(self.reconnect_sec)
                        ret = self.client.connect(self.host, self.port)

                    success = True
                except Exception:
                    self._logger.exception("connecting")
                    if self.reconnect_sec > 0:
                        self._logger.debug(
                            "Reconnecting in %s second(s)", self.reconnect_sec
                        )
                        time.sleep(self.reconnect_sec)

            self._logger.debug("Connection successful.")

        # Connect in a separate thread
        threading.Thread(target=do_connect, daemon=True).start()

    def in_connecting(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in connecting."""
        if isinstance(message, MqttConnected):
            self.connected = True
            self.transition("connected")
        elif isinstance(message, MqttDisconnected):
            if self.reconnect_sec > 0:
                self._logger.debug("Reconnecting in %s second(s)", self.reconnect_sec)
                time.sleep(self.reconnect_sec)
                self.transition("started")
        else:
            self.save_for_later(message, sender)

    def to_connected(self, from_state: str) -> None:
        """Transition to connected state."""
        assert self.client is not None
        # Subscribe to topics
        for topic in self.subscriptions:
            self.client.subscribe(topic)
            self._logger.debug("Subscribed to %s", topic)

        # Publish outstanding messages
        for topic, payloads in self.publications.items():
            for payload in payloads:
                self.client.publish(topic, payload)

        self.publications.clear()

    def in_connected(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in connected state."""
        if isinstance(message, MqttDisconnected):
            if self.reconnect_sec > 0:
                self._logger.debug("Reconnecting in %s second(s)", self.reconnect_sec)
                time.sleep(self.reconnect_sec)
                self.transition("started")
            else:
                self.transition("connecting")
        elif isinstance(message, MessageReady):
            while not self.message_queue.empty():
                mqtt_message = self.message_queue.get()
                for receiver in self.subscriptions[mqtt_message.topic]:
                    self.send(receiver, mqtt_message)
        elif self.connected:
            from rhasspy.intent import IntentRecognized

            assert self.client is not None
            if isinstance(message, MqttSubscribe):
                receiver = message.receiver or sender
                self.subscriptions[message.topic].append(receiver)
                self.client.subscribe(message.topic)
                self._logger.debug("Subscribed to %s", message.topic)
            elif isinstance(message, MqttPublish):
                self.client.publish(message.topic, message.payload)
            elif isinstance(message, IntentRecognized):
                if self.publish_intents:
                    self.publish_intent(message.intent)
        else:
            self.save_for_later(message, sender)

    def to_stopped(self, from_state: str) -> None:
        """Transition to stopped state."""
        if self.client is not None:
            self.connected = False
            self._logger.debug("Stopping MQTT client")
            self.client.loop_stop()
            self.client = None

    # -------------------------------------------------------------------------

    def save_for_later(self, message: Any, sender: RhasspyActor) -> None:
        """Cache message until connected."""
        if isinstance(message, MqttSubscribe):
            receiver = message.receiver or sender
            self.subscriptions[message.topic].append(receiver)
        elif isinstance(message, MqttPublish):
            self.publications[message.topic].append(message.payload)

    # -------------------------------------------------------------------------

    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker."""
        try:
            self._logger.info("Connected to %s:%s", self.host, self.port)
            self.send(self.myAddress, MqttConnected())
        except Exception:
            self._logger.exception("on_connect")

    def on_disconnect(self, client, userdata, flags, rc):
        """Callback when disconnected from broker."""
        try:
            self._logger.warning("Disconnected")
            self.connected = False
            self.send(self.myAddress, MqttDisconnected())
        except Exception:
            self._logger.exception("on_disconnect")

    def on_message(self, client, userdata, msg):
        """Callback when message received."""
        try:
            self.message_queue.put(MqttMessage(msg.topic, msg.payload))
            self.send(self.myAddress, MessageReady())
        except Exception:
            self._logger.exception("on_message")

    # -------------------------------------------------------------------------

    def publish_intent(self, intent: Dict[str, Any]) -> None:
        """Publish intent to MQTT using Hermes protocol."""
        intent_name = pydash.get(intent, "intent.name", "")
        not_recognized = len(intent_name) == 0

        assert self.client is not None

        if not_recognized:
            # Publish using Hermes protocol
            topic = "hermes/nlu/intentNotRecognized"
            payload = json.dumps({"sessionId": "", "input": intent.get("text", "")})
        else:
            # Publish using Rhasspy protocol
            topic = f"rhasspy/intent/{intent_name}"
            payload = json.dumps(
                {ev["entity"]: ev["value"] for ev in intent["entities"]}
            )
            self.client.publish(topic, payload)

            # Publish using Hermes protocol
            topic = f"hermes/intent/{intent_name}"
            payload = json.dumps(
                {
                    "sessionId": "",
                    "siteId": self.site_id,
                    "input": intent.get("text", ""),
                    "intent": {
                        "intentName": intent_name,
                        "confidenceScore": pydash.get(intent, "intent.confidence", 1),
                    },
                    "slots": [
                        {
                            "slotName": ev["entity"],
                            "confidence": 1,
                            "value": {"kind": ev["entity"], "value": ev["value"]},
                            "rawValue": ev["value"],
                        }
                        for ev in intent.get("entities", [])
                    ],
                }
            ).encode()

        self.client.publish(topic, payload)
        self._logger.debug("Published intent to %s", topic)

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get problems on startup."""
        problems: Dict[str, Any] = {}
        s = socket.socket()
        try:
            s.connect((self.host, self.port))
        except Exception:
            problems[
                "Can't connect to server"
            ] = f"Unable to connect to your MQTT server at {self.host}:{self.port}. Is it running?"
        finally:
            s.close()

        return problems
