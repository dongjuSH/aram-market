// 로그인 사용자의 현재 비밀번호 확인 및 새 비밀번호 변경 페이지

import { useEffect, useState } from 'react'
import { changePassword, getCurrentUser } from '../api/auth.js'
import Modal from '../components/common/modal.jsx'

// 비밀번호 조합·길이·공백 규칙 확인
function validatePassword(password) {
  return password.length >= 8
    && password.length <= 64
    && /[A-Za-z]/.test(password)
    && /\d/.test(password)
    && /[^A-Za-z0-9]/.test(password)
    && !/\s/.test(password)
}

// 현재·새 비밀번호 입력 및 변경 요청 상태 관리
function ChangePasswordPage({ onNavigate }) {
  const [form, setForm] = useState({ currentPassword: '', newPassword: '', passwordConfirm: '' })
  const [errors, setErrors] = useState({})
  const [modalMessage, setModalMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const isPreview = import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === '1'
  const [isCheckingSession, setIsCheckingSession] = useState(!isPreview)

  // 비밀번호 변경 화면 진입 시 서버에서 토큰 유효성을 확인하고 만료 세션 차단
  useEffect(() => {
    if (isPreview) return undefined

    let isMounted = true
    getCurrentUser()
      .catch(() => {
        if (!isMounted) return
        sessionStorage.removeItem('accessToken')
        sessionStorage.removeItem('currentUser')
        sessionStorage.setItem('authNotice', '로그인이 만료되었습니다. 다시 로그인해 주세요.')
        onNavigate('/login', { replace: true })
      })
      .finally(() => {
        if (isMounted) setIsCheckingSession(false)
      })

    return () => {
      isMounted = false
    }
  }, [isPreview, onNavigate])

  // 입력값 반영 및 수정 필드 오류 제거
  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: '' }))
  }

  // 입력값 검증 후 비밀번호 변경 및 기존 로그인 종료
  const handleSubmit = async (event) => {
    event.preventDefault()
    const nextErrors = {}
    if (!form.currentPassword) nextErrors.currentPassword = '* 현재 비밀번호가 입력되지 않았습니다.'
    if (!form.newPassword) nextErrors.newPassword = '* 새 비밀번호가 입력되지 않았습니다.'
    else if (!validatePassword(form.newPassword)) nextErrors.newPassword = '* 영문, 숫자, 특수문자를 포함한 8~64자로 입력해 주세요.'
    else if (form.currentPassword === form.newPassword) nextErrors.newPassword = '* 새 비밀번호는 현재 비밀번호와 다르게 입력해 주세요.'
    if (!form.passwordConfirm) nextErrors.passwordConfirm = '* 새 비밀번호 확인이 입력되지 않았습니다.'
    else if (form.newPassword !== form.passwordConfirm) nextErrors.passwordConfirm = '* 새 비밀번호가 일치하지 않습니다.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return

    setIsSubmitting(true)
    try {
      const result = await changePassword({
        currentPassword: form.currentPassword,
        newPassword: form.newPassword,
      })
      sessionStorage.removeItem('accessToken')
      sessionStorage.removeItem('currentUser')
      sessionStorage.setItem('authNotice', result.message)
      onNavigate('/login', { replace: true })
    } catch (error) {
      if (error.code === 'INVALID_CURRENT_PASSWORD') {
        setErrors((current) => ({ ...current, currentPassword: '* ' + error.message }))
      } else if (error.code === 'PASSWORD_UNCHANGED') {
        setErrors((current) => ({ ...current, newPassword: '* ' + error.message }))
      } else {
        setModalMessage(error.message)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isCheckingSession) {
    return (
      <main className="products-page products-page--loading">
        <p>로그인 정보를 확인하고 있습니다.</p>
      </main>
    )
  }

  return (
    <main className="auth-page auth-page--signup">
      <section className="auth-panel change-password-panel" aria-labelledby="change-password-title">
        <header className="auth-header auth-header--compact">
          <p className="auth-eyebrow">ACCOUNT SECURITY</p>
          <h1 id="change-password-title">비밀번호 변경</h1>
          <p className="auth-description">현재 비밀번호를 확인한 후 새 비밀번호로 변경합니다.</p>
        </header>

        <form className="auth-form change-password-form" onSubmit={handleSubmit} noValidate>
          <div className="form-field">
            <label htmlFor="change-current-password">현재 비밀번호</label>
            <input id="change-current-password" name="currentPassword" type="password" autoComplete="current-password" value={form.currentPassword} onChange={updateField} maxLength="64" aria-invalid={Boolean(errors.currentPassword)} autoFocus />
            <p className="field-error" role="alert">{errors.currentPassword}</p>
          </div>
          <div className="form-field">
            <label htmlFor="change-new-password">새 비밀번호</label>
            <input id="change-new-password" name="newPassword" type="password" autoComplete="new-password" value={form.newPassword} onChange={updateField} maxLength="64" aria-invalid={Boolean(errors.newPassword)} placeholder="영문·숫자·특수문자 포함 8~64자" />
            <p className="field-error" role="alert">{errors.newPassword}</p>
          </div>
          <div className="form-field">
            <label htmlFor="change-password-confirm">새 비밀번호 확인</label>
            <input id="change-password-confirm" name="passwordConfirm" type="password" autoComplete="new-password" value={form.passwordConfirm} onChange={updateField} maxLength="64" aria-invalid={Boolean(errors.passwordConfirm)} />
            <p className="field-error" role="alert">{errors.passwordConfirm}</p>
          </div>
          <button className="primary-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? '변경 중...' : '비밀번호 변경'}
          </button>
          <button className="back-button" type="button" onClick={() => onNavigate('/products')}>상품 목록으로 돌아가기</button>
        </form>
      </section>

      <Modal isOpen={Boolean(modalMessage)} message={modalMessage} onClose={() => setModalMessage('')} />
    </main>
  )
}

export default ChangePasswordPage
