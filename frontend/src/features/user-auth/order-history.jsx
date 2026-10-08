// 주문 카드 목록(배송 단계·취소/환불 상태, 상품, 배송지, 결제 금액, 주문 취소·취소 요청)과 마이 페이지 최근 주문 요약

import { useState } from 'react'
import { refundOrder, requestOrderCancel } from '../../api/orders.js'
import Modal from '../../components/common/modal.jsx'
import ReasonModal from '../../components/common/reason-modal.jsx'
import { DELIVERY_STEPS, getDeliveryLabel } from '../../config/delivery.js'
import { CUSTOMER_REFUND_REASONS, getCancelBadge, getCustomerCancelAction, getReasonText, isRefundPending } from '../../config/refund.js'
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

const formatDateTime = (value) => (value ? new Date(value).toLocaleString('ko-KR', { dateStyle: 'medium', timeStyle: 'short' }) : '')

// 취소 요청·거절·환불 진행 상황 안내(해당 없으면 표시하지 않음)
function CancelStatusNote({ order }) {
  const { cancel_request: cancelRequest, refund } = order
  if (order.status === 'refunded') {
    return (
      <p className="order-cancel-note order-cancel-note--refunded">
        <strong>환불 완료</strong> {formatDateTime(refund?.refunded_at)} · {order.total_amount.toLocaleString('ko-KR')}원
        <br />
        {refund?.actor === 'admin' ? '판매자 취소' : '고객 취소'} 사유: {getReasonText(refund?.reason_code, refund?.reason_detail)}
      </p>
    )
  }
  if (order.status === 'refunding') {
    return (
      <p className="order-cancel-note">
        <strong>환불 확인 중</strong> 결제사의 처리 결과를 확인하고 있어요. 잠시 후 이 화면을 새로 고쳐 결과를 확인해 주세요.
      </p>
    )
  }
  if (cancelRequest?.status === 'requested') {
    return (
      <p className="order-cancel-note">
        <strong>취소 요청 중</strong> {formatDateTime(cancelRequest.requested_at)} 요청 · 사유: {getReasonText(cancelRequest.reason_code, cancelRequest.reason_detail)}
        <br />
        판매자가 확인한 뒤 환불 또는 거절 결과를 알려 드려요.
      </p>
    )
  }
  if (cancelRequest?.status === 'rejected') {
    return (
      <p className="order-cancel-note order-cancel-note--rejected">
        <strong>취소 요청 거절</strong> {formatDateTime(cancelRequest.rejected_at)}
        <br />
        거절 사유: {cancelRequest.reject_reason}
      </p>
    )
  }
  if (refund?.failure_message) {
    return (
      <p className="order-cancel-note order-cancel-note--rejected">
        <strong>환불 실패</strong> {refund.failure_message}
      </p>
    )
  }
  return null
}

const ACTION_TEXT = {
  refund: {
    button: '주문 취소',
    confirm: '주문 취소',
    message: (order) => `주문을 취소하고 결제 금액 ${order.total_amount.toLocaleString('ko-KR')}원을 환불할까요? 취소한 주문은 되돌릴 수 없습니다.`,
    done: '주문을 취소했습니다. 결제 수단에 따라 실제 환불 반영까지 며칠이 걸릴 수 있습니다.',
  },
  request: {
    button: '취소 요청',
    confirm: '취소 요청',
    message: () => '상품 준비가 시작된 주문이라 판매자 확인 후 취소됩니다. 취소 요청은 주문당 1회만 할 수 있으며, 거절되면 다시 요청할 수 없습니다.',
    done: '취소 요청을 보냈습니다. 판매자가 확인한 뒤 결과를 알려 드려요.',
  },
}

// 결제 완료된 주문 카드 목록(마이 페이지·주문 목록 페이지 공용), 취소·취소 요청 후에는 onChanged로 목록을 다시 불러옴
export function OrderList({ orders, onNavigate, onChanged }) {
  const [target, setTarget] = useState(null) // { order, action }
  const [notice, setNotice] = useState('')

  const submitCancel = async ({ reasonCode, reasonDetail }) => {
    const { order, action } = target
    const call = action === 'refund' ? refundOrder : requestOrderCancel
    try {
      await call(order.order_id, { reasonCode, reasonDetail })
      setNotice(ACTION_TEXT[action].done)
    } catch (error) {
      if (!isRefundPending(error)) throw error // 확정 실패는 모달 안에 표시
      setNotice('환불 결과를 확인하고 있습니다. 같은 주문을 다시 취소하지 말고 잠시 후 주문 내역에서 확인해 주세요.')
    }
    setTarget(null)
    onChanged?.()
  }

  return (
    <>
      <ul className="my-orders__list">
        {orders.map((order) => {
          const currentStep = DELIVERY_STEPS.findIndex((step) => step.key === order.delivery_status)
          const badge = getCancelBadge(order)
          const action = getCustomerCancelAction(order)
          const isRefundOrder = order.status === 'refunded' || order.status === 'refunding'
          return (
            <li key={order.order_id} className="my-orders__order">
              <div className="my-orders__meta">
                <strong>
                  {new Date(order.paid_at || order.created_at).toLocaleDateString('ko-KR')} 결제
                  {badge && <span className={`cancel-badge cancel-badge--${badge.key}`}>{badge.label}</span>}
                </strong>
                <span>주문번호 {order.order_id}</span>
              </div>
              {!isRefundOrder && (
                <ol className="delivery-steps" aria-label={`배송 상태: ${getDeliveryLabel(order.delivery_status)}`}>
                  {DELIVERY_STEPS.map((step, index) => (
                    <li key={step.key} className={index <= currentStep ? 'is-done' : ''} aria-current={index === currentStep ? 'step' : undefined}>
                      {step.label}
                    </li>
                  ))}
                </ol>
              )}
              <CancelStatusNote order={order} />
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
                <span>{order.status === 'refunded' ? '환불 금액' : '결제 금액'}</span>
                <strong>{order.total_amount.toLocaleString('ko-KR')}원</strong>
              </div>
              {action && onChanged && (
                <div className="my-orders__actions">
                  <button type="button" onClick={() => setTarget({ order, action })}>{ACTION_TEXT[action].button}</button>
                </div>
              )}
            </li>
          )
        })}
      </ul>
      <ReasonModal
        key={target ? `${target.order.order_id}-${target.action}` : 'closed'}
        isOpen={Boolean(target)}
        message={target ? ACTION_TEXT[target.action].message(target.order) : ''}
        reasons={CUSTOMER_REFUND_REASONS}
        confirmLabel={target ? ACTION_TEXT[target.action].confirm : ''}
        tone="danger"
        onClose={() => setTarget(null)}
        onSubmit={submitCancel}
      />
      <Modal isOpen={Boolean(notice)} message={notice} onClose={() => setNotice('')} />
    </>
  )
}

// 마이 페이지 최근 주문 요약과 전체 주문 목록 링크
function OrderHistory({ orders, total, isLoading, onNavigate, onChanged }) {
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
        <OrderList orders={orders} onNavigate={onNavigate} onChanged={onChanged} />
      )}
    </section>
  )
}

export default OrderHistory
