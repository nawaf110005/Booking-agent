from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from booking_agent.agent import SESSION_STORE, handle
from booking_agent.agent.responses import AgentResponse
from booking_agent.api.deps import get_db

router = APIRouter()


class SessionOut(BaseModel):
    session_id: str


class ChatIn(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1)


@router.post("/sessions", response_model=SessionOut)
def create_session() -> SessionOut:
    return SessionOut(session_id=SESSION_STORE.create().session_id)


@router.post("/chat", response_model=AgentResponse)
def chat(body: ChatIn, db: Session = Depends(get_db)) -> dict:
    state = SESSION_STORE.get_or_create(body.session_id)
    result = handle(db, state, body.message)
    SESSION_STORE.save(state)  # persist so the flow survives a backend restart
    return result
