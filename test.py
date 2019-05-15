import os
import json
import tempfile
import unittest
import logging

logging.basicConfig(level=logging.DEBUG)

from rhasspy.core import RhasspyCore

class RhasspyTestCore:
    def __init__(self, profile_name, train=True):
        self.profile_name = profile_name
        self.system_profiles_dir = os.path.join(os.getcwd(), "profiles")
        self.train = train

    def __enter__(self):
        self.user_profiles_dir = tempfile.TemporaryDirectory()
        self.core = RhasspyCore(
            self.profile_name,
            self.system_profiles_dir,
            self.user_profiles_dir.name,
            do_logging=False,
        )
        self.core.profile.set("wake.system", "dummy")
        self.core.start(preload=False)
        self.core.train()


        if self.train:
            self.core.train()

        return self.core

    def __exit__(self, *args):
        self.core.shutdown()
        try:
            self.user_profiles_dir.cleanup()
        except:
            pass

# -----------------------------------------------------------------------------

PROFILES = ["en", "de"]

class RhasspyTestCase(unittest.TestCase):

    def test_transcribe(self):
        """speech -> text"""
        for profile_name in PROFILES:
            with RhasspyTestCore(profile_name) as core:
                test_dir = os.path.join("etc", "test", profile_name)
                wav_path = os.path.join(test_dir, "test.wav")
                json_path = os.path.join(test_dir, "test.json")

                with open(json_path, "r") as json_file:
                    wav_info = json.load(json_file)

                with open(wav_path, "rb") as wav_file:
                    text = core.transcribe_wav(wav_file.read()).text
                    self.assertEqual(text, wav_info["text"])

    # -------------------------------------------------------------------------

    # def test_recognize(self):
    #     """text -> intent"""
    #     intent = self.core.recognize_intent("turn on the living room lamp").intent
    #     self.assertEqual(intent["intent"]["name"], "ChangeLightState")
    #     entities = {e["entity"]: e["value"] for e in intent["entities"]}
    #     self.assertEqual(entities["name"], "living room lamp")
    #     self.assertEqual(entities["state"], "on")

    # -------------------------------------------------------------------------

    # def test_training(self):
    #     """Test training"""
    #     profile_name = "en"
    #     with tempfile.TemporaryDirectory(prefix="rhasspy_") as temp_user_dir:
    #         core = RhasspyCore(
    #             profile_name, self.system_profiles_dir, temp_user_dir, do_logging=True
    #         )
    #         core.profile.set("rhasspy.listen_on_start", False)
    #         core.profile.set("rhasspy.preload_profile", False)
    #         core.start()

    #         sentences_path = core.profile.write_path(
    #             core.profile.get("speech_to_text.sentences_ini")
    #         )

    #         with open(sentences_path, "w") as sentences_file:
    #             print("[Foo]", file=sentences_file)
    #             print("foo bar", file=sentences_file)
    #             print("foo bar baz", file=sentences_file)

    #         core.train()
    #         with open("etc/test/what_time_is_it.wav", "rb") as wav_file:
    #             text = core.transcribe_wav(wav_file.read()).text
    #             self.assertNotEqual(text, "what time is it")

    #         # Add some more sentences
    #         with open(sentences_path, "a") as sentences_file:
    #             print("", file=sentences_file)
    #             print("[GetTime]", file=sentences_file)
    #             print("what time is it", file=sentences_file)

    #         core.train()
    #         with open("etc/test/what_time_is_it.wav", "rb") as wav_file:
    #             text = core.transcribe_wav(wav_file.read()).text
    #             self.assertEqual(text, "what time is it")

    # -------------------------------------------------------------------------

    # def test_pronounce(self):
    #     # Known word
    #     pronunciations = self.core.get_word_pronunciations(["test"], n=1).pronunciations
    #     self.assertEqual(pronunciations["test"]["pronunciations"][0], "T EH S T")

    #     # Unknown word
    #     pronunciations = self.core.get_word_pronunciations(
    #         ["raxacoricofallipatorius"], n=1
    #     ).pronunciations
    #     self.assertIn(
    #         "R AE K S AH K AO R IH K AO F AE L AH P AH T AO R IY IH S",
    #         pronunciations["raxacoricofallipatorius"]["pronunciations"],
    #     )


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
