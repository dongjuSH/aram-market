# DB에 시도 기록을 남겨 서버 재시작·다중 서버에서도 유지되는 슬라이딩 윈도우 요청 제한

import hashlib
import hmac
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import DateTime, String, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.config import settings
from backend.core.database import Base

logger = logging.getLogger(__name__)


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


# 같은 버킷의 "횟수 확인 + 기록"을 한 트랜잭션에서 버킷 단위 잠금으로 직렬화해 이번 시도를 예약(기록 id 반환)
# 동시 요청이 모두 기록 전 횟수를 읽고 통과하는 경쟁을 막는다(잠금은 커밋 시 자동 해제, 서버 여러 대에서도 동일)
async def reserve_attempt(db: AsyncSession, name: str, value: str, limit: int, window_seconds: int) -> int:
    now = datetime.now(timezone.utc)
    key = bucket_key(name, value)
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:bucket, 0))"), {"bucket": key})
    count, oldest = (
        await db.execute(
            select(func.count(), func.min(RateLimitEvent.created_at)).where(
                RateLimitEvent.bucket == key,
                RateLimitEvent.created_at > now - timedelta(seconds=window_seconds),
            )
        )
    ).one()
    if count >= limit and oldest is not None:
        await db.commit()  # 잠금 해제(바꾼 데이터 없음)
        oldest = oldest if oldest.tzinfo else oldest.replace(tzinfo=timezone.utc)
        raise rate_limited_error(max(1, math.ceil((oldest + timedelta(seconds=window_seconds) - now).total_seconds())))
    event = RateLimitEvent(bucket=key)
    db.add(event)
    await db.commit()
    return event.id


# 예약 기록 삭제를 현재 트랜잭션에 넣기만 함(호출한 쪽의 변경과 같은 커밋으로 반영)
async def discard_attempt(db: AsyncSession, attempt_id: int) -> None:
    await db.execute(delete(RateLimitEvent).where(RateLimitEvent.id == attempt_id))


# 실패가 아니었던 시도의 예약 기록을 지움(정상 요청은 횟수에 넣지 않음)
async def release_attempt(db: AsyncSession, attempt_id: int) -> None:
    await discard_attempt(db, attempt_id)
    await db.commit()


# 한도 확인 후 이번 시도를 기록(메일 발송처럼 요청 자체가 비용인 경우)
async def enforce_limit(db: AsyncSession, name: str, value: str, limit: int, window_seconds: int) -> None:
    await reserve_attempt(db, name, value, limit, window_seconds)


T = TypeVar("T")
NOT_FAILURE_CODES = {"REFRESH_IN_PROGRESS", "RATE_LIMITED"}  # 동시 탭 경합·이미 제한된 요청은 실패로 세지 않음


# 기본 실패 기준: 4xx 응답(동시 탭 경합·요청 제한 제외)
def is_client_failure(error: HTTPException) -> bool:
    code = error.detail.get("code") if isinstance(error.detail, dict) else None
    return 400 <= error.status_code < 500 and code not in NOT_FAILURE_CODES


# 실패만 세는 요청: 시도를 먼저 예약해 동시 요청도 한도 안에서만 통과시키고, 실패가 아니면 예약을 지움
async def guard_failures(
    db: AsyncSession,
    name: str,
    value: str,
    limit: int,
    window_seconds: int,
    action: Callable[[], Awaitable[T]],
    is_failure: Callable[[HTTPException], bool] = is_client_failure,
) -> T:
    attempt_id = await reserve_attempt(db, name, value, limit, window_seconds)
    try:
        result = await action()
    except HTTPException as error:
        if not is_failure(error):
            await db.rollback()  # 처리 중 남은 미완료 변경이 예약 삭제 커밋에 섞이지 않게 함
            await release_attempt(db, attempt_id)
        raise
    except Exception:
        try:
            await db.rollback()
            await release_attempt(db, attempt_id)
        except Exception:
            # 서버 오류 원인을 가리지 않도록 예약 정리 실패는 경고만 남김(하루 뒤 정리 작업이 삭제)
            logger.warning("rate limit reservation cleanup failed bucket=%s", name, exc_info=True)
        raise
    await release_attempt(db, attempt_id)
    return result


# 하루 지난 시도 기록 삭제
async def purge_rate_limit_events(db: AsyncSession, commit: bool = True) -> int:
    result = await db.execute(delete(RateLimitEvent).where(RateLimitEvent.created_at < datetime.now(timezone.utc) - timedelta(days=1)))
    if commit:
        await db.commit()
    return result.rowcount or 0
