# 장바구니 담기·수량 변경·삭제·병합 요청 스키마

from typing import Annotated

from pydantic import BaseModel, Field

from backend.core.validators import MAX_DB_ID


MAX_QUANTITY = 99  # 상품당 최대 수량


# 상품 담기(이미 있으면 수량 합산)
class CartAddRequest(BaseModel):
    product_id: int = Field(gt=0, le=MAX_DB_ID)
    quantity: int = Field(default=1, ge=1, le=MAX_QUANTITY)


# 담긴 상품의 수량을 지정 값으로 변경
class CartQuantityRequest(BaseModel):
    quantity: int = Field(ge=1, le=MAX_QUANTITY)


# 선택한 상품 삭제
class CartRemoveRequest(BaseModel):
    product_ids: list[Annotated[int, Field(gt=0, le=MAX_DB_ID)]] = Field(min_length=1, max_length=100)


# 로그인 직전까지 비로그인으로 담은 상품을 계정 장바구니에 합치기
class CartMergeRequest(BaseModel):
    items: list[CartAddRequest] = Field(max_length=100)
