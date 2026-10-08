// 관리자가 주문의 배송지를 확인하고 배송 상태 변경·직접 환불·고객 취소 요청 승인/거절을 하는 화면

import { useCallback, useEffect, useState } from 'react'
import { getCurrentUser } from '../api/auth.js'
import { approveCancelRequest, getAdminOrders, refundAdminOrder, rejectCancelRequest, updateDeliveryStatus } from '../api/admin-orders.js'
import Modal from '../components/common/modal.jsx'
import ReasonModal from '../components/common/reason-modal.jsx'
import AdminHeader from '../components/products/admin-header.jsx'
import { ADMIN_LOGIN_PATH } from '../config/routes.js'
import { DELIVERY_STEPS, getDeliveryLabel } from '../config/delivery.js'
import { ADMIN_REFUND_REASONS, canAdminRefund, getCancelBadge, getReasonText, isRefundPending, REJECT_REASON_MAX_LENGTH } from '../config/refund.js'

const PAGE_SIZE = 10
// 배송 단계 탭 뒤에 붙는 취소·환불 탭(서버 view 값)
const EXTRA_TABS = [
  { key: 'view:cancel_requested', label: '취소 요청', view: 'cancel_requested' },
  { key: 'view:refunded', label: '환불', view: 'refunded' },
]
const PENDING_REFUND_MESSAGE = '환불 결과를 확인하고 있습니다. 같은 주문을 다시 환불하지 말고 잠시 후 목록을 새로 고쳐 확인해 주세요.'

const formatDateTime = (value) => (value ? new Date(value).toLocaleString('ko-KR') : '')

// 탭 키를 목록 API 조건으로 변환
function getListQuery(filter, page) {
  const extra = EXTRA_TABS.find((tab) => tab.key === filter)
  return extra ? { view: extra.view, page } : { deliveryStatus: filter, page }
}

// 취소 요청·거절·환불 기록 요약(해당 없으면 표시하지 않음)
function CancelDetail({ order }) {
  const { cancel_request: cancelRequest, refund } = order
  const lines = []
  if (cancelRequest) {
    lines.push(`취소 요청 ${formatDateTime(cancelRequest.requested_at)} · 사유: ${getReasonText(cancelRequest.reason_code, cancelRequest.reason_detail)}`)
    if (cancelRequest.status === 'rejected') lines.push(`거절 ${formatDateTime(cancelRequest.rejected_at)} · 거절 사유: ${cancelRequest.reject_reason}`)
  }
  if (refund) {
    const actor = refund.actor === 'admin' ? '관리자 환불' : '고객 취소'
    if (order.status === 'refunded') lines.push(`환불 완료 ${formatDateTime(refund.refunded_at)} · ${actor} · 사유: ${getReasonText(refund.reason_code, refund.reason_detail)}`)
    if (order.status === 'refunding') lines.push(`환불 확인 중(${formatDateTime(refund.attempted_at)} 요청) · 서버 정리 작업(매시간)이 결제사 결과를 다시 확인합니다. 목록을 새로 고쳐 확인하세요.`)
    if (order.status === 'paid' && refund.failure_message) lines.push(`최근 환불 실패: ${refund.failure_message}`)
  }
  if (lines.length === 0) return null
  return (
    <ul className="admin-orders__cancel">
      {lines.map((line) => <li key={line}>{line}</li>)}
    </ul>
  )
}

