# 주문 생성·결제 승인·배송 상태 변경·환불·취소 요청 스키마

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.address import AddressFields
from backend.core.validators import MAX_DB_ID, MAX_ORDER_PAYMENT_AMOUNT, MIN_CARD_PAYMENT_AMOUNT


# 주문할 상품 한 줄
class OrderLine(BaseModel):
    product_id: int = Field(gt=0, le=MAX_DB_ID)
    quantity: int = Field(ge=1, le=99)


# 주문 배송지: 공통 주소 입력에 배송 요청사항 추가
class ShippingAddress(AddressFields):
    delivery_memo: str = Field(default="", max_length=200)

    @field_validator("delivery_memo")
    @classmethod
    def strip_memo(cls, value: str) -> str:
        return value.strip()


# 주문 생성(가격은 받지 않고 서버가 계산)
class OrderCreateRequest(BaseModel):
    items: list[OrderLine] = Field(min_length=1, max_length=50)
    shipping: ShippingAddress
    from_cart: bool = False  # 장바구니에서 주문했으면 결제 승인 후 해당 상품을 장바구니에서 제거


# 결제창 성공 후 리다이렉트로 받은 값으로 서버 승인 요청
class OrderConfirmRequest(BaseModel):
    payment_key: str = Field(min_length=1, max_length=200)
    order_id: str = Field(min_length=6, max_length=64)
    amount: int = Field(ge=MIN_CARD_PAYMENT_AMOUNT, le=MAX_ORDER_PAYMENT_AMOUNT)


# 관리자가 변경하는 다음 배송 단계
class DeliveryStatusRequest(BaseModel):
    status: str = Field(pattern="^(preparing|shipping|delivered)$")


# 환불·취소 사유 코드와 화면·결제사에 쓰는 이름(고객 목록, 관리자 목록)
CUSTOMER_REFUND_REASONS = {
    "change_of_mind": "단순 변심",
    "wrong_order": "주문 실수(수량·상품 잘못 선택)",
    "delivery_delay": "배송 지연",
    "reorder": "다른 상품으로 재주문",
    "other": "기타",
}
ADMIN_REFUND_REASONS = {
    "customer_request": "고객 요청",
    "out_of_stock": "품절·재고 부족",
    "undeliverable": "배송 불가",
    "other": "기타",
}
REFUND_REASON_LABELS = {**CUSTOMER_REFUND_REASONS, **ADMIN_REFUND_REASONS}


# 사유 공통 검증: '기타'는 직접 입력 필수(1~100자), 다른 사유의 입력 내용은 저장하지 않음
class RefundReasonRequest(BaseModel):
    reason_detail: str = Field(default="", max_length=100)

    @field_validator("reason_detail")
    @classmethod
    def strip_detail(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_other_detail(self):
        if self.reason_code == "other" and not self.reason_detail:
            raise ValueError("기타 사유를 입력해 주세요.")
        if self.reason_code != "other":
            self.reason_detail = ""
        return self


# 고객 즉시 환불(결제완료)·취소 요청(상품준비중)
class CustomerRefundRequest(RefundReasonRequest):
    reason_code: Literal["change_of_mind", "wrong_order", "delivery_delay", "reorder", "other"]


# 관리자 직접 환불
class AdminRefundRequest(RefundReasonRequest):
    reason_code: Literal["customer_request", "out_of_stock", "undeliverable", "other"]


# 관리자 취소 요청 거절(고객에게 그대로 보이는 사유, 필수)
class CancelRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("거절 사유를 입력해 주세요.")
        return value
