# 주문과 주문 상품(가격·상품명 스냅샷), 결제 결과를 보관하는 DB 모델

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


# 고객 주문 1건(결제 승인 전에는 pending)
class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'paid', 'failed', 'refunding', 'refunded')", name="ck_orders_status"),
        CheckConstraint("delivery_status IN ('paid', 'preparing', 'shipping', 'delivered')", name="ck_orders_delivery_status"),
        CheckConstraint(
            "cancel_request_status IS NULL OR cancel_request_status IN ('requested', 'approved', 'rejected')", name="ck_orders_cancel_request_status"
        ),
        CheckConstraint(
            "cancel_request_reason_code IS NULL OR cancel_request_reason_code IN "
            "('change_of_mind', 'wrong_order', 'delivery_delay', 'reorder', 'other')",
            name="ck_orders_cancel_request_reason_code",
        ),
        CheckConstraint("refund_actor IS NULL OR refund_actor IN ('customer', 'admin')", name="ck_orders_refund_actor"),
        CheckConstraint(
            "refund_reason_code IS NULL OR refund_reason_code IN ('change_of_mind', 'wrong_order', 'delivery_delay', 'reorder', "
            "'customer_request', 'out_of_stock', 'undeliverable', 'other')",
            name="ck_orders_refund_reason_code",
        ),
        CheckConstraint("refund_attempt_count >= 0", name="ck_orders_refund_attempt_count"),
        Index("ix_orders_user_created", "user_id", "created_at"),
        Index("ix_orders_refunding_attempted_at", "refund_attempted_at", postgresql_where=text("status = 'refunding'")),
        Index("ix_orders_cancel_requested", "cancel_requested_at", postgresql_where=text("cancel_request_status = 'requested'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # 결제사에 넘기는 주문 식별자(6~64자 영숫자·-·_)
    order_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)

    # 회원 탈퇴로 계정이 삭제돼도 거래 기록은 남기도록 SET NULL
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    order_name: Mapped[str] = mapped_column(String(100), nullable=False)  # 결제창에 표시할 주문명

    # 서버가 상품 가격으로 계산한 결제 금액(원)
    total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # 결제 승인 후 장바구니에서 구매한 상품을 비울지 여부
    from_cart: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    payment_key: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    # 주문 생성 시각과 분리해 실제 승인 요청 이후에만 결제사 재조회를 시작하기 위한 기준 시각
    payment_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # 배송 정보(결제 전 입력, 기존 주문은 없을 수 있음)
    recipient_name: Mapped[str | None] = mapped_column(String(30), nullable=True)
    recipient_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    postcode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_memo: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 결제 완료 후 진행 상태(결제완료 → 상품준비중 → 배송중 → 배송완료). 관리자가 한 단계씩 변경
    delivery_status: Mapped[str] = mapped_column(String(20), default="paid", server_default="paid", nullable=False)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 고객 취소 요청(상품준비중 주문만, 주문당 1회): requested → approved(관리자 승인·환불 진행) 또는 rejected(거절 사유 필수)
    cancel_request_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_request_reason_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    cancel_request_reason_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)  # '기타' 직접 입력
    cancel_rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reject_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 전액 환불(결제사 결제 취소): 처리 주체·사유, 멱등키에 쓰는 시도 횟수, 결과
    # 환불을 시작한 주체(처리자 아님): 고객 즉시 취소·고객 요청 승인은 customer, 관리자 직접 환불은 admin. 승인 여부는 cancel_request_status
    refund_actor: Mapped[str | None] = mapped_column(String(20), nullable=True)
    refund_reason_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    refund_reason_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)
    refund_attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    refund_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_transaction_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    refund_failure_message: Mapped[str | None] = mapped_column(String(300), nullable=True)  # 최근 환불 실패 안내
    refund_delivery_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 환불 시작 시점의 배송 단계
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# 주문 당시의 상품명·가격·수량 스냅샷(이후 상품이 바뀌어도 주문 내역은 유지)
class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity BETWEEN 1 AND 99", name="ck_order_items_quantity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)

    # 상품이 물리 삭제돼도 주문 내역은 남도록 SET NULL
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)

    product_name: Mapped[str] = mapped_column(String(50), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    unit_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
