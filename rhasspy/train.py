import os
import configparser
import subprocess
import logging
import concurrent.futures
from collections import defaultdict
from typing import TextIO, Dict, List, Tuple

from profiles import Profile

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class SentenceGenerator:
    '''Base class for all sentence generators.'''

    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def preload(self):
        '''Cache important stuff up front.'''
        pass

    def generate_sentences(self) -> Dict[str, List[str]]:
        '''Generate tagged sentences with Markdown-style entities.
        Returns tagged sentences grouped by intent.'''
        pass

# -----------------------------------------------------------------------------
# jsgf-gen based sentence generator
# https://github.com/synesthesiam/jsgf-gen
# -----------------------------------------------------------------------------

class JsgfSentenceGenerator(SentenceGenerator):
    '''Uses jsgf-gen to generate sentences.'''

    def generate_sentences(self):
        ini_path = self.profile.read_path(
            self.profile.get('speech_to_text.sentences_ini'))

        grammars_dir = self.profile.write_dir(
            self.profile.get('speech_to_text.grammars_dir'))

        with open(ini_path, 'r') as ini_file:
            grammar_paths = self._make_grammars(ini_file, grammars_dir)

        # intent -> sentence templates
        tagged_sentences: Dict[str, List[str]] = defaultdict(list)

        def generate(path):
            cmd = ['jsgf-gen',
                  '--grammar', path,
                  '--exhaustive',
                  '--tags']

            logger.debug(cmd)
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

        num_sentences = sum(len(s) for s in tagged_sentences.values())
        logger.debug('Generated %s sentence(s) in %s intent(s)' % (num_sentences, len(tagged_sentences)))

        return tagged_sentences

    # -------------------------------------------------------------------------

    def _make_grammars(self, ini_file: TextIO, grammar_dir: str) -> Dict[str, str]:
        '''Create JSGF grammars for each intent from sentence ini file.
        Returns paths to all generated grammars (name -> path).'''
        config = configparser.ConfigParser(
            allow_no_value=True,
            strict=False,
            delimiters=['='])

        config.optionxform = lambda x: str(x) # case sensitive
        config.read_file(ini_file)

        os.makedirs(grammar_dir, exist_ok=True)

        # Process configuration sections
        grammar_rules = {}

        for sec_name in config.sections():
            sentences: List[str] = []
            rules: List[str] = []
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

            # Only overwrite grammar file if it contains rules or doesn't yet exist
            if (len(rules) > 0) or not os.path.exists(grammar_path):
                with open(grammar_path, 'w') as grammar_file:
                    # JSGF header
                    print('#JSGF V1.0;', file=grammar_file)
                    print('grammar {0};'.format(name), file=grammar_file)
                    print('', file=grammar_file)

                    # Grammar rules
                    for rule in rules:
                        print(rule, file=grammar_file)

            grammar_paths[name] = grammar_path

        return grammar_paths
