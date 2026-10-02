// 관리자가 상품 문의를 답변 대기·답변 완료로 나눠 검색·페이지 이동하며 답변을 등록·수정하는 화면

import { useCallback, useEffect, useState } from 'react'
import { getCurrentUser } from '../api/auth.js'
import { answerInquiry, getAdminInquiries } from '../api/admin-inquiries.js'
import AdminHeader from '../components/products/admin-header.jsx'
import ProductPagination from '../components/products/product-pagination.jsx'
import { ADMIN_INQUIRIES_PATH, ADMIN_LOGIN_PATH } from '../config/routes.js'

const PAGE_SIZE = 20
const TABS = [
  { status: 'pending', label: '답변 대기' },
  { status: 'answered', label: '답변 완료' },
]
const dateFormatter = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

// 주소의 탭·검색어·페이지 값을 정리(잘못된 값은 기본값)
function readQuery() {
  const params = new URLSearchParams(window.location.search)
  const status = TABS.some((tab) => tab.status === params.get('status')) ? params.get('status') : 'pending'
  const page = Number(params.get('page'))
  return { status, q: (params.get('q') || '').trim(), page: Number.isInteger(page) && page > 0 ? page : 1 }
}

// 탭·검색어·페이지를 주소에 담아 뒤로가기·새로고침에도 같은 목록이 보이게 함
function getInquiriesPath({ status, q, page }) {
  const params = new URLSearchParams({ status })
  if (q) params.set('q', q)
  params.set('page', String(page))
  return `${ADMIN_INQUIRIES_PATH}?${params}`
}

// 한국 시간 기준 표시용 날짜·시각(2026. 10. 01. 14:30)
function formatDate(value) {
  return dateFormatter.format(new Date(value))
}

