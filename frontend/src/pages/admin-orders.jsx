// 관리자가 결제 완료 주문의 배송지를 확인하고 배송 상태를 한 단계씩 변경하는 화면

import { useCallback, useEffect, useState } from 'react'
import { getCurrentUser } from '../api/auth.js'
import { getAdminOrders, updateDeliveryStatus } from '../api/admin-orders.js'
import AdminHeader from '../components/products/admin-header.jsx'
import { ADMIN_LOGIN_PATH } from '../config/routes.js'
import { DELIVERY_STEPS, getDeliveryLabel } from '../config/delivery.js'

const PAGE_SIZE = 10

// 주문 목록과 다음 배송 단계 버튼
function AdminOrdersPage({ onNavigate }) {
  const [user, setUser] = useState(null)
  const [data, setData] = useState({ orders: [], total: 0 })
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState('')
  const [updatingId, setUpdatingId] = useState(null)
  const [message, setMessage] = useState('')

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
    getAdminOrders({ deliveryStatus: filter, page })
      .then((result) => isMounted && setData(result))
      .catch((error) => isMounted && handleError(error))
    return () => {
      isMounted = false
    }
  }, [filter, page, handleError])

  async function advance(order, nextKey) {
    setUpdatingId(order.order_id)
    setMessage('')
    try {
      await updateDeliveryStatus(order.order_id, nextKey)
      setData(await getAdminOrders({ deliveryStatus: filter, page }))
    } catch (error) {
      handleError(error)
    } finally {
      setUpdatingId(null)
    }
  }

  if (!user) {
    return <main className="products-page products-page--loading"><p>로그인 정보를 확인하고 있습니다.</p></main>
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))

  return (
    <main className="products-page">
      <AdminHeader user={user} onNavigate={onNavigate} current="orders" />
      <section className="product-content" aria-labelledby="order-admin-title">
        <div className="product-toolbar">
          <div>
            <h1 id="order-admin-title">주문·배송 관리</h1>
            <p>결제가 완료된 주문의 배송지를 확인하고 배송 상태를 한 단계씩 변경합니다.</p>
          </div>
        </div>
        <div className="product-status-tabs" role="tablist" aria-label="배송 상태">
          <button className={filter === '' ? 'is-active' : ''} type="button" role="tab" aria-selected={filter === ''} onClick={() => { setFilter(''); setPage(1) }}>전체</button>
          {DELIVERY_STEPS.map((step) => (
            <button key={step.key} className={filter === step.key ? 'is-active' : ''} type="button" role="tab" aria-selected={filter === step.key} onClick={() => { setFilter(step.key); setPage(1) }}>{step.label}</button>
          ))}
        </div>
        {message && <p className="product-notice product-notice--error" role="alert">{message}</p>}
        {data.orders.length === 0 ? (
          <p className="detail-empty">해당하는 주문이 없습니다.</p>
        ) : (
          <ul className="admin-orders">
            {data.orders.map((order) => {
              const currentIndex = DELIVERY_STEPS.findIndex((step) => step.key === order.delivery_status)
              const next = DELIVERY_STEPS[currentIndex + 1]
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
                  <div className="admin-orders__actions">
                    <span className={`delivery-badge delivery-badge--${order.delivery_status}`}>{getDeliveryLabel(order.delivery_status)}</span>
                    {next && (
                      <button type="button" disabled={updatingId === order.order_id} onClick={() => advance(order, next.key)}>{next.action}</button>
                    )}
                  </div>
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
    </main>
  )
}

export default AdminOrdersPage
