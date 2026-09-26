# 사용자 인증 정보, 로그인 잠금 및 탈퇴 생명주기를 저장하는 DB 모델

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


# 회원 인증, 약관 동의, 로그인 잠금 및 탈퇴 상태를 보관하는 테이블
class User(Base):
    # Supabase의 public.users 테이블과 연결
    __tablename__ = "users"

    # DB에서 허용하는 계정 상태 제한
    __table_args__ = (CheckConstraint("status IN ('active', 'pending_deletion', 'withdrawn')", name="ck_users_status"),)

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
