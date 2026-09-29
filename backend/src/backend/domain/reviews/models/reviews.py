# 구매 고객이 작성한 상품 후기(별점·내용)를 보관하는 DB 모델

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


# 고객당 상품 1개에 후기 1건
class ProductReview(Base):
    __tablename__ = "product_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_product_reviews_user_product"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_product_reviews_rating"),
        Index("ix_product_reviews_product_created", "product_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    # 탈퇴해도 후기는 남기되 작성자는 '탈퇴한 회원'으로 표시
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    rating: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
