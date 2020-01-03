"""Support for playing sounds."""
import os
import re
import subprocess
import uuid
from typing import Any, Dict, List, Optional, Type

from rhasspy.actor import RhasspyActor
from rhasspy.events import MqttPublish, PlayWavData, PlayWavFile, WavPlayed

# -----------------------------------------------------------------------------


def get_sound_class(system: str) -> Type[RhasspyActor]:
    """Get class type for profile audio player."""
    assert system in ["aplay", "hermes", "dummy"], f"Unknown sound system: {system}"

    if system == "aplay":
        return APlayAudioPlayer

    if system == "hermes":
        return HermesAudioPlayer

    return DummyAudioPlayer


# -----------------------------------------------------------------------------
# Dummy audio player
# -----------------------------------------------------------------------------


class DummyAudioPlayer(RhasspyActor):
    """Does not play sound. Responds immediately with WavPlayed."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, (PlayWavFile, PlayWavData)):
            self.send(message.receiver or sender, WavPlayed())

    @classmethod
    def get_speakers(cls) -> Dict[Any, Any]:
        """Get list of possible audio output devices."""
        return {}


# -----------------------------------------------------------------------------
# APlay based audio player
# -----------------------------------------------------------------------------


class APlayAudioPlayer(RhasspyActor):
    """Plays WAV files using aplay command."""

    def __init__(self):
        super().__init__()
        self.device: Optional[str] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.device = self.config.get("device") or self.profile.get(
            "sounds.aplay.device"
        )

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, PlayWavFile):
            self.play_file(message.wav_path)
            self.send(message.receiver or sender, WavPlayed())
        elif isinstance(message, PlayWavData):
            self.play_data(message.wav_data)
            self.send(message.receiver or sender, WavPlayed())

    # -------------------------------------------------------------------------

    def play_file(self, path: str) -> None:
        """Play a WAV file using aplay."""
        if not os.path.exists(path):
            self._logger.warning("Path does not exist: %s", path)
            return

        aplay_cmd = ["aplay", "-q"]

        if self.device is not None:
            aplay_cmd.extend(["-D", str(self.device)])

        # Play file
        aplay_cmd.append(path)

        self._logger.debug(aplay_cmd)
        subprocess.run(aplay_cmd, check=True)

    def play_data(self, wav_data: bytes) -> None:
        """Play a WAV buffer using aplay."""
        aplay_cmd = ["aplay", "-q"]

        if self.device is not None:
            aplay_cmd.extend(["-D", str(self.device)])

        self._logger.debug(aplay_cmd)

        # Play data
        subprocess.run(aplay_cmd, input=wav_data, check=True)

    # -------------------------------------------------------------------------

    @classmethod
    def get_speakers(cls) -> Dict[Any, Any]:
        """Get list of possible audio output devices."""
        output = subprocess.check_output(["aplay", "-L"]).decode().splitlines()

        speakers: Dict[Any, Any] = {}
        name, description = None, None

        # Parse output of arecord -L
        first_speaker = True
        for line in output:
            line = line.rstrip()
            if re.match(r"^\s", line):
                description = line.strip()
                if first_speaker:
                    description = description + "*"
                    first_speaker = False
            else:
                if name is not None:
                    speakers[name] = description

                name = line.strip()

        return speakers


# -----------------------------------------------------------------------------
# MQTT audio player for Snips.AI Hermes Protocol
# https://docs.snips.ai/reference/hermes
# -----------------------------------------------------------------------------


class HermesAudioPlayer(RhasspyActor):
    """Sends audio data over MQTT via Hermes (Snips) protocol."""

    def __init__(self):
        super().__init__()
        self.mqtt: Optional[RhasspyActor] = None
        self.site_ids: List[str] = []

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.mqtt = self.config["mqtt"]
        self.site_ids = self.profile.get("mqtt.site_id", "default").split(",")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, PlayWavFile):
            self.play_file(message.wav_path)
            self.send(message.receiver or sender, WavPlayed())
        elif isinstance(message, PlayWavData):
            self.play_data(message.wav_data)
            self.send(message.receiver or sender, WavPlayed())

    # -------------------------------------------------------------------------

    def play_file(self, path: str) -> None:
        """Send WAV file over MQTT."""
        if not os.path.exists(path):
            self._logger.warning("Path does not exist: %s", path)
            return

        with open(path, "rb") as wav_file:
            self.play_data(wav_file.read())

    def play_data(self, wav_data: bytes) -> None:
        """Send WAV buffer over MQTT."""
        request_id = str(uuid.uuid4())

        # Send to all site ids
        for site_id in self.site_ids:
            topic = f"hermes/audioServer/{site_id}/playBytes/{request_id}"
            self.send(self.mqtt, MqttPublish(topic, wav_data))

    # -------------------------------------------------------------------------

    @classmethod
    def get_speakers(cls) -> Dict[Any, Any]:
        """Get list of possible audio output devices."""
        return {}
