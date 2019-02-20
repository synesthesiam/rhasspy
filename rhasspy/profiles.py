import os
import json
import collections
import logging
from typing import List, Dict, Mapping, Any

import pydash

from .utils import recursive_update

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class Profile:
    def __init__(self,
                 name: str,
                 profiles_dirs: List[str],
                 layers: str ='all') -> None:

        self.name: str = name
        self.profiles_dirs: List[str] = profiles_dirs
        self.layers: str = layers
        self.load_profile()

    # -------------------------------------------------------------------------

    @classmethod
    def load_defaults(cls, profiles_dirs: List[str]) -> Dict[str, Any]:
        defaults:Dict[str, Any] = {}
        for profiles_dir in profiles_dirs[::-1]:
            defaults_path = os.path.join(profiles_dir, 'defaults.json')
            if os.path.exists(defaults_path):
                with open(defaults_path, 'r') as defaults_file:
                    recursive_update(defaults, json.load(defaults_file))

        return defaults

    # -------------------------------------------------------------------------

    def get(self, path: str, default:Any=None) -> Any:
        return pydash.get(self.json, path, default)

    def set(self, path: str, value: Any) -> None:
        pydash.set_(self.json, path, value)

    # -------------------------------------------------------------------------

    def load_profile(self) -> None:
        # Load defaults first
        self.json: Dict[str, Any] = {}  # no defaults

        if self.layers in ['all', 'defaults']:
            for profiles_dir in self.profiles_dirs[::-1]:
                defaults_path = os.path.join(profiles_dir, 'defaults.json')
                if os.path.exists(defaults_path):
                    with open(defaults_path, 'r') as defaults_file:
                        recursive_update(self.json, json.load(defaults_file))

        # Overlay with profile
        if self.layers in ['all', 'profile']:
            self.json_path = self.read_path('profile.json')
            if os.path.exists(self.json_path):
                with open(self.json_path, 'r') as profile_file:
                    recursive_update(self.json, json.load(profile_file))

    def read_path(self, *path_parts: str) -> str:
        for profiles_dir in self.profiles_dirs:
            # Try to find in the runtime profile first
            full_path = os.path.join(profiles_dir, self.name, *path_parts)

            if os.path.exists(full_path):
                return full_path

        # Use base dir
        return os.path.join('profiles', self.name, path_parts[-1])

    def read_paths(self, *path_parts: str) -> List[str]:
        return_paths:List[str] = []

        for profiles_dir in self.profiles_dirs:
            # Try to find in the runtime profile first
            full_path = os.path.join(profiles_dir, self.name, *path_parts)

            if os.path.exists(full_path):
                return_paths.append(full_path)

        return return_paths

    def write_path(self, *path_parts: str) -> str:
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

    def write_dir(self, *dir_parts: str) -> str:
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
