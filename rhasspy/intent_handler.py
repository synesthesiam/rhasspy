#!/usr/bin/env python3
import os
import logging
from urllib.parse import urljoin
from typing import Dict, Any

from profiles import Profile

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class IntentHandler:
    '''Base class for all intent handlers.'''

    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def preload(self):
        '''Cache anything useful upfront.'''
        pass

    def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        '''Do something with an intent, optionally transforming and returning it.'''
        return intent

# -----------------------------------------------------------------------------

class HomeAssistantIntentHandler(IntentHandler):
    '''Forward intents to Home Assistant as events.'''

    def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
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
            logger.debug('POSTed intent to %s with headers=%s' % (post_url, headers))

            response.raise_for_status()
        except Exception as e:
            # Fail gracefully
            logger.exception('send_intent')
            intent['error'] = str(e)

        return intent
