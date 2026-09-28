# 단일 관리자 인증과 토큰 무효화 상태를 보관하는 DB 모델

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


# 상품 관리 시스템에 한 개만 존재하는 관리자 계정 모델
class AdminAccount(Base):
    __tablename__ = "admin_accounts"
    __table_args__ = (
        CheckConstraint("username = 'admin'", name="ck_admin_accounts_single_username"),
        UniqueConstraint("username", name="uq_admin_accounts_username"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # 내부 참조용 고유번호
    username: Mapped[str] = mapped_column(String(20), nullable=False)  # 고정 관리자 아이디 admin
    password_hash: Mapped[str] = mapped_column("password", String(255), nullable=False)  # PBKDF2 해시만 저장
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # 긴급 접근 차단용 상태
    auth_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 관리 스크립트 재설정 시 토큰 무효화 버전
