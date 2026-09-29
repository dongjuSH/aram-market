# 로그인 고객이 찜한 상품을 보관하는 DB 모델

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


# 고객당 상품 1행으로 유지되는 찜 항목
class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_wishlist_items_user_product"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    # 회원 삭제 시 함께 정리
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    # 상품이 물리 삭제되면 함께 정리(소프트 삭제 상품은 조회에서 제외)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
