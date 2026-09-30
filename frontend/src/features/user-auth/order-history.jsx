// 마이 페이지 주문 내역: 주문별 배송 단계, 상품, 배송지, 결제 금액

import { DELIVERY_STEPS, getDeliveryLabel } from '../../config/delivery.js'

// 결제 완료된 주문 목록(최신순)
function OrderHistory({ orders, isLoading }) {
  return (
    <section className="my-page-card my-orders" aria-labelledby="orders-title">
      <div className="my-page-card__heading">
        <div>
          <p>ORDERS</p>
          <h2 id="orders-title">주문·배송</h2>
        </div>
      </div>
      {isLoading ? (
        <p className="my-orders__note" role="status">주문 내역을 불러오고 있습니다.</p>
      ) : orders.length === 0 ? (
        <div className="my-empty">
          <strong>주문 내역이 없어요</strong>
          <span>결제가 완료된 주문이 여기에 표시됩니다.</span>
        </div>
      ) : (
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
                  <div key={`${order.order_id}-${index}`} className="my-orders__item">
                    {item.image_url ? <img src={item.image_url} alt="" /> : <span className="my-orders__noimage" aria-hidden="true" />}
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.unit_price.toLocaleString('ko-KR')}원 · {item.quantity}개</span>
                    </div>
                  </div>
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
      )}
    </section>
  )
}

export default OrderHistory
