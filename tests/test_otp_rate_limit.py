from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from app.core.exceptions import AppError
from app.modules.auth import service
from app.modules.auth.models import Role
from app.modules.auth.schemas import LoginRequest, SignupRequest, normalize_email


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="ada@example.com",
        full_name="Ada Lovelace",
        phone_number=None,
        is_active=True,
        email_verified=False,
        role=Role.USER,
        is_instructor=False,
    )


def _otp(*, seconds_ago: int) -> SimpleNamespace:
    return SimpleNamespace(
        created_at=datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    )


@pytest.fixture
def db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def otp_repo(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    latest = AsyncMock(return_value=None)
    count = AsyncMock(return_value=0)
    invalidate = AsyncMock()
    create = AsyncMock()
    get_by_email = AsyncMock(return_value=None)
    send = AsyncMock()
    monkeypatch.setattr(service.repository, "get_latest_email_otp", latest)
    monkeypatch.setattr(service.repository, "count_email_otps_since", count)
    monkeypatch.setattr(service.repository, "invalidate_unused_email_otps", invalidate)
    monkeypatch.setattr(service.repository, "create_email_otp", create)
    monkeypatch.setattr(service.repository, "get_by_email", get_by_email)
    monkeypatch.setattr(service, "send_email", send)
    return SimpleNamespace(
        get_latest=latest,
        count=count,
        invalidate=invalidate,
        create=create,
        get_by_email=get_by_email,
        send=send,
    )


async def test_first_send_allowed(db: MagicMock, otp_repo: SimpleNamespace) -> None:
    await service._issue_otp(db, _user())

    otp_repo.create.assert_awaited_once()
    otp_repo.send.assert_awaited_once()


async def test_second_send_within_60s_is_rejected(
    db: MagicMock, otp_repo: SimpleNamespace
) -> None:
    otp_repo.get_latest.return_value = _otp(seconds_ago=10)

    with pytest.raises(AppError) as exc_info:
        await service._issue_otp(db, _user())

    assert exc_info.value.status_code == 429
    assert exc_info.value.message == service.OTP_COOLDOWN_MESSAGE
    otp_repo.create.assert_not_awaited()
    otp_repo.send.assert_not_awaited()


async def test_send_after_60s_is_allowed(db: MagicMock, otp_repo: SimpleNamespace) -> None:
    otp_repo.get_latest.return_value = _otp(seconds_ago=61)
    otp_repo.count.return_value = 1

    await service._issue_otp(db, _user())

    otp_repo.create.assert_awaited_once()
    otp_repo.send.assert_awaited_once()


async def test_sixth_send_in_window_is_rejected(
    db: MagicMock, otp_repo: SimpleNamespace
) -> None:
    otp_repo.get_latest.return_value = _otp(seconds_ago=61)
    otp_repo.count.return_value = 5

    with pytest.raises(AppError) as exc_info:
        await service._issue_otp(db, _user())

    assert exc_info.value.status_code == 429
    assert exc_info.value.message == service.OTP_RATE_LIMIT_MESSAGE
    otp_repo.create.assert_not_awaited()
    otp_repo.send.assert_not_awaited()


async def test_unknown_email_login_is_rejected(
    db: MagicMock, otp_repo: SimpleNamespace
) -> None:
    with pytest.raises(AppError) as exc_info:
        await service.request_login_otp(db, email="missing@example.com")

    assert exc_info.value.status_code == 404
    assert exc_info.value.message == service.ACCOUNT_NOT_FOUND_MESSAGE
    otp_repo.get_latest.assert_not_awaited()
    otp_repo.send.assert_not_awaited()


async def test_signup_rejects_existing_email(
    db: MagicMock, otp_repo: SimpleNamespace
) -> None:
    otp_repo.get_by_email.return_value = _user()
    create_user = AsyncMock()

    with (
        patch.object(service.repository, "create_user", create_user),
        pytest.raises(AppError) as exc_info,
    ):
        await service.signup(
            db,
            email="ada@example.com",
            full_name="Ada Lovelace",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.message == service.ACCOUNT_EXISTS_MESSAGE
    create_user.assert_not_awaited()
    otp_repo.send.assert_not_awaited()


def test_normalize_email_lowercases_and_trims() -> None:
    assert normalize_email("  Ada@Example.COM ") == "ada@example.com"
    assert SignupRequest(email="Ada@Example.COM", full_name="Ada").email == "ada@example.com"
    assert LoginRequest(email="Ada@Example.COM").email == "ada@example.com"


async def test_login_looks_up_lowercase_email(
    db: MagicMock, otp_repo: SimpleNamespace
) -> None:
    otp_repo.get_by_email.return_value = _user()

    await service.request_login_otp(db, email="Ada@Example.COM")

    otp_repo.get_by_email.assert_awaited_once_with(db, "ada@example.com")
    otp_repo.send.assert_awaited_once()


async def test_signup_stores_lowercase_email(
    db: MagicMock, otp_repo: SimpleNamespace
) -> None:
    created = _user()
    create_user = AsyncMock(return_value=created)

    with patch.object(service.repository, "create_user", create_user):
        await service.signup(
            db,
            email="Ada@Example.COM",
            full_name="Ada Lovelace",
        )

    otp_repo.get_by_email.assert_awaited_once_with(db, "ada@example.com")
    assert create_user.await_args.kwargs["email"] == "ada@example.com"
