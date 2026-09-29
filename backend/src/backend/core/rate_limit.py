# DB에 시도 기록을 남겨 서버 재시작·다중 서버에서도 유지되는 슬라이딩 윈도우 요청 제한

import hashlib
import hmac
import math
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import DateTime, String, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.config import settings
from backend.core.database import Base


# 제한 대상(원문 대신 HMAC 해시)별 시도 시각 기록
class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    bucket: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)


# IP·이메일 원문을 저장하지 않도록 이름과 값을 HMAC 해시 버킷 키로 변환
def bucket_key(name: str, value: str) -> str:
    return hmac.new(settings.auth_secret_key.encode(), f"{name}|{value.strip().lower()}".encode(), hashlib.sha256).hexdigest()


# 초과 시 Retry-After를 포함한 429 오류 생성
def rate_limited_error(retry_after: int) -> HTTPException:
    minutes = math.ceil(retry_after / 60)
    wait = f"{retry_after}초" if retry_after < 60 else f"{minutes}분"
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "RATE_LIMITED",
            "message": f"요청이 너무 많습니다. {wait} 후에 다시 시도해 주세요.",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


# 기록 없이 현재 윈도우의 시도 횟수가 한도에 도달했는지 확인(도달했으면 429)
async def check_limit(db: AsyncSession, name: str, value: str, limit: int, window_seconds: int) -> None:
    now = datetime.now(timezone.utc)
    key = bucket_key(name, value)
    count, oldest = (
        await db.execute(
            select(func.count(), func.min(RateLimitEvent.created_at)).where(
                RateLimitEvent.bucket == key,
                RateLimitEvent.created_at > now - timedelta(seconds=window_seconds),
            )
        )
    ).one()
    if count >= limit and oldest is not None:
        oldest = oldest if oldest.tzinfo else oldest.replace(tzinfo=timezone.utc)
        raise rate_limited_error(max(1, math.ceil((oldest + timedelta(seconds=window_seconds) - now).total_seconds())))


# 시도 1회 기록
async def record_attempt(db: AsyncSession, name: str, value: str) -> None:
    db.add(RateLimitEvent(bucket=bucket_key(name, value)))
    await db.commit()


# 한도 확인 후 이번 시도를 기록(메일 발송처럼 요청 자체가 비용인 경우)
async def enforce_limit(db: AsyncSession, name: str, value: str, limit: int, window_seconds: int) -> None:
    await check_limit(db, name, value, limit, window_seconds)
    await record_attempt(db, name, value)


T = TypeVar("T")
NOT_FAILURE_CODES = {"REFRESH_IN_PROGRESS", "RATE_LIMITED"}  # 동시 탭 경합·이미 제한된 요청은 실패로 세지 않음


# 토큰 확인 계열 요청: 한도에 도달했으면 차단하고, 4xx 실패만 기록(정상 요청은 세지 않음)
async def guard_failures(
    db: AsyncSession,
    name: str,
    client_ip: str,
    limit: int,
    window_seconds: int,
    action: Callable[[], Awaitable[T]],
) -> T:
    await check_limit(db, name, client_ip, limit, window_seconds)
    try:
        return await action()
    except HTTPException as error:
        code = error.detail.get("code") if isinstance(error.detail, dict) else None
        if 400 <= error.status_code < 500 and code not in NOT_FAILURE_CODES:
            await record_attempt(db, name, client_ip)
        raise


# 하루 지난 시도 기록 삭제
async def purge_rate_limit_events(db: AsyncSession, commit: bool = True) -> int:
    result = await db.execute(delete(RateLimitEvent).where(RateLimitEvent.created_at < datetime.now(timezone.utc) - timedelta(days=1)))
    if commit:
        await db.commit()
    return result.rowcount or 0
