# pyrefly: ignore[missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
# pyrefly: ignore[missing-import]
from sqlalchemy.exc import IntegrityError
# pyrefly: ignore[missing-import]
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.settings import crud
from app.settings.schema import (
    ProfileResponse,
    ProfileUpdate,
    SettingsResponse,
    SettingsUpdate,
)
from database.database import get_db


router = APIRouter(
    prefix="/settings",
    tags=["Settings"],
)


@router.get("/me", response_model=SettingsResponse)
def get_my_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_or_create_settings(
        db,
        current_user.id,
    )


@router.patch("/me", response_model=SettingsResponse)
def update_my_settings(
    data: SettingsUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes = data.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    if not changes:
        return crud.get_or_create_settings(
            db,
            current_user.id,
        )

    try:
        return crud.update_settings(
            db,
            current_user.id,
            changes,
        )
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save settings",
        )


@router.get("/profile", response_model=ProfileResponse)
def get_my_profile(
    current_user=Depends(get_current_user),
):
    return current_user


@router.patch("/profile", response_model=ProfileResponse)
def update_my_profile(
    data: ProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes = data.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    if not changes:
        return current_user

    try:
        return crud.update_profile(
            db,
            current_user,
            changes,
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update profile",
        ) from exc