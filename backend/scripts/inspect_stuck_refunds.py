# 하루 이상 환불 확인 중인 주문과 토스 조회 결과를 보여 주는 읽기 전용 운영 스크립트(DB·결제 상태 변경 없음)

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.core.database import async_session, engine
from backend.domain.orders.models.orders import Order
from backend.domain.orders.services import toss
from backend.domain.orders.services.refunds import (
    RefundCandidate,
    cancel_reason_text,
    payment_not_refunded,
    refund_matches,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="오래된 refunding 주문을 조회합니다. 이 스크립트는 데이터를 변경하지 않습니다.")
    parser.add_argument("--min-age-hours", type=int, default=24, help="이 시간 이상 지난 주문만 조회합니다(기본 24시간).")
    parser.add_argument("--database-only", action="store_true", help="토스 API를 호출하지 않고 DB 상태만 출력합니다.")
    return parser.parse_args()


async def load_candidates(min_age_hours: int) -> list[RefundCandidate]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=min_age_hours)
    async with async_session() as session:
        orders = (
            await session.execute(
                select(Order)
                .where(
                    Order.status == "refunding",
                    Order.payment_key.is_not(None),
                    Order.refund_attempted_at.is_not(None),
                    Order.refund_attempted_at <= cutoff,
                )
                .order_by(Order.refund_attempted_at, Order.id)
            )
        ).scalars().all()
        return [
            RefundCandidate(
                order_id=order.id,
                order_number=order.order_number,
                payment_key=order.payment_key,
                total_amount=order.total_amount,
                attempt=order.refund_attempt_count,
                cancel_reason=cancel_reason_text(
                    order.refund_actor or "admin", order.refund_reason_code or "other", order.refund_reason_detail
                ),
                attempted_at=order.refund_attempted_at,
            )
            for order in orders
        ]


def gateway_summary(candidate: RefundCandidate, payment: dict | None) -> dict:
    if refund_matches(candidate, payment):
        result = "full_refund_confirmed"
    elif payment_not_refunded(candidate, payment):
        result = "not_refunded_done"
    elif payment is None:
        result = "payment_not_found"
    else:
        result = "manual_review"
    cancels = payment.get("cancels") if isinstance(payment, dict) else None
    return {
        "gateway_result": result,
        "gateway_status": payment.get("status") if isinstance(payment, dict) else None,
        "cancel_statuses": [
            cancel.get("cancelStatus") for cancel in cancels if isinstance(cancel, dict)
        ]
        if isinstance(cancels, list)
        else None,
    }


async def run(min_age_hours: int, database_only: bool) -> int:
    if min_age_hours < 0:
        print("min_age_hours_must_be_non_negative=true")
        return 2
    candidates = await load_candidates(min_age_hours)
    print(f"stuck_refund_count={len(candidates)}")
    lookup_failures = 0
    now = datetime.now(timezone.utc)
    for candidate in candidates:
        attempted_at = candidate.attempted_at
        if attempted_at is not None and attempted_at.tzinfo is None:
            attempted_at = attempted_at.replace(tzinfo=timezone.utc)
        record = {
            "order_number": candidate.order_number,
            "attempt": candidate.attempt,
            "amount": candidate.total_amount,
            "attempted_at": attempted_at.isoformat() if attempted_at else None,
            "age_hours": round((now - attempted_at).total_seconds() / 3600, 1) if attempted_at else None,
            "payment_key_suffix": candidate.payment_key[-6:],
        }
        if not database_only:
            try:
                payment = await toss.get_payment(candidate.payment_key)
                record.update(gateway_summary(candidate, payment))
            except Exception as error:
                lookup_failures += 1
                record.update({"gateway_result": "lookup_error", "error_type": type(error).__name__})
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    print(f"gateway_lookup_failures={lookup_failures}")
    return 1 if lookup_failures else 0


async def main() -> int:
    args = parse_args()
    try:
        return await run(args.min_age_hours, args.database_only)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
