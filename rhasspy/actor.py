"""Actor system for Rhasspy."""
import asyncio
import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional, List

from rhasspy.profiles import Profile

# -----------------------------------------------------------------------------


class ConfigureEvent:
    """Sent to actors before transitioning to started state."""

    def __init__(self, profile: Profile, **kwargs: Any) -> None:
        self.profile = profile
        self.config = kwargs


class Configured:
    """Response from actor to ConfigureEvent."""

    def __init__(self, name: str, problems: Optional[Dict[str, Any]] = None):
        self.name = name
        self.problems = problems or {}


class StateTransition:
    """Emitted from actors during state transitions."""

    def __init__(self, name: str, from_state: str, to_state: str) -> None:
        self.name = name
        self.from_state = from_state
        self.to_state = to_state


# -----------------------------------------------------------------------------


class WakeupMessage:
    """Sent to actor when wakeupAfter timeout elapses."""

    def __init__(self, payload=None) -> None:
        self.payload = payload


class ChildActorExited:
    """Emitted by child actor to parent when it exits."""

    def __init__(self, actor):
        self.actor = actor


class ActorExitRequest:
    """Ask actor to shut down."""

    pass


# -----------------------------------------------------------------------------


class RhasspyActor:
    """Base class for all actors in Rhasspy."""

    shared_lock = threading.Lock()

    def __init__(self) -> None:
        # Message inbox
        self._queue: queue.Queue = queue.Queue()

        # True when loop is running
        self._running: bool = False

        # Thread for actor
        self._thread: Optional[threading.Thread] = None

        # Unique actor name
        self._name: str = self.__class__.__name__

        # Logger for actor
        self._logger = logging.getLogger(self._name)

        # Current state
        self._state: str = ""

        # Current on_ method to call when message is received
        self._state_method: Optional[Callable[[Any, RhasspyActor], None]] = None

        # Parent actor
        self._parent: Optional[RhasspyActor] = None

        # Rhasspy profile
        self._profile: Optional[Profile] = None

        # Settings for this actor
        self.config: Dict[str, Any] = {}

        # When True, report all state transitions
        self._transitions: bool = False
        self._lock = RhasspyActor.shared_lock

        # Child actors
        self._actors: List[RhasspyActor] = []

    # -------------------------------------------------------------------------

    def start(self):
        """Start actor loop in a separate thread."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self, block=True):
        """Stop this actor and its children."""
        for child_actor in self._actors:
            child_actor.stop(block=block)

        self.send(self, ActorExitRequest())
        if block:
            self._thread.join()

    def _loop(self):
        """Main loop for this actor."""
        while self._running:
            message_dict = self._queue.get()
            self.on_receive(message_dict)

    @property
    def profile(self) -> Profile:
        """Get user profile."""
        assert self._profile is not None
        return self._profile

    # -------------------------------------------------------------------------

    def on_receive(self, message_dict: Dict[str, Any]) -> None:
        """Called when a message has been sent to this actor."""
        try:
            sender = message_dict["sender"]
            message = message_dict["message"]

            if isinstance(message, ActorExitRequest):
                # Transition to stopped state and exit
                self._running = False
                self.transition("stopped")
                self.send(self._parent, ChildActorExited(self))
            elif isinstance(message, ConfigureEvent):
                # Receive configuration and transition to started state
                self._parent = sender
                self._profile = message.profile
                self.config = message.config
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
                    self._logger.warning(
                        "Unhandled message in state %s: %s", self._state, message
                    )
        except Exception:
            self._logger.exception("on_receive")

    # -------------------------------------------------------------------------

    def send(self, actor, message):
        """Send message to another actor."""
        if actor is not None:
            actor.queue.put({"sender": self, "message": message})

    def createActor(self, cls):
        """Create a new child actor from class type."""
        child_actor = cls().start()
        self._actors.append(child_actor)
        return child_actor

    @property
    def myAddress(self):
        """Get handle for current actor."""
        return self

    @property
    def queue(self):
        """Get message queue for current actor."""
        return self._queue

    def wakeupAfter(self, timedelta, payload=None):
        """Request delivery of WakeupMessage after a timeout."""

        def wait():
            time.sleep(timedelta.total_seconds())
            self.send(self, WakeupMessage(payload=payload))

        threading.Thread(target=wait, daemon=True).start()

    # -------------------------------------------------------------------------

    def transition(self, to_state: str) -> None:
        """Transition actor to another state."""
        from_state = self._state
        transition_method = "to_" + to_state
        self._state = to_state

        # Set state method (in_STATE)
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

    def __repr__(self):
        """String representation of actor."""
        return self._name

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get dict of problems actor found during start up."""
        return {}


# -----------------------------------------------------------------------------


class InboxActor(RhasspyActor):
    """Special actor that can be used to send/receive messages outside of the actor system."""

    def __init__(self):
        super().__init__()
        self.receive_event = threading.Event()
        self.async_receive_event = asyncio.Event()
        self.loop = asyncio.get_event_loop()
        self.message = None

    def on_receive(self, message_dict):
        """Called when a message is received."""
        self.message = message_dict["message"]
        self.receive_event.set()
        self.loop.call_soon_threadsafe(self.async_receive_event.set)

    def ask(self, actor, message, timeout=None):
        """Send a message to an actor and block until reply or timeout."""
        self.tell(actor, message)
        return self.listen(timeout=timeout)

    async def async_ask(self, actor, message, timeout=None):
        """Send a message to an actor and await a reply or timeout."""
        self.tell(actor, message)
        return await self.async_listen(timeout=timeout)

    def tell(self, actor, message):
        """Send a message to an actor."""
        actor.queue.put({"sender": self, "message": message})

    def listen(self, timeout=None):
        """Block until a message is received or timeout."""
        self.message = None
        self.receive_event.wait(timeout=timeout)
        self.receive_event.clear()
        return self.message

    async def async_listen(self, timeout=None):
        """Await a message or timeout."""
        self.message = None
        await asyncio.wait_for(self.async_receive_event.wait(), timeout)
        self.async_receive_event.clear()
        return self.message

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop(block=False)


class ActorSystem:
    """Container for all actors."""

    def __init__(self, *args, **kwargs):
        self.inbox = InboxActor().start()
        self.actors = [self.inbox]

    def createActor(self, cls):
        """Create a new actor from a class type."""
        actor = cls().start()
        self.actors.append(actor)
        return actor

    def ask(self, actor, message):
        """Send a message to an actor and block until a reply."""
        return self.inbox.ask(actor, message)

    def tell(self, actor, message):
        """Send a message to an actor."""
        self.inbox.tell(actor, message)

    def private(self):
        """Create a short-lived actor to send/receive messages."""
        return InboxActor()

    def shutdown(self):
        """Shut down all actors."""
        for actor in self.actors:
            actor.stop(block=False)
