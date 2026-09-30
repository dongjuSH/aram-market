# 여러 도메인(회원·주문)이 함께 쓰는 이름·휴대폰 입력 검증

import re


# 공백을 제거한 이름이 2~30자인지 확인
def normalize_person_name(value: str) -> str:
    normalized = value.strip()
    if len(normalized) < 2 or len(normalized) > 30:
        raise ValueError("이름을 2~30자로 입력해 주세요.")
    return normalized


# 숫자만 남겨 휴대폰 번호인지 확인하고 010-1234-5678 형식으로 정규화
def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if not re.fullmatch(r"01[016789]\d{7,8}", digits):
        raise ValueError("휴대폰 번호를 010-1234-5678 형식으로 입력해 주세요.")
    return f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"
