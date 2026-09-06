from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from app.core.exceptions import AppError
from app.modules.auth import service
from app.modules.auth.models import Role


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


@pytest.fixture
def db() -> MagicMock:
    return MagicMock()


async def test_become_instructor_sets_flag(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()

    async def set_flag(_db, stored) -> None:
        stored.is_instructor = True

    monkeypatch.setattr(service.repository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(service.repository, "set_is_instructor", AsyncMock(side_effect=set_flag))

    result = await service.become_instructor(db, user_id=user.id)

    assert result.is_instructor is True
    assert result.role == Role.USER


async def test_become_instructor_rejects_duplicate(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user(is_instructor=True)
    set_flag = AsyncMock()
    monkeypatch.setattr(service.repository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(service.repository, "set_is_instructor", set_flag)

    with pytest.raises(AppError) as exc_info:
        await service.become_instructor(db, user_id=user.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == service.ALREADY_INSTRUCTOR_MESSAGE
    set_flag.assert_not_awaited()


async def test_become_instructor_rejects_staff(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user(role=Role.ADMIN)
    set_flag = AsyncMock()
    monkeypatch.setattr(service.repository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(service.repository, "set_is_instructor", set_flag)

    with pytest.raises(AppError) as exc_info:
        await service.become_instructor(db, user_id=user.id)

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == service.STAFF_CANNOT_BECOME_INSTRUCTOR_MESSAGE
    set_flag.assert_not_awaited()
