#!/usr/bin/env python3
import io
import os
import re
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import Iterable, List, Tuple

from num2words import num2words
import pywrapfst as fst

from doit import create_after
from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain
from doit.reporter import ConsoleReporter

from rhasspynlu import (
    parse_ini,
    intents_to_graph,
    graph_to_fst,
    graph_to_json,
    json_to_graph,
    jsgf,
    ini_jsgf,
)

from rhasspy.train.vocab_dict import make_dict, FORMAT_CMU, FORMAT_JULIUS
from rhasspy.profiles import Profile
from rhasspy.utils import (
    ppath as utils_ppath,
    read_dict,
    get_ini_paths,
    get_all_intents,
)

_LOGGER = logging.getLogger("train")

# -----------------------------------------------------------------------------


def train_profile(profile_dir: Path, profile: Profile) -> Tuple[int, List[str]]:

    # Compact
    def ppath(query, default=None, write=False):
        return utils_ppath(profile, profile_dir, query, default, write=write)

    language = profile.get("language", "")

    # Inputs
    stt_system = profile.get("speech_to_text.system")
    stt_prefix = f"speech_to_text.{stt_system}"

    # intent_whitelist = ppath("training.intent-whitelist", "intent_whitelist")
    sentences_ini = ppath("speech_to_text.sentences_ini", "sentences.ini")
    sentences_dir = ppath("speech_to_text.sentences_dir", "sentences.dir")
    base_dictionary = ppath(f"{stt_prefix}.base_dictionary", "base_dictionary.txt")
    base_language_model = ppath(
        f"{stt_prefix}.base_language_model", "base_language_model.txt"
    )
    base_language_model_weight = float(profile.get(f"{stt_prefix}.mix_weight", 0))
    g2p_model = ppath(f"{stt_prefix}.g2p_model", "g2p.fst")
    acoustic_model_type = stt_system

    # Pocketsphinx
    acoustic_model = ppath(f"{stt_prefix}.acoustic_model", "acoustic_model")

    # Kaldi
    kaldi_dir = Path(
        os.path.expandvars(profile.get(f"{stt_prefix}.kaldi_dir", "/opt/kaldi"))
    )
    kaldi_graph_dir = acoustic_model / profile.get(f"{stt_prefix}.graph", "graph")

    if acoustic_model_type == "kaldi":
        # Kaldi acoustic models are inside model directory
        acoustic_model = ppath(f"{stt_prefix}.model_dir", "model")
    else:
        _LOGGER.warning("Unsupported acoustic model type: %s", acoustic_model_type)

    # ignore/upper/lower
    word_casing = profile.get("speech_to_text.dictionary_casing", "ignore").lower()

    # default/ignore/upper/lower
    g2p_word_casing = profile.get("speech_to_text.g2p_casing", word_casing).lower()

    # all/first
    dict_merge_rule = profile.get("speech_to_text.dictionary_merge_rule", "all").lower()

    # Outputs
    dictionary = ppath(f"{stt_prefix}.dictionary", "dictionary.txt", write=True)
    custom_words = ppath(f"{stt_prefix}.custom_words", "custom_words.txt", write=True)
    language_model = ppath(
        f"{stt_prefix}.language_model", "language_model.txt", write=True
    )
    base_language_model_fst = ppath(
        f"{stt_prefix}.base_language_model_fst", "base_language_model.fst", write=True
    )
    intent_graph = ppath("intent.fsticiffs.intent_graph", "intent.json", write=True)
    intent_fst = ppath("intent.fsticiffs.intent_fst", "intent.fst", write=True)
    vocab = ppath(f"{stt_prefix}.vocabulary", "vocab.txt", write=True)
    unknown_words = ppath(
        f"{stt_prefix}.unknown_words", "unknown_words.txt", write=True
    )
    grammar_dir = ppath("speech_to_text.grammars_dir", "grammars", write=True)
    fsts_dir = ppath("speech_to_text.fsts_dir", "fsts", write=True)
    slots_dir = ppath("speech_to_text.slots_dir", "slots", write=True)

    # -----------------------------------------------------------------------------

    # Create cache directories
    for dir_path in [grammar_dir, fsts_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------------

    ini_paths: List[Path] = get_ini_paths(sentences_ini, sentences_dir)

    # Join ini files into a single combined file and parse
    _LOGGER.debug("Parsing ini file(s): %s", [str(p) for p in ini_paths])

    try:
        intents = get_all_intents(ini_paths)
    except Exception:
        _LOGGER.exception("Failed to parse %s", ini_paths)
        return (1, ["Failed to parse sentences"])

    # -----------------------------------------------------------------------------

    def get_slot_names(item):
        """Yield referenced slot names."""
        if isinstance(item, jsgf.SlotReference):
            yield item.slot_name
        elif isinstance(item, jsgf.Sequence):
            for sub_item in item.items:
                for slot_name in get_slot_names(sub_item):
                    yield slot_name
        elif isinstance(item, jsgf.Rule):
            for slot_name in get_slot_names(item.rule_body):
                yield slot_name

    def number_transform(word):
        """Automatically transform numbers"""
        if not isinstance(word, jsgf.Word):
            # Skip anything besides words
            return

        try:
            n = int(word.text)

            # 75 -> (seventy five):75
            number_text = num2words(n, lang=language).replace("-", " ").strip()
            assert number_text, f"Empty num2words result for {n}"
            number_words = number_text.split()

            if len(number_words) == 1:
                # Easy case, single word
                word.text = number_text
                word.substitution = str(n)
            else:
                # Hard case, split into mutliple Words
                return jsgf.Sequence(
                    text=number_text,
                    type=jsgf.SequenceType.GROUP,
                    substitution=str(n),
                    items=[jsgf.Word(w) for w in number_words],
                )
        except ValueError:
            # Not a number
            pass

    def do_intents_to_graph(intents, slot_names, targets):
        sentences, replacements = ini_jsgf.split_rules(intents)

        # Load slot values
        for slot_name in slot_names:
            slot_path = slots_dir / slot_name
            assert slot_path.is_file(), f"Missing slot file at {slot_path}"

            # Parse each non-empty line as a JSGF sentence
            slot_values = []
            with open(slot_path, "r") as slot_file:
                for line in slot_file:
                    line = line.strip()
                    if line:
                        sentence = jsgf.Sentence.parse(line)
                        slot_values.append(sentence)

            # Replace $slot with sentences
            replacements[f"${slot_name}"] = slot_values

        if profile.get("intent.replace_numbers", True):
            # Replace numbers in parsed sentences
            for intent_sentences in sentences.values():
                for sentence in intent_sentences:
                    jsgf.walk_expression(sentence, number_transform, replacements)

        # Convert to directed graph
        graph = intents_to_graph(intents, replacements)

        # Write graph to JSON file
        json_graph = graph_to_json(graph)
        with open(targets[0], "w") as graph_file:
            json.dump(json_graph, graph_file)

    def task_ini_graph():
        """sentences.ini -> intent.json"""
        slot_names = set()
        for intent_name in intents:
            for item in intents[intent_name]:
                for slot_name in get_slot_names(item):
                    slot_names.add(slot_name)

        # Add slot files as dependencies
        deps = [(slots_dir / slot_name) for slot_name in slot_names]

        # Add profile itself as a dependency
        profile_json_path = profile_dir / "profile.json"
        if profile_json_path.is_file():
            deps.append(profile_json_path)

        return {
            "file_dep": ini_paths + deps,
            "targets": [intent_graph],
            "actions": [(do_intents_to_graph, [intents, slot_names])],
        }

    # -----------------------------------------------------------------------------

    def do_graph_to_fst(intent_graph, targets):
        with open(intent_graph, "r") as graph_file:
            json_graph = json.load(graph_file)

        graph = json_to_graph(json_graph)
        graph_fst = graph_to_fst(graph)

        # Create symbol tables
        isymbols = fst.SymbolTable()
        for symbol, number in graph_fst.input_symbols.items():
            isymbols.add_symbol(symbol, number)

        osymbols = fst.SymbolTable()
        for symbol, number in graph_fst.output_symbols.items():
            osymbols.add_symbol(symbol, number)

        # Compile FST
        compiler = fst.Compiler(
            isymbols=isymbols, osymbols=osymbols, keep_isymbols=True, keep_osymbols=True
        )

        compiler.write(graph_fst.intent_fst)
        compiled_fst = compiler.compile()

        # Write to file
        compiled_fst.write(str(targets[0]))

    def task_intent_fst():
        """intent.json -> intent.fst"""
        return {
            "file_dep": [intent_graph],
            "targets": [intent_fst],
            "actions": [(do_graph_to_fst, [intent_graph])],
        }

    # -----------------------------------------------------------------------------

    @create_after(executed="intent_fst")
    def task_language_model():
        """Creates an ARPA language model from intent.fst."""

        if base_language_model_weight > 0:
            yield {
                "name": "base_lm_to_fst",
                "file_dep": [base_language_model],
                "targets": [base_language_model_fst],
                "actions": ["ngramread --ARPA %(dependencies)s %(targets)s"],
            }

        # FST -> n-gram counts
        intent_counts = str(intent_fst) + ".counts"
        yield {
            "name": "intent_counts",
            "file_dep": [intent_fst],
            "targets": [intent_counts],
            "actions": ["ngramcount %(dependencies)s %(targets)s"],
        }

        # n-gram counts -> model
        intent_model = str(intent_fst) + ".model"
        yield {
            "name": "intent_model",
            "file_dep": [intent_counts],
            "targets": [intent_model],
            "actions": ["ngrammake %(dependencies)s %(targets)s"],
        }

        if base_language_model_weight > 0:
            merged_model = Path(str(intent_model) + ".merge")

            # merge
            yield {
                "name": "lm_merge",
                "file_dep": [base_language_model_fst, intent_model],
                "targets": [merged_model],
                "actions": [
                    f"ngrammerge --alpha={base_language_model_weight} %(dependencies)s %(targets)s"
                ],
            }

            intent_model = merged_model

        # model -> ARPA
        yield {
            "name": "intent_arpa",
            "file_dep": [intent_model],
            "targets": [language_model],
            "actions": ["ngramprint --ARPA %(dependencies)s > %(targets)s"],
        }

    # -----------------------------------------------------------------------------

    def do_vocab(targets):
        with open(targets[0], "w") as vocab_file:
            input_symbols = fst.Fst.read(str(intent_fst)).input_symbols()
            for i in range(input_symbols.num_symbols()):
                # Critical that we use get_nth_key here when input symbols
                # numbering is discontiguous.
                key = input_symbols.get_nth_key(i)
                symbol = input_symbols.find(key).decode().strip()
                if symbol and not (symbol.startswith("__") or symbol.startswith("<")):
                    print(symbol, file=vocab_file)

            if base_language_model_weight > 0:
                # Add all words from base dictionary
                with open(base_dictionary, "r") as dict_file:
                    for word in read_dict(dict_file):
                        print(word, file=vocab_file)

    @create_after(executed="language_model")
    def task_vocab():
        """Writes all vocabulary words to a file from intent.fst."""
        return {"file_dep": [intent_fst], "targets": [vocab], "actions": [do_vocab]}

    # -----------------------------------------------------------------------------

    def do_dict(dictionary_paths: Iterable[Path], targets):
        with open(targets[0], "w") as dictionary_file:
            if unknown_words.exists():
                unknown_words.unlink()

            dictionary_format = FORMAT_CMU
            if acoustic_model_type == "julius":
                dictionary_format = FORMAT_JULIUS

            make_dict(
                vocab,
                dictionary_paths,
                dictionary_file,
                unknown_path=unknown_words,
                dictionary_format=dictionary_format,
                merge_rule=dict_merge_rule,
                upper=(word_casing == "upper"),
                lower=(word_casing == "lower"),
            )

            if unknown_words.exists() and g2p_model.exists():
                # Generate single pronunciation guesses
                _LOGGER.debug("Guessing pronunciations for unknown word(s)")

                g2p_output = subprocess.check_output(
                    [
                        "phonetisaurus-apply",
                        "--model",
                        str(g2p_model),
                        "--word_list",
                        str(unknown_words),
                        "--nbest",
                        "1",
                    ],
                    universal_newlines=True,
                )

                g2p_transform = lambda w: w
                if g2p_word_casing == "upper":
                    g2p_transform = lambda w: w.upper()
                elif g2p_word_casing == "lower":
                    g2p_transform = lambda w: w.lower()

                # Append to dictionary and custom words
                with open(custom_words, "a") as words_file:
                    with open(unknown_words, "w") as unknown_words_file:
                        for line in g2p_output.splitlines():
                            line = line.strip()
                            word, phonemes = re.split(r"\s+", line, maxsplit=1)
                            word = g2p_transform(word)
                            print(word, phonemes, file=dictionary_file)
                            print(word, phonemes, file=words_file)
                            print(word, phonemes, file=unknown_words_file)

    @create_after(executed="vocab")
    def task_vocab_dict():
        """Creates custom pronunciation dictionary based on desired vocabulary."""
        dictionary_paths = [base_dictionary]
        if custom_words.exists():
            # Custom dictionary goes first so that the "first" dictionary merge
            # rule will choose pronunciations from it.
            dictionary_paths.insert(0, custom_words)

        # Exclude dictionaries that don't exist
        dictionary_paths = [p for p in dictionary_paths if p.exists()]

        return {
            "file_dep": [vocab] + dictionary_paths,
            "targets": [dictionary],
            "actions": [(do_dict, [dictionary_paths])],
        }

    # -----------------------------------------------------------------------------

    @create_after(executed="vocab_dict")
    def task_kaldi_train():
        """Creates HCLG.fst for a Kaldi nnet3 or gmm model."""
        if acoustic_model_type == "kaldi":
            return {
                "file_dep": [dictionary, language_model],
                "targets": [kaldi_graph_dir / "HCLG.fst"],
                "actions": [
                    [
                        "bash",
                        str(acoustic_model / "train.sh"),
                        str(kaldi_dir),
                        str(acoustic_model),
                        str(dictionary),
                        str(language_model),
                    ]
                ],
            }

    # -----------------------------------------------------------------------------

    errors = []

    class MyReporter(ConsoleReporter):
        def add_failure(self, task, exception):
            super().add_failure(task, exception)
            errors.append(f"{task}: {exception}")

        def runtime_error(self, msg):
            super().runtime_error(msg)
            errors.append(msg)

    DOIT_CONFIG = {"action_string_formatting": "old", "reporter": MyReporter}

    # Monkey patch inspect to make doit work inside Pyinstaller.
    # It grabs the line numbers of functions probably for debugging reasons, but
    # PyInstaller doesn't seem to keep that information around.
    #
    # This better thing to do would be to create a custom TaskLoader.
    import inspect

    inspect.getsourcelines = lambda obj: [0, 0]

    # Run doit main
    result = DoitMain(ModuleTaskLoader(locals())).run(sys.argv[1:])
    return (result, errors)
