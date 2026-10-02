// 결제 완료 주문 전체를 조회 기간(3·6·12개월 또는 최근 5년 안의 직접 지정 날짜)과 페이지 단위로 보여주는 고객 주문 목록 페이지

import { useEffect, useState } from 'react'
import { getOrders } from '../../api/orders.js'
import { clearStoredUser } from '../../api/user-auth.js'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'
import { USER_LOGIN_PATH, USER_MY_PAGE_PATH, USER_ORDERS_PATH } from '../../config/routes.js'
import { OrderList } from './order-history.jsx'

const PERIODS = [
  { months: 3, label: '3개월' },
  { months: 6, label: '6개월' },
  { months: 12, label: '1년' },
]
const DEFAULT_MONTHS = 3
const HISTORY_YEARS = 5 // 직접 지정으로 조회할 수 있는 최대 과거(서버 ORDER_HISTORY_MONTHS와 같은 5년)
const PAGE_SIZE = 5 // 주문 카드가 길어 모바일에서도 한 페이지가 지나치게 길지 않은 개수
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

// 한국 시간 기준 오늘과 5년 전 같은 날(2월 29일이면 28일)을 YYYY-MM-DD로 계산
function getSelectableRange() {
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date())
  const [year, month, day] = today.split('-').map(Number)
  const lastDay = new Date(Date.UTC(year - HISTORY_YEARS, month, 0)).getUTCDate()
  const earliest = `${year - HISTORY_YEARS}-${String(month).padStart(2, '0')}-${String(Math.min(day, lastDay)).padStart(2, '0')}`
  return { earliest, today }
}

// 주소의 조회 조건·페이지 값을 정리(날짜가 둘 다 형식에 맞으면 직접 지정, 아니면 개월 버튼, 잘못된 값은 기본값)
function readQuery() {
  const params = new URLSearchParams(window.location.search)
  const from = params.get('from') || ''
  const to = params.get('to') || ''
  const months = Number(params.get('months'))
  const page = Number(params.get('page'))
  const filter = DATE_PATTERN.test(from) && DATE_PATTERN.test(to)
    ? { from, to }
    : { months: PERIODS.some((period) => period.months === months) ? months : DEFAULT_MONTHS }
  return { filter, page: Number.isInteger(page) && page > 0 ? page : 1 }
}

// 조회 조건·페이지를 주소에 담아 뒤로가기·새로고침에도 같은 목록이 보이게 함
function getOrdersPath(filter, page) {
  const params = new URLSearchParams(filter.months ? { months: String(filter.months) } : { from: filter.from, to: filter.to })
  params.set('page', String(page))
  return `${USER_ORDERS_PATH}?${params}`
}

// 화면 표시용 날짜(2026-10-01 → 2026.10.01)
function formatDate(value) {
  return value.replaceAll('-', '.')
}

