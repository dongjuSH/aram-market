# 주문 생성·결제 승인·배송 상태 변경 요청 스키마

import re

from pydantic import BaseModel, Field, field_validator


# 주문할 상품 한 줄
class OrderLine(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=99)


# 배송지 입력(받는 분·휴대폰·주소)
class ShippingAddress(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=30)
    recipient_phone: str = Field(min_length=1, max_length=20)
    postcode: str = Field(default="", max_length=10)
    address: str = Field(min_length=1, max_length=200)
    address_detail: str = Field(default="", max_length=100)
    delivery_memo: str = Field(default="", max_length=200)

    @field_validator("recipient_name", "address", "address_detail", "postcode", "delivery_memo")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("recipient_name")
    @classmethod
    def name_length(cls, value: str) -> str:
        if len(value) < 2:
            raise ValueError("받는 분 이름을 2자 이상 입력해 주세요.")
        return value

    @field_validator("address")
    @classmethod
    def address_length(cls, value: str) -> str:
        if len(value) < 5:
            raise ValueError("주소를 5자 이상 입력해 주세요.")
        return value

    # 010-1234-5678 형식으로 정규화
    @field_validator("recipient_phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if not re.fullmatch(r"01[016789]\d{7,8}", digits):
            raise ValueError("휴대폰 번호를 010-1234-5678 형식으로 입력해 주세요.")
        return f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"


# 주문 생성(가격은 받지 않고 서버가 계산)
class OrderCreateRequest(BaseModel):
    items: list[OrderLine] = Field(min_length=1, max_length=50)
    shipping: ShippingAddress
    from_cart: bool = False  # 장바구니에서 주문했으면 결제 승인 후 해당 상품을 장바구니에서 제거


# 결제창 성공 후 리다이렉트로 받은 값으로 서버 승인 요청
class OrderConfirmRequest(BaseModel):
    payment_key: str = Field(min_length=1, max_length=200)
    order_id: str = Field(min_length=6, max_length=64)
    amount: int = Field(gt=0)


# 관리자가 변경하는 다음 배송 단계
class DeliveryStatusRequest(BaseModel):
    status: str = Field(pattern="^(preparing|shipping|delivered)$")
