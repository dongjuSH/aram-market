# 상품 등록·수정 입력값과 목록 조회 조건 검증 스키마

import base64
import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.validators import MAX_DB_ID, MAX_ORDER_PAYMENT_AMOUNT, MIN_CARD_PAYMENT_AMOUNT


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif"}  # 화면에서 허용하는 이미지 MIME 형식
IMAGE_DATA_PATTERN = re.compile(r"^data:([^;]+);base64,(.+)$", re.DOTALL)
UPLOAD_SESSION_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


# 공통 이미지 data URL 형식과 5MB 제한 검증
def validate_image_data_value(value: str | None) -> str | None:
    if value is None:
        return None
    matched = IMAGE_DATA_PATTERN.fullmatch(value)
    if not matched or matched.group(1).lower() not in ALLOWED_IMAGE_TYPES:
        raise ValueError("JPG, JPEG, PNG, GIF 이미지만 등록할 수 있습니다.")
    try:
        image_bytes = base64.b64decode(matched.group(2), validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError("이미지 데이터가 올바르지 않습니다.") from error
    if len(image_bytes) > 5 * 1024 * 1024:
        raise ValueError("이미지 파일은 5MB 이하만 등록할 수 있습니다.")
    return value


# 상품 생성과 수정에서 공통으로 받는 전체 입력값
class ProductWriteRequest(BaseModel):
    visible: bool
    display_order: int = Field(ge=1, le=2_147_483_647)
    category_id: int = Field(gt=0, le=MAX_DB_ID)
    name: str = Field(min_length=1, max_length=50)
    code: str = Field(min_length=1, max_length=50)
    price: int = Field(ge=MIN_CARD_PAYMENT_AMOUNT, le=MAX_ORDER_PAYMENT_AMOUNT)
    image_data: str | None = None
    image_name: str = Field(min_length=1, max_length=255)
    image_description: str | None = Field(default=None, max_length=200)
    detail_html: str = Field(default="", max_length=200_000)
    related_product_ids: list[Annotated[int, Field(gt=0, le=MAX_DB_ID)]] = Field(default_factory=list, max_length=2)
    editor_upload_session_id: str | None = Field(default=None, pattern=UPLOAD_SESSION_PATTERN)

    # 상품명·코드·설명·파일명의 불필요한 양끝 공백 제거
    @field_validator("name", "image_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("필수 입력값을 입력해 주세요.")
        return normalized

    # 대소문자만 다른 상품코드도 같은 코드로 취급하도록 대문자 정규화
    @field_validator("code")
    @classmethod
    def normalize_product_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("상품코드를 입력해 주세요.")
        return normalized

    # 선택 설명의 빈 문자열을 미입력값으로 정규화
    @field_validator("image_description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else ""
        return normalized or None

    # 허용 이미지 형식과 디코딩 후 5MB 제한 검증
    @field_validator("image_data")
    @classmethod
    def validate_image_data(cls, value: str | None) -> str | None:
        return validate_image_data_value(value)

    # 관련 상품의 중복 선택 차단
    @model_validator(mode="after")
    def validate_related_products(self):
        if len(set(self.related_product_ids)) != len(self.related_product_ids):
            raise ValueError("같은 관련 상품을 중복 선택할 수 없습니다.")
        return self


# 신규 상품 전체 필드 입력 스키마
class ProductCreateRequest(ProductWriteRequest):
    # 신규 등록에는 반드시 원본 이미지 필요
    @model_validator(mode="after")
    def require_image(self):
        if not self.image_data:
            raise ValueError("상품 이미지를 첨부해 주세요.")
        return self


# 기존 상품 전체 필드 교체 스키마
class ProductUpdateRequest(ProductWriteRequest):
    pass


# 에디터 본문 이미지의 Storage 업로드 입력
class EditorImageUploadRequest(BaseModel):
    image_data: str = Field(min_length=1)
    category_id: int = Field(gt=0, le=MAX_DB_ID)
    product_id: int | None = Field(default=None, gt=0, le=MAX_DB_ID)
    upload_session_id: str = Field(pattern=UPLOAD_SESSION_PATTERN)

    _validate_image_data = field_validator("image_data")(validate_image_data_value)
