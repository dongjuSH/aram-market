// 상품 문의 목록·작성·삭제 구역(로그인 고객 누구나 작성, 비밀글은 작성자만 열람, 관리자 답변 표시)

import { useCallback, useEffect, useState } from 'react'
import { createInquiry, deleteInquiry, getInquiries } from '../../api/inquiries.js'
import { getStoredUser } from '../../api/user-auth.js'
import { getLoginPath } from '../../config/routes.js'

const PAGE_SIZE = 5

// 문의 구역: 목록과 작성 폼
function ProductInquiries({ productId, onNavigate }) {
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [form, setForm] = useState({ content: '', isSecret: false })
  const [message, setMessage] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const isLoggedIn = Boolean(getStoredUser())

  const load = useCallback((targetPage) => getInquiries(productId, targetPage).then(setData), [productId])

  useEffect(() => {
    load(page).catch((error) => setMessage(error.message))
  }, [load, page])

  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))

  async function submit(event) {
    event.preventDefault()
    setIsSaving(true)
    setMessage('')
    try {
      await createInquiry(productId, form)
      setForm({ content: '', isSecret: false })
      setPage(1)
      await load(1)
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsSaving(false)
    }
  }

  async function remove(inquiryId) {
    if (!window.confirm('문의를 삭제할까요?')) return
    try {
      await deleteInquiry(inquiryId)
      setPage(1)
      await load(1)
    } catch (error) {
      setMessage(error.message)
    }
  }

  return (
    <>
      {isLoggedIn ? (
        <form className="feedback-form" onSubmit={submit}>
          <fieldset>
            <legend>문의 작성</legend>
            <textarea value={form.content} maxLength={1000} placeholder="상품에 대해 궁금한 점을 5자 이상 남겨 주세요." onChange={(event) => setForm((current) => ({ ...current, content: event.target.value }))} />
            <div className="feedback-form__actions">
              <label className="feedback-form__secret">
                <input type="checkbox" checked={form.isSecret} onChange={(event) => setForm((current) => ({ ...current, isSecret: event.target.checked }))} />
                비밀글
              </label>
              <span>{form.content.length} / 1000</span>
              <button type="submit" className="is-primary" disabled={isSaving}>{isSaving ? '저장 중...' : '문의 등록'}</button>
            </div>
          </fieldset>
        </form>
      ) : (
        <p className="feedback-guide">
          문의는 로그인 후 작성할 수 있어요. <button type="button" onClick={() => onNavigate(getLoginPath(`${window.location.pathname}${window.location.search}`))}>로그인</button>
        </p>
      )}
      {message && <p className="feedback-error" role="alert">{message}</p>}

      {data && data.items.length === 0 && <p className="detail-empty">등록된 문의가 없습니다.</p>}
      {data && data.items.length > 0 && (
        <ul className="feedback-list">
          {data.items.map((inquiry) => (
            <li key={inquiry.id}>
              <div className="feedback-list__head">
                <span className={`feedback-badge${inquiry.is_answered ? ' is-answered' : ''}`}>{inquiry.is_answered ? '답변완료' : '답변대기'}</span>
                {inquiry.is_secret && <span className="feedback-lock" aria-label="비밀글">🔒</span>}
                <strong>{inquiry.author}</strong>
                <time dateTime={inquiry.created_at}>{new Date(inquiry.created_at).toLocaleDateString('ko-KR')}</time>
              </div>
              <p>{inquiry.content}</p>
              {inquiry.answer && (
                <div className="feedback-answer">
                  <strong>아람 마켓 답변</strong>
                  <p>{inquiry.answer}</p>
                </div>
              )}
              {inquiry.is_mine && (
                <div className="feedback-list__actions">
                  <button type="button" onClick={() => remove(inquiry.id)}>삭제</button>
                </div>
              )}
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
    </>
  )
}

export default ProductInquiries
