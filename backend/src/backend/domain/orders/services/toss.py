# 토스페이먼츠 결제 승인 API 호출

import httpx
from fastapi import status

from backend.core.config import settings
from backend.core.errors import api_error


# 결제창에서 받은 paymentKey를 서버에서 승인(금액·주문번호는 서버 값 사용). 멱등 키로 중복 승인을 막음
async def confirm_payment(payment_key: str, order_number: str, amount: int) -> dict:
    if not settings.toss_secret_key:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "PAYMENT_NOT_CONFIGURED", "결제 설정이 완료되지 않았습니다.")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{settings.toss_api_base}/v1/payments/confirm",
                auth=(settings.toss_secret_key, ""),
                headers={"Idempotency-Key": order_number},
                json={"paymentKey": payment_key, "orderId": order_number, "amount": amount},
            )
    except httpx.HTTPError as error:
        raise api_error(status.HTTP_502_BAD_GATEWAY, "PAYMENT_GATEWAY_UNAVAILABLE", "결제 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.") from error
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if response.status_code != 200:
        raise api_error(
            status.HTTP_400_BAD_REQUEST,
            "PAYMENT_FAILED",
            str(payload.get("message") or "결제 승인에 실패했습니다."),
            gateway_code=payload.get("code"),
        )
    return payload
