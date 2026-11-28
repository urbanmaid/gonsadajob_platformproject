"""목록 API 공통 페이지네이션 (page 기본 1, limit 기본 20·최대 100)."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


@dataclass(frozen=True)
class PageParams:
    page: int
    limit: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def page_params(
    page: int = Query(1, ge=1, description="1부터 시작하는 페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수 (최대 100)"),
) -> PageParams:
    return PageParams(page=page, limit=limit)


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    limit: int
    total: int
