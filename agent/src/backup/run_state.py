"""Backup Run State Machine for RetroVault Backup Engine V4."""

from enum import Enum
from typing import Dict, Set, Optional, Callable, List
from agent.src.logger import get_logger


class RunState(str, Enum):
    CREATED = "CREATED"
    DISCOVERING = "DISCOVERING"
    SCANNING = "SCANNING"
    BACKING_UP = "BACKING_UP"
    PAUSED = "PAUSED"
    INTERRUPTED = "INTERRUPTED"
    RESUMING = "RESUMING"
    VERIFYING = "VERIFYING"
    COMPLETING = "COMPLETING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Allowed state transitions
VALID_TRANSITIONS: Dict[RunState, Set[RunState]] = {
    RunState.CREATED: {RunState.DISCOVERING, RunState.FAILED, RunState.CANCELLED},
    RunState.DISCOVERING: {RunState.SCANNING, RunState.FAILED, RunState.CANCELLED},
    RunState.SCANNING: {RunState.BACKING_UP, RunState.FAILED, RunState.CANCELLED},
    RunState.BACKING_UP: {RunState.VERIFYING, RunState.PAUSED, RunState.INTERRUPTED, RunState.FAILED, RunState.CANCELLED},
    RunState.PAUSED: {RunState.BACKING_UP, RunState.FAILED, RunState.CANCELLED},
    RunState.INTERRUPTED: {RunState.RESUMING, RunState.FAILED, RunState.CANCELLED},
    RunState.RESUMING: {RunState.BACKING_UP, RunState.FAILED, RunState.CANCELLED},
    RunState.VERIFYING: {RunState.COMPLETING, RunState.FAILED, RunState.CANCELLED},
    RunState.COMPLETING: {RunState.COMPLETED, RunState.FAILED},
    RunState.COMPLETED: set(),
    RunState.FAILED: set(),
    RunState.CANCELLED: set(),
}


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""
    pass


class RunStateMachine:
    """Manages the state lifecycle of a backup run and validates state transitions."""

    def __init__(self, initial_state: RunState = RunState.CREATED):
        self._current_state = initial_state
        self._listeners: List[Callable[[RunState, RunState], None]] = []
        self._logger = get_logger()

    @property
    def current_state(self) -> RunState:
        return self._current_state

    @property
    def is_terminal(self) -> bool:
        return self._current_state in (RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED)

    @property
    def is_recoverable(self) -> bool:
        return self._current_state in (
            RunState.CREATED,
            RunState.DISCOVERING,
            RunState.SCANNING,
            RunState.BACKING_UP,
            RunState.PAUSED,
            RunState.INTERRUPTED,
            RunState.RESUMING,
            RunState.VERIFYING,
            RunState.COMPLETING
        )

    def add_listener(self, callback: Callable[[RunState, RunState], None]) -> None:
        self._listeners.append(callback)

    def transition_to(self, new_state: RunState, reason: Optional[str] = None) -> RunState:
        """Attempt to transition to new_state. Validates legality against VALID_TRANSITIONS."""
        if new_state == self._current_state:
            return self._current_state

        allowed = VALID_TRANSITIONS.get(self._current_state, set())
        if new_state not in allowed:
            msg = (
                f"Illegal state transition from {self._current_state.value} to {new_state.value}. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )
            self._logger.error(msg)
            raise InvalidStateTransitionError(msg)

        old_state = self._current_state
        self._current_state = new_state
        self._logger.info(f"RunState transition: {old_state.value} -> {new_state.value}" + (f" ({reason})" if reason else ""))

        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                self._logger.warning(f"Error in state transition listener: {e}")

        return self._current_state

    # Convenience alias
    transition = transition_to
