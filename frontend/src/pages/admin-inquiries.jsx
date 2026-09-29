// 관리자가 상품 문의를 확인하고 답변을 등록·수정하는 화면

import { useCallback, useEffect, useState } from 'react'
import { getCurrentUser } from '../api/auth.js'
import { answerInquiry, getAdminInquiries } from '../api/admin-inquiries.js'
import AdminHeader from '../components/products/admin-header.jsx'
import { ADMIN_LOGIN_PATH } from '../config/routes.js'

const PAGE_SIZE = 10

// 문의 목록과 인라인 답변 폼
function AdminInquiriesPage({ onNavigate }) {
  const [user, setUser] = useState(null)
  const [data, setData] = useState({ items: [], total: 0 })
  const [page, setPage] = useState(1)
  const [unansweredOnly, setUnansweredOnly] = useState(true)
  const [drafts, setDrafts] = useState({})
  const [savingId, setSavingId] = useState(null)
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
    getAdminInquiries({ unanswered: unansweredOnly, page })
      .then((result) => isMounted && setData(result))
      .catch((error) => isMounted && handleError(error))
    return () => {
      isMounted = false
    }
  }, [unansweredOnly, page, handleError])

  async function submit(inquiry) {
    const answer = (drafts[inquiry.id] ?? inquiry.answer ?? '').trim()
    if (!answer) {
      setMessage('답변 내용을 입력해 주세요.')
      return
    }
    setSavingId(inquiry.id)
    setMessage('')
    try {
      await answerInquiry(inquiry.id, answer)
      setDrafts((current) => ({ ...current, [inquiry.id]: undefined }))
      setData(await getAdminInquiries({ unanswered: unansweredOnly, page }))
    } catch (error) {
      handleError(error)
    } finally {
      setSavingId(null)
    }
  }

  if (!user) {
    return <main className="products-page products-page--loading"><p>로그인 정보를 확인하고 있습니다.</p></main>
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))

  return (
    <main className="products-page">
      <AdminHeader user={user} onNavigate={onNavigate} current="inquiries" />
      <section className="product-content" aria-labelledby="inquiry-admin-title">
        <div className="product-toolbar">
          <div>
            <h1 id="inquiry-admin-title">상품 문의 관리</h1>
            <p>고객이 남긴 문의를 확인하고 답변합니다. 비밀글도 이곳에서는 내용을 볼 수 있어요.</p>
          </div>
        </div>
        <div className="product-status-tabs" role="tablist" aria-label="문의 상태">
          <button className={unansweredOnly ? 'is-active' : ''} type="button" role="tab" aria-selected={unansweredOnly} onClick={() => { setUnansweredOnly(true); setPage(1) }}>답변 대기</button>
          <button className={!unansweredOnly ? 'is-active' : ''} type="button" role="tab" aria-selected={!unansweredOnly} onClick={() => { setUnansweredOnly(false); setPage(1) }}>전체</button>
        </div>
        {message && <p className="product-notice product-notice--error" role="alert">{message}</p>}
        {data.items.length === 0 ? (
          <p className="detail-empty">{unansweredOnly ? '답변을 기다리는 문의가 없습니다.' : '등록된 문의가 없습니다.'}</p>
        ) : (
          <ul className="admin-inquiries">
            {data.items.map((inquiry) => (
              <li key={inquiry.id}>
                <div className="admin-inquiries__meta">
                  <strong>{inquiry.product_name || '삭제된 상품'}</strong>
                  <span>{inquiry.author} · {new Date(inquiry.created_at).toLocaleString('ko-KR')}{inquiry.is_secret ? ' · 🔒 비밀글' : ''}</span>
                </div>
                <p>{inquiry.content}</p>
                <textarea
                  value={drafts[inquiry.id] ?? inquiry.answer ?? ''}
                  maxLength={1000}
                  placeholder="답변을 입력해 주세요."
                  onChange={(event) => setDrafts((current) => ({ ...current, [inquiry.id]: event.target.value }))}
                />
                <div className="admin-inquiries__actions">
                  {inquiry.answered_at && <span>답변 {new Date(inquiry.answered_at).toLocaleString('ko-KR')}</span>}
                  <button type="button" disabled={savingId === inquiry.id} onClick={() => submit(inquiry)}>{inquiry.answer ? '답변 수정' : '답변 등록'}</button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {totalPages > 1 && (
          <nav className="catalog-pagination" aria-label="문의 페이지">
            <button type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>이전</button>
            <span>{page} / {totalPages}</span>
            <button type="button" disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}>다음</button>
          </nav>
        )}
      </section>
    </main>
  )
}

export default AdminInquiriesPage
