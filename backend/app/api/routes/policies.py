from __future__ import annotations

from fastapi import APIRouter, Depends

from ...models.user import User
from ...policies.loader import load_all_policies, load_policy
from ..deps import get_current_user

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("")
def read_all_policies(_user: User = Depends(get_current_user)):
    return load_all_policies()


@router.get("/{policy_name}")
def read_policy(policy_name: str, _user: User = Depends(get_current_user)):
    return load_policy(policy_name)
