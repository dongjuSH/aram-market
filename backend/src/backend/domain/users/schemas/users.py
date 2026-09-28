# 추후 사용자 로그인·회원가입·계정 찾기·비밀번호 변경·탈퇴 API 입력 형식

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{4,20}$")  # 영문·숫자·밑줄 아이디 규칙
NICKNAME_PATTERN = re.compile(r"^[A-Za-z0-9_가-힣]{2,10}$")  # 한글 포함 화면 표시명 규칙
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")  # 공백과 기본 주소 오류를 막는 이메일 규칙


# 회원가입·계정 찾기 아이디 형식 통일
def normalize_username(value: str) -> str:
    normalized = value.strip().lower()  # 아이디 대소문자 미구분
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError("아이디는 영문, 숫자, 밑줄 4~20자로 입력해 주세요.")
    return normalized


# 비밀번호 길이 및 조합 규칙 검증
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


# 이메일 비교 및 중복 검사용 소문자 정규화
def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) > 254 or not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("올바른 이메일 형식으로 입력해 주세요.")
    return normalized


# 회원가입 화면에서 전달하는 회원정보와 약관 동의값을 검증
class SignUpRequest(BaseModel):
    username: str = Field(min_length=4, max_length=20)  # 중복 불가 로그인 아이디
    password: str = Field(min_length=8, max_length=64)  # DB에는 해시만 저장
    nickname: str = Field(min_length=2, max_length=10)  # 중복 불가 표시명
    email: str = Field(min_length=3, max_length=254)  # 중복 불가 복구 이메일
    service_policy: bool  # 필수 이용약관 동의
    privacy_policy: bool  # 필수 개인정보 동의

    _normalize_username = field_validator("username")(normalize_username)
    _validate_password = field_validator("password")(validate_password)
    _normalize_email = field_validator("email")(normalize_email)

    # 닉네임 양끝 공백 제거 및 문자·길이 검증
    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str) -> str:
        normalized = value.strip()
        if not NICKNAME_PATTERN.fullmatch(normalized):
            raise ValueError("닉네임은 한글, 영문, 숫자, 밑줄 2~10자로 입력해 주세요.")
        return normalized

    # 서비스·개인정보 필수 약관 동의 검증
    @field_validator("service_policy", "privacy_policy")
    @classmethod
    def validate_required_policy(cls, value: bool) -> bool:
        if not value:
            raise ValueError("필수 약관에 동의해 주세요.")
        return value


# 로그인 아이디 및 현재 비밀번호 검증
class SignInRequest(BaseModel):
    username: str = Field(min_length=1, max_length=20)  # 가입 시 정규화된 로그인 아이디
    password: str = Field(min_length=1, max_length=64)  # 현재 비밀번호 원문, 저장하지 않음

    # 로그인 시 가입 형식 오류보다 계정 존재 여부 우선 안내
    @field_validator("username")
    @classmethod
    def normalize_login_username(cls, value: str) -> str:
        return value.strip().lower()


# 아이디 안내 메일용 가입 이메일 검증
class FindUsernameRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)  # 아이디 안내 메일을 받을 가입 이메일

    _normalize_email = field_validator("email")(normalize_email)


# 비밀번호 재설정 메일 요청의 아이디·이메일 조합 검증
class PasswordResetEmailRequest(BaseModel):
    username: str = Field(min_length=4, max_length=20)  # 재설정 대상 아이디
    email: str = Field(min_length=3, max_length=254)  # 해당 아이디의 가입 이메일

    _normalize_username = field_validator("username")(normalize_username)
    _normalize_email = field_validator("email")(normalize_email)


# 메일 단기 토큰 및 새 비밀번호 검증
class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=20, max_length=2048)  # 메일 링크에 포함된 단기 서명 토큰
    new_password: str = Field(min_length=8, max_length=64)  # 교체할 새 비밀번호

    _validate_password = field_validator("new_password")(validate_password)


# 로그인 사용자의 현재 비밀번호 확인 및 새 비밀번호 검증
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=64)  # 본인 확인용 현재 비밀번호
    new_password: str = Field(min_length=8, max_length=64)  # 교체할 새 비밀번호

    _validate_password = field_validator("new_password")(validate_password)


# 회원 탈퇴용 현재 비밀번호 및 확인 문구 검증
class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=64)  # 탈퇴 요청자 본인 확인용 현재 비밀번호
    confirmation: Literal["회원 탈퇴"]  # 오작동을 막는 고정 확인 문구


# 7일 유예기간에 발급한 탈퇴 복구 토큰 검증
class CancelWithdrawalRequest(BaseModel):
    recovery_token: str = Field(min_length=20, max_length=2048)  # 로그인 검증 후 발급한 10분 복구 토큰
