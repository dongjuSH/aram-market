# 후기 작성·수정 요청 스키마

from pydantic import BaseModel, Field, field_validator


# 후기 작성·수정 공통 입력(별점 1~5, 내용 10~1000자)
class ReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def content_length(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("후기는 10자 이상 입력해 주세요.")
        return value
