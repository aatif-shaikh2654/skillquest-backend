from app.core.config import parse_origins
from app.middleware.rate_limit import (
    allow_request,
    decide_rate_limit,
    rate_limit_enabled_for_origin,
)


def test_parse_origins_splits_and_trims() -> None:
    assert parse_origins("http://localhost:3000, http://localhost:5173") == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    assert parse_origins('"http://localhost:3000, http://localhost:5173"') == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    assert parse_origins("https://app.skillquest.com/") == ["https://app.skillquest.com"]
    assert parse_origins(" , , ") == []


def test_local_http_origin_disables_rate_limit() -> None:
    assert rate_limit_enabled_for_origin("http://localhost:3000") is False
    assert rate_limit_enabled_for_origin("http://127.0.0.1:3000") is False


def test_local_https_origin_disables_rate_limit() -> None:
    assert rate_limit_enabled_for_origin("https://localhost:3000") is False


def test_http_public_origin_disables_rate_limit() -> None:
    assert rate_limit_enabled_for_origin("http://app.skillquest.com") is False


def test_https_public_origin_enables_rate_limit() -> None:
    assert rate_limit_enabled_for_origin("https://app.skillquest.com") is True


def test_disabled_never_rejects() -> None:
    hits = [1.0, 2.0, 3.0]
    allowed, remaining = decide_rate_limit(
        enabled=False,
        hits=hits,
        now=3.0,
        window_seconds=60,
        max_hits=3,
    )
    assert allowed is True
    assert remaining == hits


def test_under_cap_is_allowed() -> None:
    allowed, remaining = allow_request([10.0, 20.0], now=30.0, window_seconds=60, max_hits=3)
    assert allowed is True
    assert remaining == [10.0, 20.0, 30.0]


def test_at_cap_is_rejected() -> None:
    allowed, remaining = allow_request(
        [10.0, 20.0, 30.0],
        now=40.0,
        window_seconds=60,
        max_hits=3,
    )
    assert allowed is False
    assert remaining == [10.0, 20.0, 30.0]


def test_window_expiry_allows_again() -> None:
    allowed, remaining = allow_request(
        [10.0, 20.0, 30.0],
        now=80.0,
        window_seconds=60,
        max_hits=3,
    )
    assert allowed is True
    assert remaining == [30.0, 80.0]
