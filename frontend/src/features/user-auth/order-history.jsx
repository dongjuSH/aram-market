// 주문 카드 목록(배송 단계, 상품, 배송지, 결제 금액)과 마이 페이지 최근 주문 요약

import { DELIVERY_STEPS, getDeliveryLabel } from '../../config/delivery.js'
import { getCustomerProductDetailPath, USER_ORDERS_PATH } from '../../config/routes.js'

export const RECENT_ORDER_COUNT = 3 // 마이 페이지에 보여줄 최근 주문 수

// 주문 상품 한 줄(이미지·이름·가격), 상품이 남아 있으면 누를 때 상품 상세로 이동
function OrderItem({ item, onNavigate }) {
  const content = (
    <>
      {item.image_url ? <img src={item.image_url} alt="" /> : <span className="my-orders__noimage" aria-hidden="true" />}
      <div>
        <strong>{item.name}</strong>
        <span>{item.unit_price.toLocaleString('ko-KR')}원 · {item.quantity}개</span>
      </div>
    </>
  )
  if (!item.product_id) return <div className="my-orders__item">{content}</div> // 상품 행이 삭제된 지난 주문
  const detailPath = getCustomerProductDetailPath(item.product_id)
  return (
    <a
      className="my-orders__item my-orders__item--link"
      href={detailPath}
      onClick={(event) => {
        event.preventDefault()
        onNavigate(detailPath)
      }}
    >
      {content}
    </a>
  )
}

// 결제 완료된 주문 카드 목록(마이 페이지·주문 목록 페이지 공용)
export function OrderList({ orders, onNavigate }) {
  return (
    <ul className="my-orders__list">
      {orders.map((order) => {
        const currentStep = DELIVERY_STEPS.findIndex((step) => step.key === order.delivery_status)
        return (
          <li key={order.order_id} className="my-orders__order">
            <div className="my-orders__meta">
              <strong>{new Date(order.paid_at || order.created_at).toLocaleDateString('ko-KR')} 결제</strong>
              <span>주문번호 {order.order_id}</span>
            </div>
            <ol className="delivery-steps" aria-label={`배송 상태: ${getDeliveryLabel(order.delivery_status)}`}>
              {DELIVERY_STEPS.map((step, index) => (
                <li key={step.key} className={index <= currentStep ? 'is-done' : ''} aria-current={index === currentStep ? 'step' : undefined}>
                  {step.label}
                </li>
              ))}
            </ol>
            {order.items.map((item, index) => (
              <OrderItem key={`${order.order_id}-${index}`} item={item} onNavigate={onNavigate} />
            ))}
            {order.shipping && (
              <p className="my-orders__address">
                <strong>{order.shipping.recipient_name}</strong> · {order.shipping.recipient_phone}<br />
                {order.shipping.postcode ? `[${order.shipping.postcode}] ` : ''}{order.shipping.address} {order.shipping.address_detail}
                {order.shipping.delivery_memo && <><br />요청사항: {order.shipping.delivery_memo}</>}
              </p>
            )}
            <div className="my-orders__total">
              <span>결제 금액</span>
              <strong>{order.total_amount.toLocaleString('ko-KR')}원</strong>
            </div>
          </li>
        )
      })}
    </ul>
  )
}

// 마이 페이지 최근 주문 요약과 전체 주문 목록 링크
function OrderHistory({ orders, total, isLoading, onNavigate }) {
  return (
    <section className="my-page-card my-orders" aria-labelledby="orders-title">
      <div className="my-page-card__heading">
        <div>
          <p>ORDERS</p>
          <h2 id="orders-title">주문·배송</h2>
        </div>
        {total > 0 && (
          <a
            className="my-orders__more"
            href={USER_ORDERS_PATH}
            onClick={(event) => {
              event.preventDefault()
              onNavigate(USER_ORDERS_PATH)
            }}
          >
            전체 보기 <span aria-hidden="true">›</span>
          </a>
        )}
      </div>
      {isLoading ? (
        <p className="my-orders__note" role="status">주문 내역을 불러오고 있습니다.</p>
      ) : orders.length === 0 ? (
        <div className="my-empty">
          <strong>주문 내역이 없어요</strong>
          <span>결제가 완료된 주문이 여기에 표시됩니다.</span>
        </div>
      ) : (
        <OrderList orders={orders} onNavigate={onNavigate} />
      )}
    </section>
  )
}

export default OrderHistory
