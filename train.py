import os
import re
import tempfile
import subprocess
import logging
import shutil
import json
from collections import defaultdict

import yaml

import intent
import utils
import jsgf_utils

def train(profile):
    stt_config = profile.speech_to_text
    intent_config = profile.intent

    # Load sentence templates, write examples
    sentences_ini_path = profile.read_path(stt_config['sentences_ini'])

    # Load from ini file and write to examples file
    words_needed = set()
    sentences_by_intent = defaultdict(list)
    grammars_dir = profile.write_dir(stt_config['grammars_dir'])

    with open(sentences_ini_path, 'r') as sentences_ini_file:
        grammar_paths = jsgf_utils.make_grammars(sentences_ini_file, grammars_dir)

        # intent -> sentence templates
        tagged_sentences = jsgf_utils.generate_sentences(grammar_paths)

        for intent_name, intent_sents in tagged_sentences.items():
            for intent_sent in intent_sents:
                # Template -> untagged sentence + entities
                sentence, entities = utils.extract_entities(intent_sent)

                # Split sentence into words (tokens)
                sentence, tokens = sanitize_sentence(sentence, profile.training)
                sentences_by_intent[intent_name].append((sentence, entities))

                # Collect all used words
                words_needed.update(tokens)

    # Load base and custom dictionaries
    ps_config = stt_config['pocketsphinx']
    base_dictionary_path = profile.read_path(ps_config['base_dictionary'])
    custom_path = profile.read_path(ps_config['custom_words'])

    word_dict = {}
    for word_dict_path in [base_dictionary_path, custom_path]:
        if os.path.exists(word_dict_path):
            with open(word_dict_path, 'r') as dictionary_file:
                utils.read_dict(dictionary_file, word_dict)

    # Add words from wake word if using pocketsphinx
    if profile.wake.get('system') == 'pocketsphinx':
        wake_config = profile.wake['pocketsphinx']
        wake_keyphrase = wake_config['keyphrase']
        _, wake_tokens = sanitize_sentence(wake_keyphrase, profile.training)
        words_needed.update(wake_tokens)

    # Check for unknown words
    unknown_words = words_needed - word_dict.keys()
    unknown_path = profile.read_path(ps_config['unknown_words'])

    if len(unknown_words) > 0:
        with open(unknown_path, 'w') as unknown_file:
            for word in unknown_words:
                result = utils.lookup_word(word, word_dict, profile, n=1)

                pronounces = result['pronunciations']
                phonemes = ' '.join(pronounces)

                # Dictionary uses upper-case letters
                if stt_config.get('dictionary_upper', False):
                    word = word.upper()
                else:
                    word = word.lower()

                print(word.lower(), phonemes, file=unknown_file)

        raise RuntimeError('Training failed due to %s unknown word(s)' % len(unknown_words))

    elif os.path.exists(unknown_path):
        # Remove unknown dictionary
        os.unlink(unknown_path)


    # Write out dictionary with only the necessary words (speeds up loading)
    dictionary_path = profile.write_path(ps_config['dictionary'])
    with open(dictionary_path, 'w') as dictionary_file:
        for word in sorted(words_needed):
            for i, pronounce in enumerate(word_dict[word]):
                if i < 1:
                    print(word, pronounce, file=dictionary_file)
                else:
                    print('%s(%s)' % (word, i+1), pronounce, file=dictionary_file)

    logging.debug('Wrote %s word(s) to %s' % (len(words_needed), dictionary_path))

    # Repeat sentences so that all intents will contain the same number
    balance_sentences = profile.training.get('balance_sentences', True)
    if balance_sentences:
        # Use least common multiple
        lcm_sentences = utils.lcm(*(len(sents) for sents
                                    in sentences_by_intent.values()))
    else:
        lcm_sentences = 0  # no repeats

    # Write sentences to text file
    sentences_text_path = profile.write_path(stt_config['sentences_text'])
    with open(sentences_text_path, 'w') as sentences_text_file:
        num_sentences = 0
        for intent_name, intent_sents in sentences_by_intent.items():
            num_repeats = max(1, lcm_sentences // len(intent_sents))
            for sentence, slots in intent_sents:
                for i in range(num_repeats):
                    print(sentence, file=sentences_text_file)
                    num_sentences = num_sentences + 1

    logging.debug('Wrote %s sentence(s) to %s' % (num_sentences, sentences_text_path))

    # Generate ARPA language model
    lm = train_speech_recognizer(profile)

    # Save to profile
    lm_path = profile.write_path(ps_config['language_model'])
    with open(lm_path, 'w') as lm_file:
        lm_file.write(lm)

    # Expand sentences for intent recognizer
    intent_system = profile.intent.get('system', 'fuzzywuzzy')

    if intent_system == 'rasa':
        rasa_config = profile.intent[intent_system]

        # Use rasaNLU
        examples_md_path = profile.write_path(rasa_config['examples_markdown'])
        with open(examples_md_path, 'w') as examples_md_file:
            for intent_name, intent_sents in tagged_sentences.items():
                # Rasa Markdown training format
                print('## intent:%s' % intent_name, file=examples_md_file)
                for intent_sent in intent_sents:
                    print('-', intent_sent, file=examples_md_file)

                print('', file=examples_md_file)

        # Train rasaNLU
        project_dir = profile.write_dir(rasa_config['project_dir'])
        project_name = rasa_config['project_name']
        rasa_config_path = profile.read_path(rasa_config['config'])

        train_intent_recognizer(examples_md_path, rasa_config_path,
                                project_dir, project_name)
    else:
        fuzzy_config = profile.intent[intent_system]

        # Use fuzzywuzzy
        examples_path = profile.write_path(fuzzy_config['examples_json'])
        examples = intent.make_examples(profile, sentences_by_intent)
        with open(examples_path, 'w') as examples_file:
            json.dump(examples, examples_file, indent=4)


# -----------------------------------------------------------------------------

def train_speech_recognizer(profile):
    sentences_text_path = profile.read_path(
        profile.speech_to_text['sentences_text'])

    # Extract file name only (will be made relative to container path)
    sentences_text_path = os.path.split(sentences_text_path)[1]
    working_dir = profile.write_dir()

    # Generate symbols
    subprocess.check_call(['ngramsymbols',
                           sentences_text_path,
                           'sentences.syms'],
                          cwd=working_dir)

    # Convert to archive (FAR)
    subprocess.check_call(['farcompilestrings',
                           '-symbols=sentences.syms',
                           '-keep_symbols=1',
                           sentences_text_path,
                           'sentences.far'],
                          cwd=working_dir)

    # Generate trigram counts
    subprocess.check_call(['ngramcount',
                           '-order=3',
                           'sentences.far',
                           'sentences.cnts'],
                          cwd=working_dir)

    # Create trigram model
    subprocess.check_call(['ngrammake',
                           'sentences.cnts',
                           'sentences.mod'],
                          cwd=working_dir)

    # Convert to ARPA format
    subprocess.check_call(['ngramprint',
                           '--ARPA',
                           'sentences.mod',
                           'sentences.arpa'],
                          cwd=working_dir)

    # Return ARPA language model
    with open(os.path.join(working_dir, 'sentences.arpa'), 'r') as arpa_file:
        return arpa_file.read()

# -----------------------------------------------------------------------------

def sanitize_sentence(sentence, training_config):
    # Tokenize with spaCy, remove punctuation
    # tokens = [t for t in nlp(sentence) if not t.is_punct]

    # Re-join tokens
    # return ' '.join(t.lower_ for t in tokens), tokens

    sentence_casing = training_config.get('sentence_casing', None)
    if sentence_casing == 'lower':
        sentence = sentence.lower()
    elif sentence_casing == 'upper':
        sentence = sentence.upper()

    tokenizer = training_config.get('tokenizer', 'regex')

    if tokenizer == 'regex':
        regex_config = training_config[tokenizer]

        # Process replacement patterns
        for repl_dict in regex_config.get('replace', []):
            for pattern, repl in repl_dict.items():
                sentence = re.sub(pattern, repl, sentence)

        # Tokenize
        split_pattern = regex_config.get('split', r'\s+')
        tokens = [t for t in re.split(split_pattern, sentence)
                  if len(t.strip()) > 0]
    else:
        assert False, 'Unknown tokenizer: %s' % tokenizer

    return sentence, tokens

# -----------------------------------------------------------------------------

def train_intent_recognizer(examples_file, rasa_config,
                            project_dir, project_name,
                            num_threads=4):
    import rasa_nlu
    from rasa_nlu.train import do_train

    # Run the actual training
    do_train(cfg=rasa_nlu.config.load(rasa_config),
             data=examples_file,
             path=project_dir,
             project=project_name,
             num_threads=num_threads)