// 조회 기간 버튼·날짜 직접 지정, 주문 카드 목록, 이전·다음 페이지 이동(App이 주소가 바뀔 때마다 새로 그림)
function UserOrdersPage({ onNavigate }) {
  const [{ filter, page }] = useState(readQuery)
  const [{ earliest, today }] = useState(getSelectableRange)
  const [isRangeOpen, setIsRangeOpen] = useState(Boolean(filter.from))
  const [rangeInput, setRangeInput] = useState({ from: filter.from || '', to: filter.to || today })
  const [rangeError, setRangeError] = useState('')
  const [data, setData] = useState({ orders: [], total: 0 })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
  const periodText = filter.months
    ? `최근 ${PERIODS.find((period) => period.months === filter.months).label}`
    : `${formatDate(filter.from)} ~ ${formatDate(filter.to)}`

  useEffect(() => {
    let isMounted = true
    getOrders({ ...filter, page, pageSize: PAGE_SIZE })
      .then((result) => {
        if (!isMounted) return
        const lastPage = Math.max(1, Math.ceil(result.total / PAGE_SIZE))
        if (page > lastPage) {
          onNavigate(getOrdersPath(filter, lastPage), { replace: true }) // 주소로 범위 밖 페이지를 열면 마지막 페이지로
          return
        }
        setData(result)
      })
      .catch((requestError) => {
        if (!isMounted) return
        if (requestError.status === 401) {
          clearStoredUser()
          sessionStorage.setItem('authNotice', '로그인이 만료되었습니다. 다시 로그인해 주세요.')
          onNavigate(USER_LOGIN_PATH, { replace: true })
          return
        }
        setError(requestError.message)
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [filter, page, onNavigate])

  // 직접 지정한 날짜를 확인한 뒤 첫 페이지부터 조회(서버도 같은 규칙으로 다시 검증)
  const searchRange = (event) => {
    event.preventDefault()
    const { from, to } = rangeInput
    if (!from || !to) return setRangeError('조회 시작일과 종료일을 모두 선택해 주세요.')
    if (from > to) return setRangeError('조회 시작일이 종료일보다 늦을 수 없습니다.')
    if (from < earliest || to > today) return setRangeError(`최근 ${HISTORY_YEARS}년(${formatDate(earliest)}~${formatDate(today)}) 안에서 선택해 주세요.`)
    setRangeError('')
    onNavigate(getOrdersPath({ from, to }, 1))
  }

  const updateRangeInput = (event) => {
    setRangeInput((current) => ({ ...current, [event.target.name]: event.target.value }))
    setRangeError('')
  }

  return (
    <CustomerAccountShell onNavigate={onNavigate} className="customer-account-page--my">
      <div className="my-page-shell orders-page">
        <a
          className="orders-page__back"
          href={USER_MY_PAGE_PATH}
          onClick={(event) => {
            event.preventDefault()
            onNavigate(USER_MY_PAGE_PATH)
          }}
        >
          <span aria-hidden="true">‹</span> 마이 페이지
        </a>
        <header className="cart-heading">
          <p>ORDERS</p>
          <h1>주문 내역</h1>
        </header>

        <div className="orders-page__filters">
          <div className="orders-page__periods" role="group" aria-label="조회 기간">
            {PERIODS.map((period) => (
              <button
                key={period.months}
                type="button"
                className={period.months === filter.months ? 'is-active' : ''}
                aria-pressed={period.months === filter.months}
                onClick={() => period.months !== filter.months && onNavigate(getOrdersPath({ months: period.months }, 1))}
              >
                {period.label}
              </button>
            ))}
            <button
              type="button"
              className={filter.from ? 'is-active' : ''}
              aria-expanded={isRangeOpen}
              aria-controls="orders-range"
              onClick={() => setIsRangeOpen((current) => !current)}
            >
              기간 설정
            </button>
          </div>

          {isRangeOpen && (
            <form id="orders-range" className="orders-page__range" onSubmit={searchRange} noValidate>
              <div className="orders-page__range-fields">
                <label>
                  <span className="sr-only">조회 시작일</span>
                  <input name="from" type="date" min={earliest} max={today} value={rangeInput.from} onChange={updateRangeInput} />
                </label>
                <span aria-hidden="true">~</span>
                <label>
                  <span className="sr-only">조회 종료일</span>
                  <input name="to" type="date" min={earliest} max={today} value={rangeInput.to} onChange={updateRangeInput} />
                </label>
                <button type="submit">조회</button>
              </div>
              <p className={rangeError ? 'orders-page__range-note is-error' : 'orders-page__range-note'} role={rangeError ? 'alert' : undefined}>
                {rangeError || `최근 ${HISTORY_YEARS}년(${formatDate(earliest)}부터) 주문을 조회할 수 있어요.`}
              </p>
            </form>
          )}
        </div>

        <section className="my-page-card my-orders" aria-label={`${periodText} 주문`} aria-busy={isLoading}>
          {isLoading ? (
            <p className="my-orders__note" role="status">주문 내역을 불러오고 있습니다.</p>
          ) : error ? (
            <p className="my-orders__note" role="alert">{error}</p>
          ) : data.orders.length === 0 ? (
            <div className="my-empty">
              <strong>{periodText} 동안 주문 내역이 없어요</strong>
              <span>{filter.months === 12 || filter.from ? `기간 설정으로 최근 ${HISTORY_YEARS}년 안의 주문을 조회할 수 있어요.` : '조회 기간을 늘려 이전 주문을 확인해 보세요.'}</span>
            </div>
          ) : (
            <>
              <p className="orders-page__count">{periodText} 주문 <strong>{data.total}</strong>건</p>
              <OrderList orders={data.orders} onNavigate={onNavigate} />
            </>
          )}
        </section>

        {totalPages > 1 && (
          <nav className="catalog-pagination" aria-label="주문 페이지">
            <button type="button" disabled={page <= 1} onClick={() => onNavigate(getOrdersPath(filter, page - 1))}>이전</button>
            <span>{page} / {totalPages}</span>
            <button type="button" disabled={page >= totalPages} onClick={() => onNavigate(getOrdersPath(filter, page + 1))}>다음</button>
          </nav>
        )}
      </div>
    </CustomerAccountShell>
  )
}

export default UserOrdersPage
