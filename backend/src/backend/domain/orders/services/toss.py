# 토스페이먼츠 결제 승인·조회 API 호출

from urllib.parse import quote

import httpx
from fastapi import status

from backend.core.config import settings
from backend.core.errors import api_error


# 응답 본문을 JSON 객체로 읽음(본문이 깨졌거나 객체가 아니면 None)
def _json_object(response: httpx.Response) -> dict | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


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
    payload = _json_object(response)
    if response.status_code == 200 and payload is None:
        # 승인은 됐을 수도 있으므로 실패로 보내지 않고 "결과 불확정"으로 알림(주문 서비스가 결제사에 다시 조회)
        raise api_error(status.HTTP_502_BAD_GATEWAY, "PAYMENT_RESPONSE_INVALID", "결제 결과를 확인하지 못했습니다.")
    payload = payload or {}
    if response.status_code != 200:
        raise api_error(
            status.HTTP_400_BAD_REQUEST,
            "PAYMENT_FAILED",
            str(payload.get("message") or "결제 승인에 실패했습니다."),
            gateway_code=payload.get("code"),
            gateway_status=response.status_code,  # 확정 거절(4xx)과 불확정(409·429·5xx)을 구분하는 데 사용
        )
    return payload


# 결제키로 결제 상태 조회(정리 작업의 미확정 주문 확인용). 결제가 없으면 None, 조회 실패는 예외
async def get_payment(payment_key: str) -> dict | None:
    if not settings.toss_secret_key:
        raise RuntimeError("TOSS_SECRET_KEY가 설정되지 않았습니다.")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{settings.toss_api_base}/v1/payments/{quote(payment_key, safe='')}",
            auth=(settings.toss_secret_key, ""),
        )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise RuntimeError(f"결제 조회 실패 status={response.status_code}")
    payload = _json_object(response)
    if payload is None:
        raise RuntimeError("결제 조회 응답 형식이 올바르지 않습니다.")
    return payload
