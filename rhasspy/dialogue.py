from .actor import RhasspyActor
from .wake import StartListening, WakeWordDetected
from .command_listener import ListenForCommand, VoiceCommand

class DialogueManager(RhasspyActor):

    def to_started(self, from_state):
        self.wake = self.config['wake']
        self.listener = self.config['listener']
        self.transition('asleep')

    def to_asleep(self, from_state):
        if self.profile.get('rhasspy.listen_on_start', False):
            self._logger.info('Automatically listening for wake word')
            self.send(self.wake, StartListening(self.myAddress))

    def in_asleep(self, message, sender):
        if isinstance(message, WakeWordDetected):
            self._logger.debug('Awake!')
            self.transition('awake')

    def to_awake(self, from_state):
        self.send(self.listener, ListenForCommand(self.myAddress))

    def in_awake(self, message, sender):
        if isinstance(message, VoiceCommand):
            print(message)
            self.transition('asleep')
