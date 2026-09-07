from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ACCOUNT_DISABLED_MESSAGE, AppError
from app.modules.auth.models import Role
from app.modules.instructor import service
from app.modules.instructor.models import (
    AudienceSize,
    TeachingExperience,
    TeachingTopic,
    VideoExperience,
)
from app.modules.instructor.schemas import BecomeInstructorRequest


def _user(**overrides) -> SimpleNamespace:
    data = {
        "id": uuid.uuid4(),
        "email": "ada@example.com",
        "full_name": "Ada Lovelace",
        "phone_number": None,
        "is_active": True,
        "email_verified": True,
        "role": Role.USER,
        "is_instructor": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _payload() -> BecomeInstructorRequest:
    return BecomeInstructorRequest(
        teaching_experience=TeachingExperience.ONLINE,
        video_experience=VideoExperience.BEGINNER,
        audience_size=AudienceSize.NONE,
        teaching_topic=TeachingTopic.TECHNOLOGY,
    )


@pytest.fixture
def db() -> MagicMock:
    return MagicMock()


async def test_become_instructor_creates_row(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    payload = _payload()

    async def create(_db, stored, **kwargs):
        stored.is_instructor = True
        return SimpleNamespace(user_id=stored.id, **kwargs)

    create_for_user = AsyncMock(side_effect=create)
    monkeypatch.setattr(service.auth_repository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(service.repository, "create_for_user", create_for_user)

    result = await service.become_instructor(db, user_id=user.id, payload=payload)

    assert result.is_instructor is True
    assert result.role == Role.USER
    assert result.teaching_experience == TeachingExperience.ONLINE
    assert result.video_experience == VideoExperience.BEGINNER
    assert result.audience_size == AudienceSize.NONE
    assert result.teaching_topic == TeachingTopic.TECHNOLOGY
    create_for_user.assert_awaited_once()


async def test_become_instructor_rejects_duplicate(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user(is_instructor=True)
    create_for_user = AsyncMock()
    monkeypatch.setattr(service.auth_repository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(service.repository, "create_for_user", create_for_user)

    with pytest.raises(AppError) as exc_info:
        await service.become_instructor(db, user_id=user.id, payload=_payload())

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == service.ALREADY_INSTRUCTOR_MESSAGE
    create_for_user.assert_not_awaited()


async def test_become_instructor_rejects_unique_conflict(
    db: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _user()
    monkeypatch.setattr(service.auth_repository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(
        service.repository,
        "create_for_user",
        AsyncMock(side_effect=IntegrityError("stmt", "params", Exception("dup"))),
    )

    with pytest.raises(AppError) as exc_info:
        await service.become_instructor(db, user_id=user.id, payload=_payload())

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == service.ALREADY_INSTRUCTOR_MESSAGE


async def test_become_instructor_rejects_staff(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user(role=Role.ADMIN)
    create_for_user = AsyncMock()
    monkeypatch.setattr(service.auth_repository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(service.repository, "create_for_user", create_for_user)

    with pytest.raises(AppError) as exc_info:
        await service.become_instructor(db, user_id=user.id, payload=_payload())

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == service.STAFF_CANNOT_BECOME_INSTRUCTOR_MESSAGE
    create_for_user.assert_not_awaited()


async def test_become_instructor_rejects_inactive(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user(is_active=False)
    create_for_user = AsyncMock()
    monkeypatch.setattr(service.auth_repository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(service.repository, "create_for_user", create_for_user)

    with pytest.raises(AppError) as exc_info:
        await service.become_instructor(db, user_id=user.id, payload=_payload())

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == ACCOUNT_DISABLED_MESSAGE
    create_for_user.assert_not_awaited()


def test_become_request_rejects_invalid_topic() -> None:
    with pytest.raises(ValidationError):
        BecomeInstructorRequest(
            teaching_experience=TeachingExperience.ONLINE,
            video_experience=VideoExperience.BEGINNER,
            audience_size=AudienceSize.NONE,
            teaching_topic="NOT_A_TOPIC",
        )
