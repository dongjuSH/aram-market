# 여러 도메인이 함께 쓰는 DB 식별자·결제 금액·받는 분 정보 입력 검증

import re

# PostgreSQL integer 컬럼 상한(이보다 큰 번호는 DB 오류(500) 대신 입력 검증 오류로 처리)
MAX_DB_ID = 2_147_483_647
MIN_CARD_PAYMENT_AMOUNT = 100  # 현재 제공하는 토스 카드 결제의 최소 금액
MAX_ORDER_PAYMENT_AMOUNT = MAX_DB_ID  # 프런트·결제 승인 요청이 안전하게 동일하게 다루는 주문 금액 상한


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


# LIKE 특수문자(%, _, 역슬래시)를 글자 그대로 찾도록 이스케이프(ilike(..., escape="\\")와 함께 사용)
def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
