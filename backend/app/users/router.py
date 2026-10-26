from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import crud
from app.auth.schema import UserResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=list[UserResponse])
def get_all_users(current_user=Depends(get_current_user)):
    # No role/permission model exists yet, so avoid exposing every user's PII
    # to any authenticated account.
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrative user listing is not configured")


@router.get("/{user_id}", response_model=UserResponse)
def get_user_by_id(user_id: int, current_user=Depends(get_current_user)):
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access another user's profile")
    user = crud.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
