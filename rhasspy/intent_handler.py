"""Support for intent handling using external service."""
import json
import os
import subprocess
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Type
from urllib.parse import urljoin

import pydash
import requests

from rhasspy.actor import RhasspyActor
from rhasspy.events import (ForwardIntent, HandleIntent, IntentForwarded,
                            IntentHandled, SpeakSentence)
from rhasspy.utils import hass_request_kwargs

# -----------------------------------------------------------------------------


def get_intent_handler_class(system: str) -> Type[RhasspyActor]:
    """Get type for profile intent handlers."""
    assert system in ["dummy", "hass", "remote", "command"], (
        f"Invalid intent handler system: {system}"
    )

    if system == "hass":
        # Use Home Assistant directly
        return HomeAssistantIntentHandler

    if system == "command":
        # Use command-line intent handler
        return CommandIntentHandler

    if system == "remote":
        # Use remote HTTP intent handler
        return RemoteIntentHandler

    # Use dummy handlers as a fallback
    return DummyIntentHandler


# -----------------------------------------------------------------------------


class DummyIntentHandler(RhasspyActor):
    """Always says intent is handled."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, HandleIntent):
            self.send(message.receiver or sender, IntentHandled(message.intent))
        elif isinstance(message, ForwardIntent):
            self.send(message.receiver or sender, IntentForwarded(message.intent))


# -----------------------------------------------------------------------------
# Home Assistant Intent Handler
# -----------------------------------------------------------------------------


class HomeAssistantHandleType(str, Enum):
    """Method used to communicate intents to Home Assistnat"""

    # Send events to /api/events
    EVENT = "event"

    # Send intents to /api/intent
    INTENT = "intent"


class HomeAssistantIntentHandler(RhasspyActor):
    """Forward intents to Home Assistant as events."""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.hass_config: Dict[str, Any] = {}
        self.event_type_format = ""
        self.pem_file = ""
        self.handle_type: HomeAssistantHandleType = HomeAssistantHandleType.EVENT

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.hass_config = self.profile.get("home_assistant", {})

        # Python format string for generating event type name
        self.event_type_format = self.hass_config.get(
            "event_type_format", "rhasspy_{0}"
        )

        # Method for handling intent:
        # - send rhasspy_* events (event)
        # - use intent integration (intent)
        self.handle_type = self.hass_config.get(
            "handle_type", HomeAssistantHandleType.EVENT
        )

        # PEM file for self-signed HA certificates
        self.pem_file = self.hass_config.get("pem_file", "")
        if (self.pem_file is not None) and self.pem_file:
            self.pem_file = os.path.expandvars(self.pem_file)
            self._logger.debug("Using PEM file at %s", self.pem_file)
        else:
            self.pem_file = None  # disabled

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, HandleIntent):
            intent = message.intent
            try:
                intent = self.handle_intent(intent)
            except Exception as e:
                self._logger.exception("handle_intent")
                intent["error"] = str(e)

            self.send(message.receiver or sender, IntentHandled(intent))
        elif isinstance(message, ForwardIntent):
            intent = message.intent
            try:
                intent_name = pydash.get(intent, "intent.name", "")
                event_type: str = ""
                event_data: Dict[str, Any] = {}

                if "hass_event" not in intent:
                    event_type, event_data = self.make_hass_event(intent)
                    intent["hass_event"] = {
                        "event_type": event_type,
                        "event_data": event_data,
                    }
                else:
                    event_type = intent["hass_event"]["event_type"]
                    event_data = intent["hass_event"]["event_data"]

                self.forward_intent(intent_name, event_type, event_data)
            except Exception as e:
                self._logger.exception("forward_intent")
                intent["error"] = str(e)

            self.send(message.receiver or sender, IntentForwarded(intent))

    # -------------------------------------------------------------------------

    def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Create event for Home Assistant and send it."""
        intent_name = pydash.get(intent, "intent.name", "")

        if not intent_name:
            self._logger.warning("Empty intent. Not sending to Home Assistant")
            return intent

        event_type, slots = self.make_hass_event(intent)

        # Add a copy of the event to the intent for easier debugging
        intent["hass_event"] = {"event_type": event_type, "event_data": slots}

        self.forward_intent(intent_name, event_type, slots)
        return intent

    def forward_intent(self, intent_name: str, event_type: str, slots: Dict[str, Any]):
        """Forward existing event to Home Assistant."""

        if self.handle_type == HomeAssistantHandleType.INTENT:
            # Call /api/intent/handle
            post_url = urljoin(self.hass_config["url"], "api/intent/handle")

            # Send to Home Assistant
            kwargs = hass_request_kwargs(self.hass_config, self.pem_file)
            kwargs["json"] = {"name": intent_name, "data": slots}

            if self.pem_file is not None:
                kwargs["verify"] = self.pem_file

            response = requests.post(post_url, **kwargs)
        else:
            # Send event
            post_url = urljoin(self.hass_config["url"], "api/events/" + event_type)

            # Send to Home Assistant
            kwargs = hass_request_kwargs(self.hass_config, self.pem_file)
            kwargs["json"] = slots

            if self.pem_file is not None:
                kwargs["verify"] = self.pem_file

            response = requests.post(post_url, **kwargs)
            self._logger.debug("POSTed intent to %s", post_url)

        response.raise_for_status()

    # -------------------------------------------------------------------------

    def make_hass_event(self, intent: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Create Home Assistant event from intent."""
        event_type = self.event_type_format.format(intent["intent"]["name"])
        slots = {}
        for entity in intent["entities"]:
            slots[entity["entity"]] = entity["value"]

        # Add meta slots
        slots["_text"] = intent.get("text", "")
        slots["_raw_text"] = intent.get("raw_text", "")

        return event_type, slots

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get problems during startup."""
        problems: Dict[str, Any] = {}
        hass_url = self.hass_config["url"]
        try:
            url = urljoin(self.hass_config["url"], "/api/")
            kwargs = hass_request_kwargs(self.hass_config, self.pem_file)
            requests.get(url, **kwargs)
        except Exception:
            problems[
                "Can't contact server"
            ] = f"Unable to reach your Home Assistant server at {hass_url}. Is it running?"

        return problems


# -----------------------------------------------------------------------------
# Remote Intent Handler
# -----------------------------------------------------------------------------


class RemoteIntentHandler(RhasspyActor):
    """POST intent JSON to remote server"""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.remote_url = ""
        self.hass_handler: Optional[RhasspyActor] = None
        self.receiver: Optional[RhasspyActor] = None
        self.speech_actor: Optional[RhasspyActor] = None
        self.forward_to_hass = False

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.speech_actor = self.config.get("speech")
        self.remote_url = self.profile.get("handle.remote.url")

        self.forward_to_hass = self.profile.get("handle.forward_to_hass", False)
        self.hass_handler = self.config.get("hass_handler")

        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, HandleIntent):
            self.receiver = message.receiver or sender
            intent = message.intent
            try:
                # JSON -> Remote -> JSON
                response = requests.post(self.remote_url, json=message.intent)
                response.raise_for_status()

                intent = response.json()
                self._logger.debug(intent)

                # Check for speech
                speech = intent.get("speech", {})
                speech_text = speech.get("text", "")
                if speech_text and self.speech_actor:
                    self.send(self.speech_actor, SpeakSentence(speech_text))
            except Exception as e:
                self._logger.exception("in_started")
                intent["error"] = str(e)

            if self.forward_to_hass and self.hass_handler:
                self.transition("forwarding")
                self.send(self.hass_handler, ForwardIntent(intent))
            else:
                # No forwarding
                self.send(self.receiver, IntentHandled(intent))

    def in_forwarding(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in forwarding state."""
        if isinstance(message, IntentForwarded):
            # Return back to sender
            self.transition("ready")
            self.send(self.receiver, IntentHandled(message.intent))


# -----------------------------------------------------------------------------
# Command Intent Handler
# -----------------------------------------------------------------------------


class CommandIntentHandler(RhasspyActor):
    """Command-line based intent handler"""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.command: List[str] = []
        self.speech_actor: Optional[RhasspyActor] = None
        self.hass_handler: Optional[RhasspyActor] = None
        self.receiver: Optional[RhasspyActor] = None
        self.forward_to_hass = False

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.speech_actor = self.config.get("speech")
        program = os.path.expandvars(self.profile.get("handle.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("handle.command.arguments", [])
        ]

        self.command = [program] + arguments

        self.forward_to_hass = self.profile.get("handle.forward_to_hass", False)
        self.hass_handler = self.config.get("hass_handler")

        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, HandleIntent):
            self.receiver = message.receiver or sender
            intent = message.intent
            try:
                self._logger.debug(self.command)

                # JSON -> STDIN -> STDOUT -> JSON
                json_input = json.dumps(intent).encode()
                output = subprocess.run(
                    self.command, check=True, input=json_input, stdout=subprocess.PIPE
                ).stdout.decode()

                intent = json.loads(output)
                self._logger.debug(intent)

                # Check for speech
                speech = intent.get("speech", {})
                speech_text = speech.get("text", "")
                if speech_text and self.speech_actor:
                    self.send(self.speech_actor, SpeakSentence(speech_text))
            except Exception as e:
                self._logger.exception("in_started")
                intent["error"] = str(e)

            if self.forward_to_hass and self.hass_handler:
                self.transition("forwarding")
                self.send(self.hass_handler, ForwardIntent(intent))
            else:
                # No forwarding
                self.send(self.receiver, IntentHandled(intent))

    def in_forwarding(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in forwarding state."""
        if isinstance(message, IntentForwarded):
            # Return back to sender
            self.transition("ready")
            self.send(self.receiver, IntentHandled(message.intent))
