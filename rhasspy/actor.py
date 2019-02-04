import logging
from typing import List, Callable, Optional, Any, Dict

from thespian.actors import Actor, ActorExitRequest, ChildActorExited, ActorAddress

from .profiles import Profile

# -----------------------------------------------------------------------------

class ConfigureEvent:
    def __init__(self, profile: Profile, **kwargs: Any) -> None:
        self.profile = profile
        self.config = kwargs

class Configured:
    pass

class StateTransition:
    def __init__(self, name:str, from_state:str, to_state:str):
        self.name = name
        self.from_state = from_state
        self.to_state = to_state

# -----------------------------------------------------------------------------

class RhasspyActor(Actor):
    def __init__(self) -> None:
        self._name: str = self.__class__.__name__
        self._logger = logging.getLogger(self._name)
        self._state:str = ''
        self._state_method: Optional[Callable[[Any, ActorAddress], None]] = None

    # -------------------------------------------------------------------------

    def receiveMessage(self, message: Any, sender: ActorAddress) -> None:
        try:
            if isinstance(message, ActorExitRequest):
                self.transition('stopped')
            elif isinstance(message, ConfigureEvent):
                self._parent: ActorAddress = sender
                self.profile: Profile = message.profile
                self.config: Dict[str, Any] = message.config
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

    def transition(self, to_state: str) -> None:
        from_state = self._state
        transition_method = 'to_' + to_state
        self._state = to_state

        # Call transition method
        if (from_state != to_state) and hasattr(self, transition_method):
            getattr(self, transition_method)(from_state)

        self._logger.debug('%s -> %s', from_state, to_state)
        if self._parent is not None:
            self.send(self._parent,
                      StateTransition(self._name, from_state, to_state))

        # Set state method
        state_method_name = 'in_' + self._state
        if hasattr(self, state_method_name):
            self._state_method = getattr(self, state_method_name)
        else:
            self._state_method = None
