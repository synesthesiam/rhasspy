import os
import logging

from thespian import Actor

from profile import Profile

# -----------------------------------------------------------------------------

class ProfileEvent:
    def __init__(self, name, event):
        self.name = name
        self.event = event

# -----------------------------------------------------------------------------

class Rhasspy(Actor):

    def __init__(self):
        self.profiles = {}

        # Directory to load web assets from
        self.web_dir = os.environ.get('RHASSPY_WEB', 'dist')

        # Load default settings
        self.load_settings()

        # Load all profiles
        self.load_profiles()

    # -------------------------------------------------------------------------

    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, ProfileEvent):
                pass
        except Exception as ex:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def load_settings(self):
        # Like PATH, searched in reverse order
        self.profiles_dirs = [path for path in
                              os.environ.get('RHASSPY_PROFILES', 'profiles')\
                              .split(':') if len(path.strip()) > 0]

        self.profiles_dirs.reverse()
        logging.debug('Profiles dirs: %s' % self.profiles_dirs)

        # Load default settings
        self.defaults_json = Profile.load_defaults(self.profiles_dirs)

        # Load default profile
        self.default_profile_name = os.environ.get('RHASSPY_PROFILE', None)

        if self.default_profile_name is None:
            self.default_profile_name = \
                defaults_json['rhasspy'].get('default_profile', 'en')

        self.default_profile = self.load_profile(self.default_profile_name)

    # -------------------------------------------------------------------------

    def load_profiles(self):
        for profile_dir in self.profiles_dirs:
            profile_name = os.path.split(profile_dir)[1]
            profile = Profile(profile_name, self.profiles_dir)
            self.profiles[profile_name] = profile

    def load_profile(self, profile_name):
        profile = self.profiles.get(profile_name)
        if profile is None:
            self.profiles[profile_name] = Profile(profile_name)

        return profile

    # -------------------------------------------------------------------------

    def load_default(self):
        if self.default_profile.rhasspy.get('preload_profile', False):
            try:
                # Load speech to text decoder
                decoder = maybe_load_decoder(default_profile)
                self.stt_decoders[default_profile.name] = decoder
            except Exception as e:
                logging.error('Failed to pre-load profile')

        if self.default_profile.rhasspy.get('listen_on_start', False):
            # Start listening for wake word
            listen_for_wake(default_profile)

    def listen_for_wake(profile, no_hass=False, device_index=None):
        global listen_for_wake_func
        system = profile.wake.get('system', None)

        if system == 'pocketsphinx':
            global decoders
            listen_for_wake_func = wake.pocketsphinx_wake(
                profile, wake_decoders, functools.partial(wake_word_detected, profile, no_hass),
                device_index=device_index)

            # Start listening
            listen_for_wake_func()

            return profile.wake
        else:
            assert False, 'Unknown wake word system: %s' % system

    def wake_word_detected(profile, no_hass):
        global listen_for_wake_func

        # Listen until silence
        listen_for_command(profile, no_hass)

        # Start listening again
        listen_for_wake_func()

    def listen_for_command(profile, no_hass):
        utils.play_wav(profile.sounds.get('wake', ''))

        try:
            # Listen until silence
            from command_listener import CommandListener
            listener = CommandListener()
            recorded_data = listener.listen()

            utils.play_wav(profile.sounds.get('recorded', ''))

            # Convert to WAV
            with io.BytesIO() as wav_data:
                with wave.open(wav_data, mode='wb') as wav_file:
                    wav_file.setframerate(listener.sample_rate)
                    wav_file.setsampwidth(listener.sample_width)
                    wav_file.setnchannels(listener.channels)
                    wav_file.writeframesraw(recorded_data)

                wav_data.seek(0)

                # Get intent/send to Home Assistant
                intent = speech_to_intent(profile, wav_data.read(), no_hass)

                if not no_hass:
                    # Send intent to Home Assistant
                    utils.send_intent(profile.home_assistant, intent)

                return intent
        except:
            logging.exception('Error processing command')

        return {}

    # Cached rasaNLU projects
    # profile -> project
    intent_projects = {}

    # Cached fuzzywuzzy examples
    # profile -> examples
    intent_examples = {}

    def get_intent(profile, text):
        system = profile.intent.get('system', 'fuzzywuzzy')

        if system == 'rasa':
            rasa_config = profile.intent[system]

            # Use rasaNLU
            global intent_projects

            project = intent_projects.get(profile.name, None)
            if project is None:
                import rasa_nlu
                from rasa_nlu.project import Project
                project_dir = profile.read_path(rasa_config['project_dir'])
                project_name = rasa_config['project_name']

                project = Project(project=project_name,
                                  project_dir=project_dir)

                intent_projects[profile.name] = project

            return project.parse(text)
        elif system == 'remote':
            remote_url = profile.intent[system]['url']
            headers = { 'Content-Type': 'text/plain' }

            # Pass profile name through
            params = { 'profile': profile.name, 'nohass': True }
            response = requests.post(remote_url, headers=headers,
                                    data=text, params=params)

            response.raise_for_status()

            # Return intent directly
            return response.json()
        else:
            fuzzy_config = profile.intent[system]

            # Use fuzzywuzzy
            global intent_examples

            if not profile.name in intent_examples:
                examples_path = profile.read_path(fuzzy_config['examples_json'])
                with open(examples_path, 'r') as examples_file:
                    intent_examples[profile.name] = json.load(examples_file)

            text, intent_name, slots = best_intent(intent_examples[profile.name], text)

            # Try to match RasaNLU format for future compatibility
            intent = {
                'text': text,
                'intent': {
                    'name': intent_name,
                },
                'entities': [
                    { 'entity': name, 'value': values[0] } for name, values in slots.items()
                ]
            }

            return intent

    def speech_to_intent(profile, wav_data, no_hass=False):
        global decoders

        # speech to text
        decoder = transcribe_wav(profile, wav_data, decoders.get(profile.name))
        decoders[profile.name] = decoder

        # text to intent
        if decoder.hyp() is not None:
            text = decoder.hyp().hypstr
            intent = get_intent(profile, text)
            logging.debug(intent)

            if not no_hass:
                # Send intent to Home Assistant
                utils.send_intent(profile.home_assistant, intent)

            return intent

        return None
