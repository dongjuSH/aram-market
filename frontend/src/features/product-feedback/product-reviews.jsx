// 상품 후기 목록·작성·수정·삭제 구역(후기는 해당 상품을 구매한 로그인 고객만 작성)

import { useCallback, useEffect, useState } from 'react'
import { createReview, deleteReview, getReviewEligibility, getReviews, updateReview } from '../../api/reviews.js'
import { getStoredUser } from '../../api/user-auth.js'
import { getLoginPath } from '../../config/routes.js'
import { StarIcon } from '../../components/common/icons.jsx'

const PAGE_SIZE = 5

// 1~5 별 표시(채워진 별 수만큼 강조)
function Stars({ value }) {
  return (
    <span className="review-stars" role="img" aria-label={`별점 ${value}점`}>
      {[1, 2, 3, 4, 5].map((star) => (
        <svg key={star} viewBox="0 0 24 24" className={star <= value ? 'is-filled' : ''} aria-hidden="true">
          <path d="m12 2.8 2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.6l-5.8 3.1 1.1-6.5-4.7-4.6 6.5-.9L12 2.8Z" />
        </svg>
      ))}
    </span>
  )
}

// 후기 구역: 목록·페이지 이동과 작성 가능 여부에 따른 작성 폼·안내
function ProductReviews({ productId, onNavigate, onSummaryChange }) {
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [eligibility, setEligibility] = useState(null)
  const [isEditing, setIsEditing] = useState(false)
  const [form, setForm] = useState({ rating: 5, content: '' })
  const [message, setMessage] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const isLoggedIn = Boolean(getStoredUser())

  // 목록·내 작성 가능 여부를 함께 조회(상태 반영은 호출한 쪽에서)
  const fetchReviews = useCallback(
    async (targetPage) => {
      const [list, mine] = await Promise.all([
        getReviews(productId, targetPage),
        getStoredUser() ? getReviewEligibility(productId).catch(() => null) : Promise.resolve(null),
      ])
      return { list, mine }
    },
    [productId],
  )

  // 조회 결과를 화면 상태와 상단 평점 요약에 반영
  const apply = useCallback(
    ({ list, mine }) => {
      setData(list)
      setEligibility(mine)
      onSummaryChange(list.summary)
    },
    [onSummaryChange],
  )

  useEffect(() => {
    let isMounted = true
    fetchReviews(page)
      .then((result) => isMounted && apply(result))
      .catch((error) => isMounted && setMessage(error.message))
    return () => {
      isMounted = false
    }
  }, [fetchReviews, apply, page])

  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))

  // 작성·수정 저장 후 첫 페이지로 새로 불러옴
  async function submit(event) {
    event.preventDefault()
    setIsSaving(true)
    setMessage('')
    try {
      if (isEditing && eligibility?.review_id) await updateReview(eligibility.review_id, form)
      else await createReview(productId, form)
      setIsEditing(false)
      setForm({ rating: 5, content: '' })
      setPage(1)
      apply(await fetchReviews(1))
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsSaving(false)
    }
  }

  async function remove(reviewId) {
    if (!window.confirm('후기를 삭제할까요?')) return
    try {
      await deleteReview(reviewId)
      setPage(1)
      apply(await fetchReviews(1))
    } catch (error) {
      setMessage(error.message)
    }
  }

  function startEdit(review) {
    setForm({ rating: review.rating, content: review.content })
    setIsEditing(true)
  }

  const canWrite = eligibility?.can_review || isEditing

  return (
    <>
      {data && (
        <div className="detail-review-summary">
          <strong>{data.summary.average === null ? '-' : data.summary.average.toFixed(1)}</strong>
          <span>/ 5.0</span>
          <p>{data.summary.count > 0 ? `구매 고객 ${data.summary.count.toLocaleString('ko-KR')}명이 남긴 후기예요.` : '아직 작성된 후기가 없어요.'}</p>
        </div>
      )}

      {!isLoggedIn && (
        <p className="feedback-guide">
          후기는 상품을 구매한 고객만 작성할 수 있어요. <button type="button" onClick={() => onNavigate(getLoginPath(`${window.location.pathname}${window.location.search}`))}>로그인</button>
        </p>
      )}
      {isLoggedIn && eligibility && !canWrite && eligibility.reason === 'not_purchased' && (
        <p className="feedback-guide">이 상품을 구매하면 후기를 작성할 수 있어요.</p>
      )}
      {isLoggedIn && eligibility?.reason === 'already_reviewed' && !isEditing && <p className="feedback-guide">이미 후기를 작성했어요. 아래에서 수정하거나 삭제할 수 있어요.</p>}

      {canWrite && (
        <form className="feedback-form" onSubmit={submit}>
          <fieldset>
            <legend>{isEditing ? '후기 수정' : '후기 작성'}</legend>
            <div className="feedback-form__rating" role="radiogroup" aria-label="별점 선택">
              {[1, 2, 3, 4, 5].map((star) => (
                <button key={star} type="button" role="radio" aria-checked={form.rating === star} aria-label={`${star}점`} className={star <= form.rating ? 'is-filled' : ''} onClick={() => setForm((current) => ({ ...current, rating: star }))}>
                  <StarIcon />
                </button>
              ))}
            </div>
            <textarea value={form.content} maxLength={1000} placeholder="상품을 사용해 본 경험을 10자 이상 남겨 주세요." onChange={(event) => setForm((current) => ({ ...current, content: event.target.value }))} />
            <div className="feedback-form__actions">
              <span>{form.content.length} / 1000</span>
              {isEditing && <button type="button" onClick={() => { setIsEditing(false); setMessage('') }}>취소</button>}
              <button type="submit" className="is-primary" disabled={isSaving}>{isSaving ? '저장 중...' : '등록'}</button>
            </div>
          </fieldset>
        </form>
      )}
      {message && <p className="feedback-error" role="alert">{message}</p>}

      {data && data.items.length === 0 && <p className="detail-empty">등록된 후기가 없습니다.</p>}
      {data && data.items.length > 0 && (
        <ul className="feedback-list">
          {data.items.map((review) => (
            <li key={review.id}>
              <div className="feedback-list__head">
                <Stars value={review.rating} />
                <strong>{review.author}</strong>
                <time dateTime={review.created_at}>{new Date(review.created_at).toLocaleDateString('ko-KR')}</time>
              </div>
              <p>{review.content}</p>
              {review.is_mine && !isEditing && (
                <div className="feedback-list__actions">
                  <button type="button" onClick={() => startEdit(review)}>수정</button>
                  <button type="button" onClick={() => remove(review.id)}>삭제</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {totalPages > 1 && (
        <nav className="catalog-pagination" aria-label="후기 페이지">
          <button type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>이전</button>
          <span>{page} / {totalPages}</span>
          <button type="button" disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}>다음</button>
        </nav>
      )}
    </>
  )
}

export default ProductReviews
