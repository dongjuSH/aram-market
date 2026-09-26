// 이메일 링크 단기 토큰 기반 비밀번호 재설정 페이지

import { useState } from 'react'
import { resetPassword } from '../api/auth.js'
import Modal from '../components/common/modal.jsx'

// 이메일 링크 토큰·새 비밀번호 입력·검증 결과 관리
function ResetPasswordPage({ onNavigate }) {
  const token = new URLSearchParams(window.location.search).get('token') || ''
  const [form, setForm] = useState({ password: '', passwordConfirm: '' })
  const [errors, setErrors] = useState({})
  const [modalMessage, setModalMessage] = useState(token ? '' : '비밀번호 재설정 링크가 올바르지 않습니다.')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // 새 비밀번호 입력 반영 및 해당 필드 오류 초기화
  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: '' }))
  }

  // 비밀번호 형식 및 일치 여부 확인 후 변경 요청
  const handleSubmit = async (event) => {
    event.preventDefault()
    const nextErrors = {}
    if (!form.password) nextErrors.password = '* 새 비밀번호가 입력되지 않았습니다.'
    else if (form.password.length < 8 || !/[A-Za-z]/.test(form.password) || !/\d/.test(form.password) || !/[^A-Za-z0-9]/.test(form.password)) {
      nextErrors.password = '* 영문, 숫자, 특수문자를 포함한 8~64자로 입력해 주세요.'
    }
    if (!form.passwordConfirm) nextErrors.passwordConfirm = '* 비밀번호 확인이 입력되지 않았습니다.'
    else if (form.password !== form.passwordConfirm) nextErrors.passwordConfirm = '* 비밀번호가 일치하지 않습니다.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length || !token) return

    setIsSubmitting(true)
    try {
      const result = await resetPassword({ token, newPassword: form.password })
      sessionStorage.setItem('authNotice', result.message)
      onNavigate('/login', { replace: true })
    } catch (error) {
      setModalMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-page auth-page--signup">
      <section className="auth-panel reset-panel" aria-labelledby="reset-title">
        <header className="auth-header auth-header--compact">
          <p className="auth-eyebrow">RESET PASSWORD</p>
          <h1 id="reset-title">비밀번호 재설정</h1>
          <p className="auth-description">새로 사용할 비밀번호를 입력해 주세요.</p>
        </header>

        <form className="auth-form reset-form" onSubmit={handleSubmit} noValidate>
          <div className="form-field">
            <label htmlFor="reset-password">새 비밀번호</label>
            <input id="reset-password" name="password" type="password" autoComplete="new-password" value={form.password} onChange={updateField} maxLength="64" placeholder="영문·숫자·특수문자 포함 8~64자" />
            <p className="field-error" role="alert">{errors.password}</p>
          </div>
          <div className="form-field">
            <label htmlFor="reset-password-confirm">새 비밀번호 확인</label>
            <input id="reset-password-confirm" name="passwordConfirm" type="password" autoComplete="new-password" value={form.passwordConfirm} onChange={updateField} maxLength="64" placeholder="새 비밀번호를 다시 입력하세요." />
            <p className="field-error" role="alert">{errors.passwordConfirm}</p>
          </div>
          <button className="primary-button" type="submit" disabled={isSubmitting || !token}>
            {isSubmitting ? '변경 중...' : '비밀번호 변경'}
          </button>
          <button className="back-button" type="button" onClick={() => onNavigate('/login')}>로그인 화면으로 돌아가기</button>
        </form>
      </section>

      <Modal isOpen={Boolean(modalMessage)} message={modalMessage} onClose={() => setModalMessage('')} />
    </main>
  )
}

export default ResetPasswordPage
