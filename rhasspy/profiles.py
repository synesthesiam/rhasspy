import os
import json
import collections
import logging
from typing import List, Dict, Mapping, Any

import pydash
# from thespian.actors import Actor

# from audio_player import PlayWavFile
import utils

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class Profile:
    def __init__(self,
                 name: str,
                 profiles_dirs: List[str],
                 layers: str ='all') -> None:

        self.name = name
        self.profiles_dirs = profiles_dirs
        self.layers = layers
        self.load_profile()

    # -------------------------------------------------------------------------

    @classmethod
    def load_defaults(cls, profiles_dirs: List[str]):
        for profiles_dir in profiles_dirs:
            defaults_path = os.path.join(profiles_dir, 'defaults.json')
            if os.path.exists(defaults_path):
                with open(defaults_path, 'r') as defaults_file:
                    return json.load(defaults_file)

    # -------------------------------------------------------------------------

    def get(self, path: str, default=None):
        return pydash.get(self.json, path, default)

    # -------------------------------------------------------------------------

    def load_profile(self):
        # Load defaults first
        self.json = {}  # no defaults

        if self.layers in ['all', 'defaults']:
            for profiles_dir in self.profiles_dirs:
                defaults_path = os.path.join(profiles_dir, 'defaults.json')
                if os.path.exists(defaults_path):
                    with open(defaults_path, 'r') as defaults_file:
                        self.json = json.load(defaults_file)
                        break

        # Overlay with profile
        if self.layers in ['all', 'profile']:
            self.json_path = self.read_path('profile.json')
            if os.path.exists(self.json_path):
                with open(self.json_path, 'r') as profile_file:
                    utils.recursive_update(self.json, json.load(profile_file))

    def read_path(self, *path_parts):
        for profiles_dir in self.profiles_dirs:
            # Try to find in the runtime profile first
            full_path = os.path.join(profiles_dir, self.name, *path_parts)

            if os.path.exists(full_path):
                return full_path

        # Use base dir
        return os.path.join('profiles', self.name, path_parts[-1])

    def write_path(self, *path_parts):
        # Try to find in the runtime profile first
        for profiles_dir in self.profiles_dirs:
            full_path = os.path.join(profiles_dir, self.name, *path_parts)

            try:
                dir_path = os.path.split(full_path)[0]
                os.makedirs(dir_path, exist_ok=True)
                return full_path
            except:
                logger.exception('Unable to write to %s' % full_path)

        # Use base dir
        full_path = os.path.join('profiles', self.name, *path_parts)
        dir_path = os.path.split(full_path)[0]
        os.makedirs(dir_path, exist_ok=True)

        return full_path

    def write_dir(self, *dir_parts):
        # Try to find in the runtime profile first
        for profiles_dir in self.profiles_dirs:
            dir_path = os.path.join(profiles_dir, self.name, *dir_parts)

            try:
                os.makedirs(dir_path, exist_ok=True)
                return dir_path
            except:
                logger.exception('Unable to create %s' % dir_path)

        # Use base dir
        dir_path = os.path.join('profiles', self.name, *dir_parts)
        os.makedirs(dir_path, exist_ok=True)

        return dir_path

# -----------------------------------------------------------------------------

# class ProfileActor(Actor):
#     def __init__(self):
#         self.parent = None
#         self.profile = None
#         self.audio_player_actor = None

#     def receiveMessage(self, message, sender):
#         try:
#             if isinstance(message, Profile):
#                 self.parent = sender
#                 self.profile = profile
#             elif isinstance(message, PlayWavFile):
#                 self.maybe_load_audio_player()
#                 self.send(self.audio_player_actor, message)

#         except Exception as ex:
#             logger.exception('receiveMessage')

#     # -------------------------------------------------------------------------

#     def maybe_load_audio_player(self):
#         if self.audio_player_actor is None:
#             system = self.profile.get('sounds.system', 'aplay')
#             assert system in ['aplay'], 'Unknown audio player system'
#             if system == 'aplay':
#                 from .audio_player import APlayActor
#                 self.audio_player_actor = self.createActor(APlayActor)
#                 self.send(self.audio_player_actor, self.profile)

# -----------------------------------------------------------------------------

def request_to_profile(request, profiles_dirs: List[str], layers='all'):
    profile_name = request.args.get(
        'profile', os.environ.get('RHASSPY_PROFILE', 'en'))

    return Profile(profile_name, profiles_dirs, layers=layers)
