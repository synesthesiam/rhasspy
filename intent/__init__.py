#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

from thespian.actors import ActorSystem

from profile import Profile
from .fuzzy import FuzzyWuzzyIntentActor
from .adapt import AdaptIntentActor
from .rasa import RasaIntentActor

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------

class TrainIntentRecognizer:
    def __init__(self, sentences_by_intent):
        self.sentences_by_intent = sentences_by_intent

class IntentRecognizerTrained:
    pass

class RecognizeIntent:
    def __init__(self, text):
        self.text = text

class IntentRecognized:
    def __init__(self, intent):
        self.intent = intent

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    sentences_by_intent = {
        'GetTime': [
            ('tell me the time', 'tell me the time', {}, ['tell', 'me', 'the', 'time']),
            ('what time is it', 'what time is it', {}, ['what', 'time', 'is', 'it']),
            ('what time is it', 'what is the time', {}, ['what', 'is', 'the', 'time'])
        ],

        'ChangeLightColor': [
            ('set the [bedroom light](name) to [red](color)',
             'set the bedroom light to red',
             { 'name': ['bedroom light'], 'color': ['red'] },
             ['set', 'the', 'bedroom', 'light', 'to', 'red']),

            ('make the [bedroom light](name) [green](color)',
             'make the bedroom light green',
             { 'name': ['bedroom light'], 'color': ['green'] },
             ['make', 'the', 'bedroom', 'light', 'green']),

            ('turn the [kitchen light](name) to [blue](color)',
             'turn the kitchen light to blue',
             { 'name': ['kitchen light'], 'color': ['blue'] },
             ['turn', 'the', 'kitchen', 'light', 'blue'])
        ]
    }

    profile = Profile('en', ['profiles'])

    # Start actor system
    system = ActorSystem('multiprocQueueBase')

    try:
        # Test FuzzyWuzzy
        fuzzy_actor = system.createActor(FuzzyWuzzyIntentActor)

        # Load profile
        system.tell(fuzzy_actor, profile)

        # Train
        system.ask(fuzzy_actor, TrainIntentRecognizer(sentences_by_intent))

        # Recognize
        result = system.ask(fuzzy_actor, RecognizeIntent('what is the current time'))
        assert result.intent['intent']['name'] == 'GetTime'
        print(result.intent)

        result = system.ask(fuzzy_actor, RecognizeIntent('please set the bedroom light to blue'))
        assert result.intent['intent']['name'] == 'ChangeLightColor'
        print(result.intent)

        # ---------------------------------------------------------------------

        # Test Mycroft Adapt
        adapt_actor = system.createActor(AdaptIntentActor)

        # Load profile
        system.tell(adapt_actor, profile)

        # Train
        system.ask(adapt_actor, TrainIntentRecognizer(sentences_by_intent))

        # Recognize
        result = system.ask(adapt_actor, RecognizeIntent('what is the current time'))
        assert result.intent['intent']['name'] == 'GetTime'
        print(result.intent)

        result = system.ask(adapt_actor, RecognizeIntent('please set the bedroom light to blue'))
        assert result.intent['intent']['name'] == 'ChangeLightColor'
        print(result.intent)

        # ---------------------------------------------------------------------
        # rasa_actor = system.createActor(RasaIntentActor)

        # # Load profile
        # system.tell(rasa_actor, profile)

        # # Train
        # system.ask(rasa_actor, TrainIntentRecognizer(sentences_by_intent))

        # # Recognize
        # result = system.ask(rasa_actor, RecognizeIntent('what is the current time'))
        # assert result.intent['intent']['name'] == 'GetTime'
        # print(result.intent)

        # result = system.ask(rasa_actor, RecognizeIntent('please set the bedroom light to blue'))
        # assert result.intent['intent']['name'] == 'ChangeLightColor'
        # print(result.intent)
    finally:
        # Shut down actor system
        system.shutdown()
