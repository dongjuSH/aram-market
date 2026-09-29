# 로그인 고객의 상품 문의와 관리자 답변을 보관하는 DB 모델

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


# 상품 문의 1건(비밀글은 작성자와 관리자만 내용을 볼 수 있음)
class ProductInquiry(Base):
    __tablename__ = "product_inquiries"
    __table_args__ = (Index("ix_product_inquiries_product_created", "product_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    # 탈퇴해도 문의는 남기되 작성자는 '탈퇴한 회원'으로 표시
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 관리자 답변(없으면 답변 대기)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
