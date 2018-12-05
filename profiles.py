import os
import json
import collections
import logging

class Profile:
    def __init__(self, name, profiles_dirs, layers='all'):
        self.name = name
        self.profiles_dirs = profiles_dirs
        self.layers = layers
        self.load_profile()

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
                    recursive_update(self.json, json.load(profile_file))

        # Extract default sub-sections
        self.rhasspy = self.json.get('rhasspy', {})
        self.home_assistant = self.json.get('home_assistant', {})
        self.speech_to_text = self.json.get('speech_to_text', {})
        self.text_to_speech = self.json.get('text_to_speech', {})
        self.intent = self.json.get('intent', {})
        self.wake = self.json.get('wake', {})
        self.training = self.json.get('training', {})

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
                logging.exception('Unable to write to %s' % full_path)

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
                logging.exception('Unable to create %s' % dir_path)

        # Use base dir
        dir_path = os.path.join('profiles', self.name, *dir_parts)
        os.makedirs(dir_path, exist_ok=True)

        return dir_path

# -----------------------------------------------------------------------------

def request_to_profile(request, profiles_dirs, layers='all'):
    profile_name = request.args.get(
        'profile', os.environ.get('RHASSPY_PROFILE', 'en'))

    return Profile(profile_name, profiles_dirs, layers=layers)

def recursive_update(base_dict, new_dict):
    for k, v in new_dict.items():
        if isinstance(v, collections.Mapping) and (k in base_dict):
            recursive_update(base_dict[k], v)
        else:
            base_dict[k] = v
