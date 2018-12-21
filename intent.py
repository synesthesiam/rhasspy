#!/usr/bin/env python3
import os
import re
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

def make_adapt_parser(profile):
    from adapt.entity_tagger import EntityTagger
    from adapt.tools.text.tokenizer import EnglishTokenizer
    from adapt.tools.text.trie import Trie
    from adapt.intent import IntentBuilder
    from adapt.parser import Parser
    from adapt.engine import IntentDeterminationEngine

    stop_words = set()
    stop_words_path = profile.read_path(profile.intent.get('stop_words'))
    if os.path.exists(stop_words_path, 'r') as stop_words_file:
        stop_words = set([line.strip() for line in stop_words_file.readlines()])

    tokenizer = EnglishTokenizer()
    trie = Trie()
    tagger = EntityTagger(trie, tokenizer)
    parser = Parser(tokenizer, tagger)

    engine = IntentDeterminationEngine()

    for intent_name, examples in examples.items():
        # for word in re.split(r'\s+', )
        for mk in music_keywords:
            engine.register_entity(mk, "MusicKeyword")

        # intent = IntentBuilder(intent_name)
        #     .require("MusicVerb")\
        #     .optionally("MusicKeyword")\
        #     .optionally("Artist")\
        #     .build()

# -----------------------------------------------------------------------------
