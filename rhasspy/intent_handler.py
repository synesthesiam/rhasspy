#!/usr/bin/env python3
import json
import logging
import os
import subprocess
from typing import Any, Dict, Optional, Tuple, Type
from urllib.parse import urljoin

import pydash
import requests

from rhasspy.actor import RhasspyActor
from rhasspy.profiles import Profile

# -----------------------------------------------------------------------------


class HandleIntent:
    def __init__(
        self, intent: Dict[str, Any], receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.intent = intent
        self.receiver = receiver


class IntentHandled:
    def __init__(self, intent: Dict[str, Any]) -> None:
        self.intent = intent


class ForwardIntent:
    def __init__(
        self, intent: Dict[str, Any], receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.intent = intent
        self.receiver = receiver


class IntentForwarded:
    def __init__(self, intent: Dict[str, Any]) -> None:
        self.intent = intent


# -----------------------------------------------------------------------------


def get_intent_handler_class(system: str) -> Type[RhasspyActor]:
    assert system in ["dummy", "hass", "command"], (
        "Invalid intent handler system: %s" % system
    )

    if system == "hass":
        # Use Home Assistant directly
        return HomeAssistantIntentHandler
    elif system == "command":
        # Use command-line speech trainer
        return CommandIntentHandler

    # Use dummy handlers as a fallback
    return DummyIntentHandler


# -----------------------------------------------------------------------------


class DummyIntentHandler(RhasspyActor):
    """Does nothing"""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, HandleIntent):
            self.send(message.receiver or sender, IntentHandled(message.intent))
        elif isinstance(message, ForwardIntent):
            self.send(message.receiver or sender, IntentForwarded(message.intent))


# -----------------------------------------------------------------------------
# Home Assistant Intent Handler
# -----------------------------------------------------------------------------


class HomeAssistantIntentHandler(RhasspyActor):
    """Forward intents to Home Assistant as events."""

    def to_started(self, from_state: str) -> None:
        self.hass_config = self.profile.get("home_assistant", {})

        # Python format string for generating event type name
        self.event_type_format = self.hass_config.get(
            "event_type_format", "rhasspy_{0}"
        )

        # PEM file for self-signed HA certificates
        self.pem_file = self.hass_config.get("pem_file", "")
        if (self.pem_file is not None) and (len(self.pem_file) > 0):
            self.pem_file = os.path.expandvars(self.pem_file)
            self._logger.debug(f"Using PEM file at {self.pem_file}")
        else:
            self.pem_file = None  # disabled

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
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
                event_type: str = ""
                event_data: Dict[str, Any] = {}

                if not "hass_event" in intent:
                    event_type, event_data = self.make_hass_event(intent)
                    intent["hass_event"] = {
                        "event_type": event_type,
                        "event_data": event_data,
                    }
                else:
                    event_type = intent["hass_event"]["event_type"]
                    event_data = intent["hass_event"]["event_data"]

                self.forward_intent(event_type, event_data)
            except Exception as e:
                self._logger.exception("forward_intent")
                intent["error"] = str(e)

            self.send(message.receiver or sender, IntentForwarded(intent))

    # -------------------------------------------------------------------------

    def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        if len(pydash.get(intent, "intent.name", "")) == 0:
            self._logger.warn("Empty intent. Not sending to Home Assistant")
            return intent

        event_type, slots = self.make_hass_event(intent)

        # Add a copy of the event to the intent for easier debugging
        intent["hass_event"] = {"event_type": event_type, "event_data": slots}

        self.forward_intent(event_type, slots)
        return intent

    def forward_intent(self, event_type: str, slots: Dict[str, Any]):
        # Base URL of Home Assistant server
        post_url = urljoin(self.hass_config["url"], "api/events/" + event_type)

        # Send to Home Assistant
        kwargs = self._get_request_kwargs()
        kwargs["json"] = slots

        if self.pem_file is not None:
            kwargs["verify"] = self.pem_file

        response = requests.post(post_url, **kwargs)
        self._logger.debug(f"POSTed intent to {post_url}")
        response.raise_for_status()

    # -------------------------------------------------------------------------

    def make_hass_event(self, intent: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        event_type = self.event_type_format.format(intent["intent"]["name"])
        slots = {}
        for entity in intent["entities"]:
            slots[entity["entity"]] = entity["value"]

        return event_type, slots

    def _get_request_kwargs(self):
        headers = {}

        # Security stuff
        if ("access_token" in self.hass_config) and len(
            self.hass_config["access_token"]
        ) > 0:
            # Use token from config
            headers["Authorization"] = "Bearer %s" % self.hass_config["access_token"]
        elif ("api_password" in self.hass_config) and len(
            self.hass_config["api_password"]
        ) > 0:
            # Use API password (deprecated)
            headers["X-HA-Access"] = self.hass_config["api_password"]
        elif "HASSIO_TOKEN" in os.environ:
            # Use token from hass.io
            headers["Authorization"] = "Bearer %s" % os.environ["HASSIO_TOKEN"]

        kwargs = {"headers": headers}

        if self.pem_file is not None:
            kwargs["verify"] = self.pem_file

        return kwargs

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        problems: Dict[str, Any] = {}
        hass_url = self.hass_config["url"]
        try:
            url = urljoin(self.hass_config["url"], "/api/")
            kwargs = self._get_request_kwargs()
            requests.get(url, **kwargs)
        except:
            problems[
                "Can't contact server"
            ] = f"Unable to reach your Home Assistant server at {hass_url}. Is it running?"

        return problems


# -----------------------------------------------------------------------------
# Command Intent Recognizer
# -----------------------------------------------------------------------------


class CommandIntentHandler(RhasspyActor):
    """Command-line based intent handler"""

    def to_started(self, from_state: str) -> None:
        program = os.path.expandvars(self.profile.get("handle.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("handle.command.arguments", [])
        ]

        self.command = [program] + arguments

        self.forward_to_hass: bool = self.profile.get("handle.forward_to_hass", False)
        self.hass_handler: Optional[RhasspyActor] = self.config["hass_handler"]
        self.receiver: Optional[RhasspyActor] = None

        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, HandleIntent):
            self.receiver = message.receiver or sender
            intent = message.intent
            try:
                self._logger.debug(self.command)

                # JSON -> STDIN -> STDOUT -> JSON
                input = json.dumps(intent).encode()
                output = subprocess.check_output(self.command, input=input).decode()

                intent = json.loads(output)
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
        if isinstance(message, IntentForwarded):
            # Return back to sender
            self.transition("ready")
            self.send(self.receiver, IntentHandled(message.intent))
