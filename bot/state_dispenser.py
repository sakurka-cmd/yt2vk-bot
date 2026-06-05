"""Custom StateDispenser backed by SQLite database."""

from vkbottle.dispatch import ABCStateDispenser, StatePeer
from bot.states import States
from bot import database as db


class DbStateDispenser(ABCStateDispenser):
    """State dispenser that uses the SQLite FSM table."""

    async def get(self, peer_id: int) -> StatePeer | None:
        state_str, data = await db.get_fsm_state(peer_id)
        if not state_str:
            return None
        try:
            state_enum = States(state_str)
            return StatePeer(peer_id=peer_id, state=state_enum, payload=data)
        except ValueError:
            return None

    async def set(self, peer_id: int, state, **payload):
        state_val = state.value if hasattr(state, "value") else str(state)
        await db.save_fsm_state(peer_id, state_val, payload)

    async def delete(self, peer_id: int):
        await db.clear_fsm_state(peer_id)

