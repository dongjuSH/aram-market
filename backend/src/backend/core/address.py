# 주문 배송지와 주소록이 함께 쓰는 받는 분·연락처·주소 입력 모델과 검증

from pydantic import BaseModel, Field, field_validator

from backend.core.validators import normalize_person_name, normalize_phone


# 받는 분·휴대폰·주소(우편번호·상세주소는 선택) 공통 입력
class AddressFields(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=30)
    recipient_phone: str = Field(min_length=1, max_length=20)
    postcode: str = Field(default="", max_length=10)
    address: str = Field(min_length=1, max_length=200)
    address_detail: str = Field(default="", max_length=100)

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
