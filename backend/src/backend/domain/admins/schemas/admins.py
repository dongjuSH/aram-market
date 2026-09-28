# 단일 관리자 로그인과 관리 스크립트용 비밀번호 입력 규칙

import re

from pydantic import BaseModel, Field, field_validator


# 관리 스크립트에서 설정할 관리자 비밀번호 길이와 조합 규칙 검증
def validate_password(value: str) -> str:
    if (
        len(value) < 8
        or len(value) > 64
        or not re.search(r"[A-Za-z]", value)
        or not re.search(r"\d", value)
        or not re.search(r"[^A-Za-z0-9]", value)
        or any(character.isspace() for character in value)
    ):
        raise ValueError("비밀번호는 영문, 숫자, 특수문자를 포함한 8~64자로 입력해 주세요.")
    return value


# 고정 아이디 admin과 비밀번호를 받는 관리자 로그인 요청 모델
class SignInRequest(BaseModel):
    username: str = Field(min_length=1, max_length=20)  # 고정 관리자 아이디 admin
    password: str = Field(min_length=1, max_length=64)  # 검증 후 즉시 폐기하는 원문 비밀번호

    # 로그인 아이디의 양끝 공백과 대소문자 차이 제거
    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()
