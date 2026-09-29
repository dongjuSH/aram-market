# 문의 작성·관리자 답변 요청 스키마

from pydantic import BaseModel, Field, field_validator


# 문의 작성(내용 5~1000자, 비밀글 선택)
class InquiryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    is_secret: bool = False

    @field_validator("content")
    @classmethod
    def content_length(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("문의 내용은 5자 이상 입력해 주세요.")
        return value


# 관리자 답변(1~1000자)
class InquiryAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=1000)

    @field_validator("answer")
    @classmethod
    def answer_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("답변 내용을 입력해 주세요.")
        return value