// 주문 목록과 배송 단계·환불·취소 요청 처리 버튼
function AdminOrdersPage({ onNavigate }) {
  const [user, setUser] = useState(null)
  const [data, setData] = useState({ orders: [], total: 0 })
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState('')
  const [version, setVersion] = useState(0) // 처리 후 목록을 다시 불러오기 위한 값
  const [updatingId, setUpdatingId] = useState(null)
  const [message, setMessage] = useState('')
  const [dialog, setDialog] = useState(null) // { type: 'refund' | 'approve' | 'reject', order }
  const [notice, setNotice] = useState('')
  const [isApproving, setIsApproving] = useState(false)

  // 세션 만료(401)는 로그인 화면으로 보내고 그 외 오류는 안내
  const handleError = useCallback(
    (error) => {
      if (error.status === 401) {
        sessionStorage.removeItem('adminCurrentUser')
        onNavigate(ADMIN_LOGIN_PATH, { replace: true })
        return
      }
      setMessage(error.message)
    },
    [onNavigate],
  )

  useEffect(() => {
    getCurrentUser().then((result) => setUser(result.user)).catch(handleError)
  }, [handleError])

  useEffect(() => {
    let isMounted = true
    getAdminOrders(getListQuery(filter, page))
      .then((result) => isMounted && setData(result))
      .catch((error) => isMounted && handleError(error))
    return () => {
      isMounted = false
    }
  }, [filter, page, version, handleError])

  const reload = () => setVersion((current) => current + 1)

  const selectTab = (key) => {
    setFilter(key)
    setPage(1)
    setMessage('')
  }

  async function advance(order, nextKey) {
    setUpdatingId(order.order_id)
    setMessage('')
    try {
      await updateDeliveryStatus(order.order_id, nextKey)
      reload()
    } catch (error) {
      handleError(error)
    } finally {
      setUpdatingId(null)
    }
  }

  // 환불·거절 모달 제출: 성공·결과 확인 중이면 닫고 목록을 새로 고침, 확정 실패는 모달 안에 표시
  const submitDialog = async ({ reasonCode, reasonDetail }) => {
    const { type, order } = dialog
    try {
      if (type === 'refund') {
        await refundAdminOrder(order.order_id, { reasonCode, reasonDetail })
        setNotice('환불을 완료했습니다.')
      } else {
        await rejectCancelRequest(order.order_id, reasonDetail)
        setNotice('취소 요청을 거절했습니다. 주문은 상품준비중으로 유지됩니다.')
      }
    } catch (error) {
      if (error.status === 401) return handleError(error)
      if (!isRefundPending(error)) throw error
      setNotice(PENDING_REFUND_MESSAGE)
    }
    setDialog(null)
    reload()
  }

  // 취소 요청 승인(고객이 고른 사유로 환불)
  const approve = async () => {
    setIsApproving(true)
    try {
      await approveCancelRequest(dialog.order.order_id)
      setNotice('취소 요청을 승인하고 환불을 완료했습니다.')
    } catch (error) {
      if (error.status === 401) return handleError(error)
      setNotice(isRefundPending(error) ? PENDING_REFUND_MESSAGE : error.message)
    } finally {
      setIsApproving(false)
    }
    setDialog(null)
    reload()
  }

  if (!user) {
    return <main className="products-page products-page--loading"><p>로그인 정보를 확인하고 있습니다.</p></main>
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
  const tabs = [{ key: '', label: '전체' }, ...DELIVERY_STEPS.map((step) => ({ key: step.key, label: step.label })), ...EXTRA_TABS]

  return (
    <main className="products-page">
      <AdminHeader user={user} onNavigate={onNavigate} current="orders" />
      <section className="product-content" aria-labelledby="order-admin-title">
        <div className="product-toolbar">
          <div>
            <h1 id="order-admin-title">주문·배송 관리</h1>
            <p>결제가 완료된 주문의 배송 상태를 한 단계씩 변경하고, 배송 전 주문의 환불과 고객 취소 요청을 처리합니다.</p>
          </div>
        </div>
        <div className="product-status-tabs" role="tablist" aria-label="주문 상태">
          {tabs.map((tab) => (
            <button key={tab.key || 'all'} className={filter === tab.key ? 'is-active' : ''} type="button" role="tab" aria-selected={filter === tab.key} onClick={() => selectTab(tab.key)}>{tab.label}</button>
          ))}
        </div>
        {message && <p className="product-notice product-notice--error" role="alert">{message}</p>}
        {data.orders.length === 0 ? (
          <p className="detail-empty">해당하는 주문이 없습니다.</p>
        ) : (
          <ul className="admin-orders">
            {data.orders.map((order) => {
              const isPaid = order.status === 'paid'
              const currentIndex = DELIVERY_STEPS.findIndex((step) => step.key === order.delivery_status)
              const next = isPaid ? DELIVERY_STEPS[currentIndex + 1] : null
              const hasRequest = isPaid && order.cancel_request?.status === 'requested'
              const isShippingBlocked = hasRequest && next?.key === 'shipping'
              const badge = getCancelBadge(order)
              const isBusy = updatingId === order.order_id
              return (
                <li key={order.order_id}>
                  <div className="admin-orders__meta">
                    <strong>{order.order_id}</strong>
                    <span>{order.buyer} · {new Date(order.paid_at || order.created_at).toLocaleString('ko-KR')} · {order.total_amount.toLocaleString('ko-KR')}원</span>
                  </div>
                  <ul className="admin-orders__items">
                    {order.items.map((item, index) => (
                      <li key={`${order.order_id}-${index}`}>{item.name} × {item.quantity}</li>
                    ))}
                  </ul>
                  <p className="admin-orders__address">
                    {order.shipping
                      ? `${order.shipping.recipient_name} (${order.shipping.recipient_phone}) · ${order.shipping.postcode ? `[${order.shipping.postcode}] ` : ''}${order.shipping.address} ${order.shipping.address_detail || ''}${order.shipping.delivery_memo ? ` · 요청: ${order.shipping.delivery_memo}` : ''}`
                      : '배송지 정보 없음(배송지 입력 기능 이전 주문)'}
                  </p>
                  <CancelDetail order={order} />
                  <div className="admin-orders__actions">
                    <span className="admin-orders__badges">
                      <span className={`delivery-badge delivery-badge--${order.delivery_status}`}>{getDeliveryLabel(order.delivery_status)}</span>
                      {badge && <span className={`cancel-badge cancel-badge--${badge.key}`}>{badge.label}</span>}
                    </span>
                    <span className="admin-orders__buttons">
                      {hasRequest && (
                        <>
                          <button type="button" onClick={() => setDialog({ type: 'approve', order })}>취소 승인(환불)</button>
                          <button className="is-secondary" type="button" onClick={() => setDialog({ type: 'reject', order })}>취소 거절</button>
                        </>
                      )}
                      {!hasRequest && canAdminRefund(order) && (
                        <button className="is-danger" type="button" onClick={() => setDialog({ type: 'refund', order })}>환불</button>
                      )}
                      {next && (
                        <button
                          type="button"
                          className={hasRequest ? 'is-secondary' : ''}
                          disabled={isBusy || isShippingBlocked}
                          title={isShippingBlocked ? '취소 요청을 먼저 승인하거나 거절해야 합니다.' : undefined}
                          onClick={() => advance(order, next.key)}
                        >
                          {next.action}
                        </button>
                      )}
                    </span>
                  </div>
                  {isShippingBlocked && <p className="admin-orders__hint">취소 요청을 먼저 승인하거나 거절해야 배송중으로 변경할 수 있습니다.</p>}
                </li>
              )
            })}
          </ul>
        )}
        {totalPages > 1 && (
          <nav className="catalog-pagination" aria-label="주문 페이지">
            <button type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>이전</button>
            <span>{page} / {totalPages}</span>
            <button type="button" disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}>다음</button>
          </nav>
        )}
      </section>

      <ReasonModal
        key={dialog && dialog.type !== 'approve' ? `${dialog.type}-${dialog.order.order_id}` : 'closed'}
        isOpen={Boolean(dialog) && dialog.type !== 'approve'}
        message={
          dialog?.type === 'refund'
            ? `주문 ${dialog.order.order_id}의 결제 금액 ${dialog.order.total_amount.toLocaleString('ko-KR')}원을 전액 환불할까요? 환불은 되돌릴 수 없습니다.`
            : '취소 요청을 거절할까요? 거절 사유는 고객의 주문 내역에 그대로 표시되며, 고객은 다시 요청할 수 없습니다.'
        }
        reasons={dialog?.type === 'refund' ? ADMIN_REFUND_REASONS : null}
        textLabel="거절 사유"
        textMaxLength={dialog?.type === 'refund' ? undefined : REJECT_REASON_MAX_LENGTH}
        confirmLabel={dialog?.type === 'refund' ? '환불' : '거절'}
        tone="danger"
        onClose={() => setDialog(null)}
        onSubmit={submitDialog}
      />
      <Modal
        isOpen={dialog?.type === 'approve'}
        message={
          dialog?.type === 'approve'
            ? `고객의 취소 요청을 승인하고 결제 금액 ${dialog.order.total_amount.toLocaleString('ko-KR')}원을 환불할까요? 사유: ${getReasonText(dialog.order.cancel_request?.reason_code, dialog.order.cancel_request?.reason_detail)}`
            : ''
        }
        onClose={() => setDialog(null)}
        onConfirm={approve}
        confirmLabel="승인(환불)"
        cancelLabel="닫기"
        isPending={isApproving}
        tone="danger"
      />
      <Modal isOpen={Boolean(notice)} message={notice} onClose={() => setNotice('')} />
    </main>
  )
}

export default AdminOrdersPage
