# 주문 배송지와 주소록이 함께 쓰는 받는 분·연락처·주소 입력 모델과 검증

import re

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.validators import normalize_person_name, normalize_phone


POSTCODE_PATTERN = re.compile(r"^\d{5}$")  # 도로명 주소 우편번호(국가기초구역번호) 5자리


# 받는 분·휴대폰·우편번호·주소·상세주소 공통 입력(상세주소는 '상세 주소 없음'을 고른 경우만 비울 수 있음)
class AddressFields(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=30)
    recipient_phone: str = Field(min_length=1, max_length=20)
    postcode: str = Field(max_length=10)
    address: str = Field(min_length=1, max_length=200)
    address_detail: str = Field(default="", max_length=100)
    no_address_detail: bool = False  # 단독주택처럼 동·호수가 없는 주소

    _normalize_name = field_validator("recipient_name")(normalize_person_name)
    _normalize_phone = field_validator("recipient_phone")(normalize_phone)

    @field_validator("postcode", "address", "address_detail")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("address")
    @classmethod
    def address_length(cls, value: str) -> str:
        if len(value) < 5:
            raise ValueError("주소를 5자 이상 입력해 주세요.")
        return value

    @field_validator("postcode")
    @classmethod
    def postcode_format(cls, value: str) -> str:
        if not POSTCODE_PATTERN.match(value):
            raise ValueError("주소 검색으로 우편번호를 입력해 주세요.")
        return value

    # 상세 주소 없음을 고르면 상세 주소를 비우고, 아니면 상세 주소 필수
    @model_validator(mode="after")
    def detail_required(self):
        if self.no_address_detail:
            self.address_detail = ""
        elif not self.address_detail:
            raise ValueError("상세 주소를 입력하거나 '상세 주소 없음'을 선택해 주세요.")
        return self
