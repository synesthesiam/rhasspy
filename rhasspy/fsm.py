import logging

from thespian.actors import Actor

class FSMActor(Actor):
    STARTED_STATE = 'started'

    def __init__(self):
        self._state = None

    # -------------------------------------------------------------------------

    def receiveMessage(self, message, sender):
        try:
            if self._state is None:
                self.transition(FSMActor.STARTED)

            # Call in_<state> method
            state_method = 'in_' + self._state
            if hasattr(self, state_method):
                getattr(self, state_method)(message, sender)
        except:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def transition(self, to_state):
        from_state = self._state
        transition_method = 'to_' + to_state
        self._state = to_state
        if hasattr(self, transition_method):
            getattr(self, transition_method)(from_state)
