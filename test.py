import tempfile
import unittest
import logging

logging.basicConfig(level=logging.DEBUG)

from rhasspy.core import RhasspyCore


class RhasspyTestCase(unittest.TestCase):
    def setUp(self):
        profile_name = "en"
        profiles_dirs = ["profiles"]
        self.core = RhasspyCore(profile_name, profiles_dirs, do_logging=False)
        self.core.profile.set("wake.system", "dummy")
        self.core.start()

    def tearDown(self):
        self.core.shutdown()

    # -------------------------------------------------------------------------

    def test_transcribe(self):
        """speech -> text"""
        with open("etc/test/turn_on_living_room_lamp.wav", "rb") as wav_file:
            text = self.core.transcribe_wav(wav_file.read()).text
            assert text == "turn on the living room lamp", text

    # -------------------------------------------------------------------------

    def test_recognize(self):
        """text -> intent"""
        intent = self.core.recognize_intent("turn on the living room lamp").intent
        assert intent["intent"]["name"] == "ChangeLightState", intent["intent"]["name"]
        entities = {e["entity"]: e["value"] for e in intent["entities"]}
        assert entities["name"] == "living room lamp", entities["name"]
        assert entities["state"] == "on", entities["state"]

    # -------------------------------------------------------------------------

    def test_training(self):
        """Test training"""
        profile_name = "en"
        with tempfile.TemporaryDirectory(prefix="rhasspy_") as temp_dir:
            profiles_dirs = [temp_dir, "profiles"]
            core = RhasspyCore(profile_name, profiles_dirs, do_logging=True)
            core.profile.set("rhasspy.listen_on_start", False)
            core.profile.set("rhasspy.preload_profile", False)
            core.start()

            sentences_path = core.profile.write_path(
                core.profile.get("speech_to_text.sentences_ini")
            )

            with open(sentences_path, "w") as sentences_file:
                print("[Foo]", file=sentences_file)
                print("foo bar", file=sentences_file)
                print("foo bar baz", file=sentences_file)

            core.train()
            with open("etc/test/what_time_is_it.wav", "rb") as wav_file:
                text = core.transcribe_wav(wav_file.read()).text
                assert text != "what time is it", text

            # Add some more sentences
            with open(sentences_path, "a") as sentences_file:
                print("", file=sentences_file)
                print("[GetTime]", file=sentences_file)
                print("what time is it", file=sentences_file)

            core.train()
            with open("etc/test/what_time_is_it.wav", "rb") as wav_file:
                text = core.transcribe_wav(wav_file.read()).text
                assert text == "what time is it"

    # -------------------------------------------------------------------------

    def test_pronounce(self):
        # Known word
        pronunciations = self.core.get_word_pronunciations(["test"], n=1).pronunciations
        assert pronunciations["test"]["pronunciations"][0] == "T EH S T"

        # Unknown word
        pronunciations = self.core.get_word_pronunciations(
            ["raxacoricofallipatorius"], n=1
        ).pronunciations
        assert (
            "R AE K S AH K AO R IH K AO F AE L AH P AH T AO R IY IH S"
            in pronunciations["raxacoricofallipatorius"]["pronunciations"]
        )


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
