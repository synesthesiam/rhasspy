#!/usr/bin/env python3
import os
import logging
from urllib.parse import urljoin
from typing import Dict, Any

from .actor import RhasspyActor
from .profiles import Profile

# -----------------------------------------------------------------------------

class HandleIntent:
    def __init__(self, intent: Dict[str, Any], receiver = None) -> None:
        self.intent = intent
        self.receiver = receiver

class IntentHandled:
    def __init__(self, intent: Dict[str, Any]) -> None:
        self.intent = intent

# -----------------------------------------------------------------------------

class HomeAssistantIntentHandler(RhasspyActor):
    '''Forward intents to Home Assistant as events.'''

    def in_started(self, message, sender):
        if isinstance(message, HandleIntent):
            intent = self.handle_intent(message.intent)
            self.send(message.receiver or sender, IntentHandled(intent))

    # -------------------------------------------------------------------------

    def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        if len(intent['intent']['name']) == 0:
            self._logger.warn('Empty intent. Not sending to Home Assistant')
            return intent

        import requests

        hass_config = self.profile.get('home_assistant', {})

        # Python format string for generating event type name
        event_type_format = hass_config['event_type_format']
        event_type = event_type_format.format(intent['intent']['name'])

        # Base URL of Home Assistant server
        post_url = urljoin(hass_config['url'], 'api/events/' + event_type)
        headers = {}

        # Security stuff
        if ('access_token' in hass_config) and \
            len(hass_config['access_token']) > 0:
            # Use token from config
            headers['Authorization'] = 'Bearer %s' % hass_config['access_token']
        elif 'HASSIO_TOKEN' in os.environ:
            # Use token from hass.io
            headers['Authorization'] = 'Bearer %s' % os.environ['HASSIO_TOKEN']
        elif ('api_password' in hass_config) and \
          len(hass_config['api_password']) > 0:
            # Use API password (deprecated)
            headers['X-HA-Access'] = hass_config['api_password']

        # Add intent entities as event data properties
        slots = {}
        for entity in intent['entities']:
            slots[entity['entity']] = entity['value']

        # Add a copy of the event to the intent for easier debugging
        intent['hass_event'] = {
            'event_type': event_type,
            'event_data': slots
        }

        try:
            # Send to Home Assistant
            response = requests.post(post_url, headers=headers, json=slots)
            self._logger.debug('POSTed intent to %s with headers=%s' % (post_url, headers))

            response.raise_for_status()
        except Exception as e:
            # Fail gracefully
            self._logger.exception('send_intent')
            intent['error'] = str(e)

        return intent
