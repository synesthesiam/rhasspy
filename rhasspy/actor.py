import logging
import threading
import time
import queue
from typing import List, Callable, Optional, Any, Dict

try:
    from gevent import sleep
except:
    from time import sleep

from .profiles import Profile

# -----------------------------------------------------------------------------


class ConfigureEvent:
    def __init__(self, profile: Profile, **kwargs: Any) -> None:
        self.profile = profile
        self.config = kwargs


class Configured:
    def __init__(self, name: str, problems: Dict[str, Any] = {}):
        self.name = name
        self.problems = problems


class StateTransition:
    def __init__(self, name: str, from_state: str, to_state: str) -> None:
        self.name = name
        self.from_state = from_state
        self.to_state = to_state


# -----------------------------------------------------------------------------


class WakeupMessage:
    def __init__(self, payload=None) -> None:
        self.payload = payload


class ChildActorExited:
    def __init__(self, actor):
        self.actor = actor


class ActorExitRequest:
    pass


# -----------------------------------------------------------------------------


class RhasspyActor:
    shared_lock = threading.Lock()

    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None

        self._name: str = self.__class__.__name__
        self._logger = logging.getLogger(self._name)
        self._state: str = ""
        self._state_method: Optional[Callable[[Any, RhasspyActor], None]] = None
        self._transitions: bool = False
        self._lock = RhasspyActor.shared_lock

    # -------------------------------------------------------------------------

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self, block=True):
        self.send(self, ActorExitRequest())
        if block:
            self._thread.join()

    def _loop(self):
        while self._running:
            message_dict = self._queue.get()
            self.on_receive(message_dict)

    # -------------------------------------------------------------------------

    def on_receive(self, message_dict: Dict[str, Any]) -> None:
        try:
            sender = message_dict["sender"]
            message = message_dict["message"]

            if isinstance(message, ActorExitRequest):
                self._running = False
                self.transition("stopped")
                self.send(self._parent, ChildActorExited(self))
            elif isinstance(message, ConfigureEvent):
                self._parent: RhasspyActor = sender
                self.profile: Profile = message.profile
                self.config: Dict[str, Any] = message.config
                self._transitions = self.config.get("transitions", True)

                try:
                    self.transition("started")
                    self.send(sender, Configured(self._name, self.get_problems()))
                except Exception as e:
                    self._logger.exception("started")
                    self.send(
                        sender, Configured(self._name, {e.__class__.__name__: str(e)})
                    )
            else:
                # Call in_<state> method
                if self._state_method is not None:
                    self._state_method(message, sender)
                elif not isinstance(message, ChildActorExited) and not isinstance(
                    message, StateTransition
                ):
                    self._logger.warn(
                        "Unhandled message in state %s: %s", self._state, message
                    )
        except:
            self._logger.exception("receiveMessage")

    # -------------------------------------------------------------------------

    def send(self, actor, message):
        if actor is not None:
            actor.queue.put({"sender": self, "message": message})

    def createActor(self, cls):
        return cls().start()

    @property
    def myAddress(self):
        return self

    @property
    def queue(self):
        return self._queue

    def wakeupAfter(self, timedelta, payload=None):
        def wait():
            time.sleep(timedelta.total_seconds())
            self.send(self, WakeupMessage(payload=payload))

        threading.Thread(target=wait, daemon=True).start()

    # -------------------------------------------------------------------------

    def transition(self, to_state: str) -> None:
        from_state = self._state
        transition_method = "to_" + to_state
        self._state = to_state

        # Set state method
        state_method_name = "in_" + self._state
        if hasattr(self, state_method_name):
            self._state_method = getattr(self, state_method_name)
        else:
            self._state_method = None

        self._logger.debug("%s -> %s", from_state, to_state)

        # Call transition method
        if (from_state != to_state) and hasattr(self, transition_method):
            getattr(self, transition_method)(from_state)

        # Report state transition
        if self._transitions and (self._parent is not None):
            self.send(self._parent, StateTransition(self._name, from_state, to_state))

        # Yield execution
        sleep(0)

    def __repr__(self):
        return self._name

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        return {}


# -----------------------------------------------------------------------------


class InboxActor(RhasspyActor):
    def __init__(self):
        super().__init__()
        self.receive_event = threading.Event()
        self.message = None

    def on_receive(self, message_dict):
        self.message = message_dict["message"]
        self.receive_event.set()

    def ask(self, actor, message, timeout=None):
        self.tell(actor, message)
        return self.listen(timeout=timeout)

    def tell(self, actor, message):
        actor.queue.put({"sender": self, "message": message})

    def listen(self, timeout=None):
        self.message = None
        self.receive_event.wait(timeout=timeout)
        self.receive_event.clear()
        return self.message

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop(block=False)


class ActorSystem:
    def __init__(self, *args, **kwargs):
        self.inbox = InboxActor().start()
        self.actors = [self.inbox]

    def createActor(self, cls):
        actor = cls().start()
        self.actors.append(actor)
        return actor

    def ask(self, actor, message):
        return self.inbox.ask(actor, message)

    def tell(self, actor, message):
        self.inbox.tell(actor, message)

    def private(self):
        return InboxActor()

    def shutdown(self):
        for actor in self.actors:
            actor.stop(block=False)
