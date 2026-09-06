from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from app.core.exceptions import AppError
from app.core.pagination import offset_for, paginate
from app.modules.admin import service as admin_service
from app.modules.admin.repository import _ilike_pattern
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


async def test_get_me_returns_staff(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    admin = _user(role=Role.ADMIN, email="admin@example.com", full_name="Admin")
    monkeypatch.setattr(admin_service, "get_by_id", AsyncMock(return_value=admin))

    result = await admin_service.get_me(db, admin.id)

    assert result.role == Role.ADMIN
    assert result.email == "admin@example.com"


async def test_get_me_rejects_public_user(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    monkeypatch.setattr(admin_service, "get_by_id", AsyncMock(return_value=user))

    with pytest.raises(AppError) as exc_info:
        await admin_service.get_me(db, user.id)

    assert exc_info.value.status_code == 401


async def test_logout_rejects_public_user(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    logout = AsyncMock()
    monkeypatch.setattr(admin_service.auth_service, "resolve_session_user", AsyncMock(return_value=user))
    monkeypatch.setattr(admin_service.auth_service, "logout", logout)

    with pytest.raises(AppError) as exc_info:
        await admin_service.logout(db, "session", "renewal")

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == admin_service.NOT_AUTHORIZED_MESSAGE
    logout.assert_not_awaited()


async def test_logout_invalidates_staff(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    admin = _user(role=Role.SUPER_ADMIN)
    logout = AsyncMock()
    monkeypatch.setattr(admin_service.auth_service, "resolve_session_user", AsyncMock(return_value=admin))
    monkeypatch.setattr(admin_service.auth_service, "logout", logout)

    await admin_service.logout(db, "session", "renewal")

    logout.assert_awaited_once()


async def test_list_users_returns_public_accounts(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    users = [_user(), _user(email="al@example.com", full_name="Al")]
    monkeypatch.setattr(
        admin_service.repository,
        "list_users",
        AsyncMock(return_value=(users, 2)),
    )

    result = await admin_service.list_users(db, page=1, limit=50)

    assert result.total_count == 2
    assert result.page == 1
    assert result.limit == 50
    assert result.total_pages == 1
    assert [item.email for item in result.items] == ["ada@example.com", "al@example.com"]
    assert all(item.role == Role.USER for item in result.items)


async def test_list_users_passes_trimmed_search(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    list_users = AsyncMock(return_value=([_user()], 1))
    monkeypatch.setattr(admin_service.repository, "list_users", list_users)

    result = await admin_service.list_users(db, page=2, limit=20, search="  ada  ")

    assert result.total_count == 1
    list_users.assert_awaited_once_with(db, limit=20, offset=20, search="ada")


async def test_list_users_ignores_blank_search(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    list_users = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(admin_service.repository, "list_users", list_users)

    await admin_service.list_users(db, page=1, limit=20, search="   ")

    list_users.assert_awaited_once_with(db, limit=20, offset=0, search=None)


def test_search_pattern_is_case_insensitive_wildcard_and_escaped() -> None:
    assert _ilike_pattern("ada") == "%ada%"
    assert _ilike_pattern("100%") == r"%100\%%"
    assert _ilike_pattern("a_b") == r"%a\_b%"


def test_paginate_computes_page_metadata() -> None:
    page = paginate(["a", "b"], page=2, limit=20, total_count=45)

    assert page.page == 2
    assert page.limit == 20
    assert page.total_count == 45
    assert page.total_pages == 3
    assert offset_for(2, 20) == 20


def test_paginate_empty_result_has_zero_pages() -> None:
    page = paginate([], page=1, limit=20, total_count=0)

    assert page.total_count == 0
    assert page.total_pages == 0
