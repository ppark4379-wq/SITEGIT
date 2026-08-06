from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.security import decode_access_token
from ...db.session import SessionLocal
from ...models.user import User
from ...realtime.manager import manager
from ...schemas.state import StateResponse, StateUpdate
from ...services.state_service import get_or_create_state, update_state
from ..deps import get_current_user, get_db, require_roles

router = APIRouter(prefix="/state", tags=["shared-state"])


def _to_response(state) -> StateResponse:
    return StateResponse(
        project_id=state.project_id,
        payload=state.payload,
        revision=state.revision,
        updated_at=state.updated_at,
        updated_by=state.updated_by,
    )


@router.get("/{project_id}", response_model=StateResponse)
def read_state(
    project_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> StateResponse:
    settings = get_settings()
    state = get_or_create_state(db, project_id=project_id, seed_path=settings.seed_state_path)
    return _to_response(state)


@router.put("/{project_id}", response_model=StateResponse)
async def write_state(
    project_id: str,
    update: StateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "manager", "reviewer")),
) -> StateResponse:
    settings = get_settings()
    state = get_or_create_state(db, project_id=project_id, seed_path=settings.seed_state_path)
    state = update_state(
        db,
        state=state,
        payload=update.payload,
        expected_revision=update.revision,
        source=update.source,
        user=user,
    )
    await manager.broadcast(
        project_id,
        {
            "type": "state.updated",
            "project_id": project_id,
            "revision": state.revision,
            "updated_by": user.username,
        },
    )
    return _to_response(state)


@router.websocket("/ws/{project_id}")
async def state_socket(websocket: WebSocket, project_id: str) -> None:
    settings = get_settings()
    token = websocket.cookies.get(settings.auth_cookie_name) or websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    with SessionLocal() as db:
        user = db.get(User, payload.get("sub"))
        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    await manager.connect(project_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(project_id, websocket)
