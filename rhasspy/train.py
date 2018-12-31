from typing import TextIO, Dict, List, Tuple

from profiles import Profile
import generate_jsgf as jsgf

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class SentenceGenerator:
    def generate_sentences(self, sentences_ini: TextIO):
        pass

# -----------------------------------------------------------------------------

class JsgfSentenceGenerator(SentenceGenerator):
    def __init__(self, profile: Profile):
        self.profile = profile

    def generate_sentences(self, sentences_ini: TextIO):
        # Load from ini file and write to examples file
        words_needed = set()
        sentences_by_intent = defaultdict(list)
        grammars_dir = self.profile.write_dir(stt_config['grammars_dir'])

        grammar_paths = jsgf.make_grammars(sentences_ini, grammars_dir)
        logging.debug(grammar_paths)

        # intent -> sentence templates
        return jsgf.generate_sentences(grammar_paths)
