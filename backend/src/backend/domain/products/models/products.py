# 전역 상품 카탈로그, 확장 가능한 카테고리 및 관련 상품 연결 DB 모델

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


# 관리자가 추가·비활성화할 수 있는 상품 분류 테이블
class ProductCategory(Base):
    __tablename__ = "product_categories"
    __table_args__ = (UniqueConstraint("code", name="uq_product_categories_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# 단일 관리자가 관리하는 전역 상품 카탈로그 테이블
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index(
            "uq_products_active_code",
            "code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_products_active_display_order",
            "display_order",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        CheckConstraint("display_order >= 1", name="ck_products_display_order_positive"),
        CheckConstraint("price >= 0", name="ck_products_price_nonnegative"),
        CheckConstraint("stock >= 0", name="ck_products_stock_nonnegative"),
        CheckConstraint("status IN ('active', 'deleted')", name="ck_products_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("product_categories.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 판매 가능 수량. 결제 승인 직전에 차감하고 미결제 확정·환불 완료 시 되돌림(033)
    stock: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    image_name: Mapped[str] = mapped_column(String(255), nullable=False)
    image_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active", index=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# 상품당 최대 두 개의 같은 카테고리 관련 상품 연결 테이블
class ProductRelation(Base):
    __tablename__ = "product_relations"
    __table_args__ = (
        CheckConstraint("product_id <> related_product_id", name="ck_product_relations_not_self"),
    )

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    related_product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)


# 상품 변경 시각·필드별 이전/이후 값을 보존하는 감사 로그
class ProductAuditLog(Base):
    __tablename__ = "product_audit_logs"
    __table_args__ = (
        CheckConstraint("action IN ('created', 'updated', 'deleted', 'restored')", name="ck_product_audit_logs_action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    changes: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
