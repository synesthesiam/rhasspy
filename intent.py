#!/usr/bin/env python3
import os
import json
from collections import defaultdict

import yaml

import utils

def make_examples(profile, sentences_by_intent):
    from fuzzywuzzy import process

    # { intent: [ { 'text': ..., 'slots': { ... } }, ... ] }
    examples = defaultdict(list)

    for intent, intent_sents in sentences_by_intent.items():
        for sentence, entities in intent_sents:
            slots = defaultdict(list)
            for entity, value in entities:
                slots[entity].append(value)

            examples[intent].append({ 'text': sentence,
                                      'slots': slots })

    return examples

# -----------------------------------------------------------------------------

def best_intent(examples, sentence):
    from fuzzywuzzy import process

    # sentence -> (sentence, intent, slots)
    choices = {}
    for intent, intent_examples in examples.items():
        for example in intent_examples:
            text = example['text']
            choices[text] = (text, intent, example['slots'])

    # Find closest matching sentence
    best_text, best_score = process.extractOne(sentence, choices.keys())

    # (text, intent, slots)
    return choices.get(best_text)

# -----------------------------------------------------------------------------
