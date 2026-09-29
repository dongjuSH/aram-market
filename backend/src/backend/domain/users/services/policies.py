# 약관 종류별 현재 시행 버전과 본문 정의

from dataclasses import dataclass


# 하나의 약관 종류에 대한 시행 버전, 필수 여부 및 본문
@dataclass(frozen=True)
class PolicyDocument:
    policy_type: str  # service, privacy, marketing
    title: str
    version: str  # 본문을 바꿀 때 함께 올리는 시행 버전
    required: bool
    content: str


POLICY_SERVICE = "service"
POLICY_PRIVACY = "privacy"
POLICY_MARKETING = "marketing"

# 현재 시행 중인 약관 목록이며 본문을 수정하면 반드시 version도 올린다
CURRENT_POLICIES: dict[str, PolicyDocument] = {
    POLICY_SERVICE: PolicyDocument(
        POLICY_SERVICE,
        "서비스 이용약관",
        "1.0",
        True,
        "서비스 이용약관\n\n본 약관은 서비스 이용 조건과 회원의 권리·의무를 정합니다. 회원은 정확한 정보를 제공하고 계정 정보를 안전하게 관리해야 하며, 서비스 운영을 방해하거나 타인의 권리를 침해해서는 안 됩니다. 약관 위반 시 이용이 제한될 수 있습니다.",
    ),
    POLICY_PRIVACY: PolicyDocument(
        POLICY_PRIVACY,
        "개인정보 수집 및 이용 동의",
        "1.0",
        True,
        "개인정보 수집 및 이용 동의\n\n수집 항목: 아이디, 닉네임, 이메일, 비밀번호 해시\n이용 목적: 회원 식별, 이메일 소유 확인, 계정 관리, 로그인 보안 및 계정 잠금 해제\n보유 기간: 회원 탈퇴 요청 후 7일간 복구를 위해 보관하며, 유예기간 종료 후 정리 작업을 통해 삭제합니다. 이메일 인증을 완료하지 않은 가입 정보는 24시간 후 삭제합니다.",
    ),
    POLICY_MARKETING: PolicyDocument(
        POLICY_MARKETING,
        "마케팅 정보 수신 동의",
        "1.0",
        False,
        "마케팅 정보 수신 동의\n\n수신 항목: 신상품, 혜택 및 이벤트 안내\n수신 방법: 이메일\n보유 기간: 동의 철회 또는 회원 탈퇴 시까지\n선택 동의 항목으로, 동의하지 않아도 회원 가입과 기본 서비스 이용이 가능합니다.",
    ),
}
