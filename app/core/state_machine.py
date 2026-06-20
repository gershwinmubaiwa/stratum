from enum import Enum
from typing import List, Dict

class DebateState(str, Enum):
    AWAITING_INPUT = "AWAITING_INPUT"
    CEO_AGENDA = "CEO_AGENDA"
    CFO_ANALYSIS = "CFO_ANALYSIS"
    CMO_COUNTER = "CMO_COUNTER"
    CEO_SYNTHESIS = "CEO_SYNTHESIS"
    CONVERGED = "CONVERGED"
    BRIEFING_READY = "BRIEFING_READY"
    INTERJECTED = "INTERJECTED"
    ERRORED = "ERRORED"

TRANSITIONS: Dict[DebateState, List[DebateState]] = {
    DebateState.AWAITING_INPUT: [DebateState.CEO_AGENDA],
    DebateState.CEO_AGENDA: [DebateState.CFO_ANALYSIS, DebateState.INTERJECTED, DebateState.ERRORED],
    DebateState.CFO_ANALYSIS: [DebateState.CMO_COUNTER, DebateState.INTERJECTED, DebateState.ERRORED],
    DebateState.CMO_COUNTER: [DebateState.CEO_SYNTHESIS, DebateState.INTERJECTED, DebateState.ERRORED],
    DebateState.CEO_SYNTHESIS: [DebateState.CONVERGED, DebateState.INTERJECTED, DebateState.ERRORED],
    DebateState.CONVERGED: [DebateState.BRIEFING_READY, DebateState.ERRORED],
    DebateState.BRIEFING_READY: [DebateState.ERRORED],
    DebateState.INTERJECTED: [DebateState.CEO_AGENDA, DebateState.CFO_ANALYSIS, DebateState.CMO_COUNTER, DebateState.CEO_SYNTHESIS, DebateState.CONVERGED,DebateState.ERRORED],
    DebateState.ERRORED: [],
}

class InvalidStateTransitionError(Exception):
    def __init__(self, from_state: DebateState, to_state: DebateState):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid transition from {from_state} to {to_state}")

def validate_transition(from_state: DebateState, to_state: DebateState) -> bool:
    if to_state not in TRANSITIONS.get(from_state, []):
        raise InvalidStateTransitionError(from_state, to_state)
    return True
