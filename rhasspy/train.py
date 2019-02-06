import os
import re
import configparser
import subprocess
import itertools
import logging
import concurrent.futures
from collections import defaultdict
from typing import TextIO, Dict, List, Tuple, Any, Optional

from thespian.actors import ActorAddress

from .actor import RhasspyActor
from .profiles import Profile

# -----------------------------------------------------------------------------

class GenerateSentences:
    def __init__(self,
                 receiver:Optional[ActorAddress]=None) -> None:
        self.receiver = receiver

class SentencesGenerated:
    def __init__(self,
                 tagged_sentences: Dict[str, List[str]]) -> None:
        self.tagged_sentences = tagged_sentences

# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# jsgf-gen based sentence generator
# https://github.com/synesthesiam/jsgf-gen
# -----------------------------------------------------------------------------

class JsgfSentenceGenerator(RhasspyActor):
    '''Uses jsgf-gen to generate sentences.'''

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, GenerateSentences):
            tagged_sentences = self.generate_sentences()
            self.send(message.receiver or sender,
                      SentencesGenerated(tagged_sentences))

    # -------------------------------------------------------------------------

    def generate_sentences(self) -> Dict[str, List[str]]:
        ini_path = self.profile.read_path(
            self.profile.get('speech_to_text.sentences_ini'))

        grammars_dir = self.profile.write_dir(
            self.profile.get('speech_to_text.grammars_dir'))

        with open(ini_path, 'r') as ini_file:
            grammar_paths = self._make_grammars(ini_file, grammars_dir)

        # intent -> sentence templates
        tagged_sentences: Dict[str, List[str]] = defaultdict(list)

        # Ready slots values
        slots_dir = self.profile.write_dir(
            self.profile.get('speech_to_text.slots_dir'))

        # colors -> [red, green, blue]
        slot_values = {}
        if os.path.exists(slots_dir):
            for slot_file_name in os.listdir(slots_dir):
                slot_path = os.path.join(slots_dir, slot_file_name)
                if os.path.isfile(slot_path):
                    slot_name = os.path.splitext(slot_file_name)[0]
                    values = []
                    with open(slot_path, 'r') as slot_file:
                        for line in slot_file:
                            line = line.strip()
                            if len(line) > 0:
                                values.append(line)

                    slot_values[slot_name] = values

        print(slot_values)

        # Generate sentences concurrently
        with concurrent.futures.ProcessPoolExecutor() as executor:
            future_to_name = { executor.submit(_jsgf_generate, path, slot_values) : name
                               for name, path in grammar_paths.items() }

            # Add to the list as they get done
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                tagged_sentences[name] = future.result()

        num_sentences = sum(len(s) for s in tagged_sentences.values())
        self._logger.debug('Generated %s sentence(s) in %s intent(s)' % (num_sentences, len(tagged_sentences)))

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

# -----------------------------------------------------------------------------

def _jsgf_generate(path, slot_values) -> List[str]:
    cmd = ['jsgf-gen',
            '--grammar', path,
            '--exhaustive',
            '--tags']

    logging.debug(cmd)

    # Generate sentences
    sentences = []
    for sentence in subprocess.check_output(cmd).decode().splitlines():
        # Check for template replacements ($name$)
        if '$' in sentence:
            chunks = re.split(r'\$([^$]+)\$', sentence)
            replacements = []
            for i, chunk in enumerate(chunks):
                if ((i % 2) != 0) and (chunk in slot_values):
                    replacements.append(slot_values[chunk])
                else:
                    replacements.append([chunk])

            # Create all combinations of replacements
            for replacement in itertools.product(*replacements):
                sentences.append(''.join(replacement))
        else:
            # No replacements
            sentences.append(sentence)

    return sentences
