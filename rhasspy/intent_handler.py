#!/usr/bin/env python3
import os
import logging
from urllib.parse import urljoin
from typing import Dict, Any

from profile import Profile

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class IntentHandler:
    def __init__(self, profile: Profile):
        self.profile = profile

    def preload(self):
        pass

    def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        return intent

# -----------------------------------------------------------------------------

class HomeAssistantIntentHandler(IntentHandler):

    def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        import requests

        hass_config = self.profile.get('home_assistant', {})

        event_type_format = hass_config['event_type_format']
        event_type = event_type_format.format(intent['intent']['name'])
        post_url = urljoin(hass_config['url'], 'api/events/' + event_type)
        headers = {}

        if ('access_token' in hass_config) and \
            len(hass_config['access_token']) > 0:
            # Use token from config
            headers['Authorization'] = 'Bearer %s' % hass_config['access_token']
        elif 'HASSIO_TOKEN' in os.environ:
            # Use token from hass.io
            headers['Authorization'] = 'Bearer %s' % os.environ['HASSIO_TOKEN']
        elif ('api_password' in hass_config) and \
          len(hass_config['api_password']) > 0:
            # Use API pasword
            headers['X-HA-Access'] = hass_config['api_password']

        slots = {}
        for entity in intent['entities']:
            slots[entity['entity']] = entity['value']

        # Add a copy of the event to the intent
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
            logger.exception('send_intent')
            intent['error'] = str(e)

        return intent