// 탭(건수)·검색·요약 행 목록(눌러서 펼친 뒤 답변)·번호 페이지 이동(App이 주소를 바꾸면 다시 그림)
function AdminInquiriesPage({ onNavigate }) {
  const { status, q, page } = readQuery()
  const [user, setUser] = useState(null)
  const [data, setData] = useState({ items: [], total: 0, counts: { pending: 0, answered: 0 } })
  const [isLoading, setIsLoading] = useState(true)
  const [requestVersion, setRequestVersion] = useState(0)
  const [openId, setOpenId] = useState(null)
  const [drafts, setDrafts] = useState({})
  const [savingId, setSavingId] = useState(null)
  const [message, setMessage] = useState('')
  const [notice, setNotice] = useState('')

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
    getAdminInquiries({ status, q, page, pageSize: PAGE_SIZE })
      .then((result) => {
        if (!isMounted) return
        const lastPage = Math.max(1, Math.ceil(result.total / PAGE_SIZE))
        if (page > lastPage) {
          onNavigate(getInquiriesPath({ status, q, page: lastPage }), { replace: true }) // 범위 밖 페이지는 마지막 페이지로
          return
        }
        setData(result)
      })
      .catch((error) => isMounted && handleError(error))
      .finally(() => isMounted && setIsLoading(false))
    return () => {
      isMounted = false
    }
  }, [status, q, page, requestVersion, handleError, onNavigate])

  // 탭·검색·페이지 이동은 주소만 바꾸고 펼친 행·안내는 닫음
  const moveTo = (next) => {
    setOpenId(null)
    setMessage('')
    setNotice('')
    setIsLoading(true)
    onNavigate(getInquiriesPath({ status, q, page, ...next }))
  }

  const search = (event) => {
    event.preventDefault()
    moveTo({ q: new FormData(event.currentTarget).get('q').trim(), page: 1 })
  }

  async function submit(inquiry) {
    const answer = (drafts[inquiry.id] ?? inquiry.answer ?? '').trim()
    if (!answer) {
      setMessage('답변 내용을 입력해 주세요.')
      return
    }
    setSavingId(inquiry.id)
    setMessage('')
    setNotice('')
    try {
      await answerInquiry(inquiry.id, answer)
      setDrafts((current) => ({ ...current, [inquiry.id]: undefined }))
      setOpenId(null)
      setNotice(inquiry.answer ? '답변을 수정했습니다.' : '답변을 등록했습니다. 답변 완료 탭에서 확인할 수 있습니다.')
      setIsLoading(true)
      setRequestVersion((current) => current + 1)
    } catch (error) {
      handleError(error)
    } finally {
      setSavingId(null)
    }
  }

  if (!user) {
    return <main className="products-page products-page--loading"><p>로그인 정보를 확인하고 있습니다.</p></main>
  }

  const isAnsweredTab = status === 'answered'
  const emptyText = q
    ? `'${q}' 검색 결과가 없습니다.`
    : isAnsweredTab ? '답변한 문의가 없습니다.' : '답변을 기다리는 문의가 없습니다.'

  return (
    <main className="products-page">
      <AdminHeader user={user} onNavigate={onNavigate} current="inquiries" />
      <section className="product-content" aria-labelledby="inquiry-admin-title">
        <div className="product-toolbar">
          <div>
            <h1 id="inquiry-admin-title">상품 문의 관리</h1>
            <p>답변 대기는 오래된 문의부터, 답변 완료는 최근 답변부터 보여 줍니다. 비밀글도 이곳에서는 내용을 볼 수 있어요.</p>
          </div>
          <form key={q} className="product-search" role="search" onSubmit={search}>
            <label className="sr-only" htmlFor="inquiry-keyword">문의 검색</label>
            <div className="product-search__input-wrap">
              <input id="inquiry-keyword" name="q" type="search" defaultValue={q} maxLength={100} placeholder="상품명, 문의 내용, 작성자 닉네임으로 검색" />
              <button type="submit" aria-label="검색">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="11" cy="11" r="6.5" />
                  <path d="m16 16 4 4" />
                </svg>
              </button>
            </div>
          </form>
        </div>
        <div className="product-status-tabs" role="tablist" aria-label="문의 상태">
          {TABS.map((tab) => (
            <button
              key={tab.status}
              className={status === tab.status ? 'is-active' : ''}
              type="button"
              role="tab"
              aria-selected={status === tab.status}
              onClick={() => status !== tab.status && moveTo({ status: tab.status, page: 1 })}
            >
              {tab.label} <span className="admin-inquiries__count">{data.counts[tab.status].toLocaleString('ko-KR')}</span>
            </button>
          ))}
        </div>
        {q && (
          <p className="admin-inquiries__search-result">
            '<strong>{q}</strong>' 검색 결과 {data.total.toLocaleString('ko-KR')}건
            <button type="button" onClick={() => moveTo({ q: '', page: 1 })}>검색 해제</button>
          </p>
        )}
        {message && <p className="product-notice product-notice--error" role="alert">{message}</p>}
        {notice && <p className="product-notice admin-inquiries__notice" role="status">{notice}</p>}
        <div className="admin-inquiries" aria-busy={isLoading}>
          <div className="admin-inquiries__row admin-inquiries__row--head" aria-hidden="true">
            <span>상품</span>
            <span>문의 내용</span>
            <span>작성자</span>
            <span>{isAnsweredTab ? '답변일' : '작성일'}</span>
          </div>
          {data.items.length === 0 ? (
            <p className="admin-inquiries__empty">{isLoading ? '문의를 불러오고 있습니다.' : emptyText}</p>
          ) : (
            <ul>
              {data.items.map((inquiry) => {
                const isOpen = openId === inquiry.id
                return (
                  <li key={inquiry.id} className={isOpen ? 'is-open' : ''}>
                    <button
                      className="admin-inquiries__row"
                      type="button"
                      aria-expanded={isOpen}
                      aria-controls={`inquiry-panel-${inquiry.id}`}
                      onClick={() => setOpenId(isOpen ? null : inquiry.id)}
                    >
                      <span className="admin-inquiries__product">{inquiry.product_name || '삭제된 상품'}</span>
                      <span className="admin-inquiries__preview">
                        {inquiry.is_secret && <em>비밀글</em>}
                        {inquiry.content}
                      </span>
                      <span>{inquiry.author}</span>
                      <span>{formatDate(isAnsweredTab ? inquiry.answered_at : inquiry.created_at)}</span>
                    </button>
                    {isOpen && (
                      <div className="admin-inquiries__panel" id={`inquiry-panel-${inquiry.id}`}>
                        <p className="admin-inquiries__content">{inquiry.content}</p>
                        <p className="admin-inquiries__dates">
                          작성 {formatDate(inquiry.created_at)}
                          {inquiry.answered_at && ` · 답변 ${formatDate(inquiry.answered_at)}`}
                        </p>
                        <label className="sr-only" htmlFor={`inquiry-answer-${inquiry.id}`}>답변</label>
                        <textarea
                          id={`inquiry-answer-${inquiry.id}`}
                          value={drafts[inquiry.id] ?? inquiry.answer ?? ''}
                          maxLength={1000}
                          placeholder="답변을 입력해 주세요."
                          onChange={(event) => setDrafts((current) => ({ ...current, [inquiry.id]: event.target.value }))}
                        />
                        <div className="admin-inquiries__actions">
                          <button className="is-secondary" type="button" onClick={() => setOpenId(null)}>닫기</button>
                          <button type="button" disabled={savingId === inquiry.id} onClick={() => submit(inquiry)}>{inquiry.answer ? '답변 수정' : '답변 등록'}</button>
                        </div>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
        <ProductPagination
          page={page}
          total={data.total}
          pageSize={PAGE_SIZE}
          label="문의 목록 페이지"
          onPageChange={(nextPage) => nextPage !== page && moveTo({ page: nextPage })}
        />
      </section>
    </main>
  )
}

export default AdminInquiriesPage
