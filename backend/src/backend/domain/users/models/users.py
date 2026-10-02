# 고객 인증·로그인 잠금·탈퇴 생명주기 DB 모델

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


# 사용자 인증, 약관 동의, 로그인 잠금 및 탈퇴 상태를 보관하는 테이블
class User(Base):
    # public.users 테이블과 연결
    __tablename__ = "users"

    # DB에서 허용하는 계정 상태 제한
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'pending_deletion', 'withdrawn')",
            name="ck_users_status",
        ),
    )

    # 가입 순서대로 생성되는 내부 고유번호
    id: Mapped[int] = mapped_column(primary_key=True)

    # 로그인 아이디
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    # 기존 password 컬럼명을 유지하되 애플리케이션에서는 해시값만 취급
    password_hash: Mapped[str] = mapped_column("password", String(255), nullable=False)

    # 화면 표시명
    nickname: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)

    # 계정 복구 이메일
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)

    # 가입 시각
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 계정 사용 가능 여부(False이면 관리자가 비활성화한 계정)
    is_active: Mapped[bool] = mapped_column(default=True)

    # 연속 비밀번호 실패 횟수
    login_fail_count: Mapped[int] = mapped_column(default=0)

    # 로그인 잠금 만료 시각(None이면 잠기지 않은 상태)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 계정 생명주기 상태(active, pending_deletion, withdrawn)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)

    # 탈퇴 접수 시각(None이면 탈퇴를 신청하지 않은 상태)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 비밀번호 변경 시 증가시켜 기존 인증 토큰을 무효화
    auth_version: Mapped[int] = mapped_column(default=0)

    # 서비스 이용약관 필수 동의
    service_policy: Mapped[bool] = mapped_column(default=False)

    # 개인정보 수집 필수 동의
    privacy_policy: Mapped[bool] = mapped_column(default=False)

    # 상품·혜택 이메일 수신에 대한 선택 동의
    marketing_consent: Mapped[bool] = mapped_column(default=False, nullable=False)

    # 이메일 소유 확인 완료 시각(None이면 미인증 계정이며 로그인 불가)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 마지막 인증 메일 발송 시각(재발송 남용 방지)
    email_verification_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# 약관 종류·시행 버전·동의 여부와 동의 시각을 변경 이력으로 보관하는 테이블
class UserPolicyConsent(Base):
    __tablename__ = "user_policy_consents"

    __table_args__ = (
        CheckConstraint(
            "policy_type IN ('service', 'privacy', 'marketing')",
            name="ck_user_policy_consents_type",
        ),
        Index("ix_user_policy_consents_user_type", "user_id", "policy_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # 회원 삭제 시 함께 정리되는 동의 주체
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # service, privacy, marketing 중 하나
    policy_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 동의 당시 시행 중이던 약관 버전
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # 동의(True) 또는 철회·거부(False)
    agreed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # 동의·철회 시각
    agreed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# 로그인 세션별 리프레시 토큰(해시만 저장)과 회전·재사용 탐지 상태를 보관하는 테이블
class UserRefreshToken(Base):
    __tablename__ = "user_refresh_tokens"

    __table_args__ = (Index("ix_user_refresh_tokens_family", "family_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    # 회원 삭제 시 함께 정리되는 토큰 주인
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    # 한 번의 로그인에서 회전되는 토큰들을 묶는 식별자(재사용 탐지 시 일괄 폐기)
    family_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # 원문 대신 저장하는 SHA-256 해시
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # 발급 당시 인증 버전(비밀번호 변경·탈퇴 시 불일치하여 무효)
    auth_version: Mapped[int] = mapped_column(nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # 회전·로그아웃·재사용 탐지로 폐기된 시각(None이면 사용 가능)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# 회원의 배송지 주소록(최대 10개, 기본 배송지는 회원당 1개)
class UserAddress(Base):
    __tablename__ = "user_addresses"

    # 기본 배송지가 회원당 둘 이상이 되지 않도록 DB가 보장
    __table_args__ = (
        Index("uq_user_addresses_default", "user_id", unique=True, postgresql_where=text("is_default")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # 회원 삭제 시 함께 정리
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    label: Mapped[str] = mapped_column(String(20), nullable=False)  # 명칭(집, 회사 등)
    recipient_name: Mapped[str] = mapped_column(String(30), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    postcode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address: Mapped[str] = mapped_column(String(200), nullable=False)
    address_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
