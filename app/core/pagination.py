from math import ceil
from typing import Annotated, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")

DEFAULT_PAGE = 1
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

PageNumber = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
SearchQuery = Annotated[str | None, Query(max_length=255)]


class Page[T](BaseModel):
    items: list[T]
    page: int
    limit: int
    total_count: int
    total_pages: int


def offset_for(page: int, limit: int) -> int:
    return (page - 1) * limit


def paginate(
    items: list[T],
    *,
    page: int,
    limit: int,
    total_count: int,
) -> Page[T]:
    total_pages = ceil(total_count / limit) if total_count > 0 else 0
    return Page(
        items=items,
        page=page,
        limit=limit,
        total_count=total_count,
        total_pages=total_pages,
    )
