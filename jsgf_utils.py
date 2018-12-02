import os
import configparser
import subprocess
import logging
import concurrent.futures
from collections import defaultdict

def make_grammars(ini_file, grammar_dir):
    config = configparser.ConfigParser(
        allow_no_value=True,
        strict=False,
        delimiters=['='])

    config.optionxform = str # case sensitive
    config.read_file(ini_file)

    os.makedirs(grammar_dir, exist_ok=True)

    # Process configuration sections
    grammar_rules = {}

    for sec_name in config.sections():
        sentences = []
        rules = []
        for k, v in config[sec_name].items():
            if v is None:
                # Collect non-valued keys as sentences
                sentences.append('({0})'.format(k.strip()))
            else:
                # Collect key/value pairs as JSGF rules
                rule = '<{0}> = ({1});'.format(k, v)
                rules.append(rule)

        if len(sentences) > 0:
            # Combine all sentences into one big rule (same name as section)
            sentences_rule = 'public <{0}> = ({1});'.format(sec_name, ' | '.join(sentences))
            rules.insert(0, sentences_rule)

        grammar_rules[sec_name] = rules

    # Write JSGF grammars
    grammar_paths = {}
    for name, rules in grammar_rules.items():
        grammar_path = os.path.join(grammar_dir, '{0}.gram'.format(name))
        with open(grammar_path, 'w') as grammar_file:
            print('#JSGF V1.0;', file=grammar_file)
            print('grammar {0};'.format(name), file=grammar_file)
            print('', file=grammar_file)

            for rule in rules:
                print(rule, file=grammar_file)

        grammar_paths[name] = grammar_path

    return grammar_paths

def generate_sentences(grammar_paths):
    tagged_sentences = defaultdict(list)

    def generate(path):
        cmd = ['jsgf-gen',
               '--grammar', path,
               '--exhaustive',
               '--tags']

        logging.debug(cmd)
        return subprocess.check_output(cmd)\
                         .decode()\
                         .splitlines()

    # Generate sentences concurrently
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_name = { executor.submit(generate, path) : name
                           for name, path in grammar_paths.items() }

        # Add to the list as they get done
        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            tagged_sentences[name] = future.result()

    return tagged_sentences
