# 주문 생성·결제 승인·배송 상태 변경 요청 스키마

from pydantic import BaseModel, Field, field_validator

from backend.core.address import AddressFields
from backend.core.validators import MAX_DB_ID


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
    amount: int = Field(gt=0, le=MAX_DB_ID)


# 관리자가 변경하는 다음 배송 단계
class DeliveryStatusRequest(BaseModel):
    status: str = Field(pattern="^(preparing|shipping|delivered)$")
