import logging
from typing import List

from thespian.actors import Actor, ActorExitRequest, ChildActorExited

from .profiles import Profile

# -----------------------------------------------------------------------------

class ConfigureEvent:
    def __init__(self, profile: Profile, **kwargs):
        self.profile = profile
        self.config = kwargs

class Configured:
    pass

# -----------------------------------------------------------------------------

class RhasspyActor(Actor):
    def __init__(self):
        self._name = self.__class__.__name__
        self._logger = logging.getLogger(self._name)
        self._state = ''
        self._state_method = None

    # -------------------------------------------------------------------------

    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, ActorExitRequest):
                self.transition('stopped')
            elif isinstance(message, ConfigureEvent):
                self.profile = message.profile
                self.config = message.config
                self.transition('started')
                self.send(sender, Configured())
            else:
                # Call in_<state> method
                if self._state_method is not None:
                    self._state_method(message, sender)
                elif not isinstance(message, ChildActorExited):
                    self._logger.warn('Unhandled message in state %s: %s',
                                      self._state, message)
        except:
            self._logger.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def transition(self, to_state):
        from_state = self._state
        transition_method = 'to_' + to_state
        self._state = to_state

        # Call transition method
        if (from_state != to_state) and hasattr(self, transition_method):
            getattr(self, transition_method)(from_state)

        # Set state method
        state_method_name = 'in_' + self._state
        if hasattr(self, state_method_name):
            self._state_method = getattr(self, state_method_name)
        else:
            self._state_method = None

        self._logger.debug('%s -> %s', from_state, to_state)
