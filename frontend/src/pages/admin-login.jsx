// 비공개 경로에서 단일 관리자 계정만 인증하는 로그인 화면

import { useState } from 'react'
import { signIn, verifyMfa } from '../api/auth.js'
import Modal from '../components/common/modal.jsx'
import { ADMIN_PRODUCTS_PATH } from '../config/routes.js'

// 세션 만료 후 전달된 일회성 안내 조회
function getInitialNotice() {
  const notice = sessionStorage.getItem('adminAuthNotice')
  sessionStorage.removeItem('adminAuthNotice')
  return notice || ''
}

// 관리자 아이디·비밀번호 입력 및 로그인 상태 관리
function AdminLoginPage({ onNavigate }) {
  const [form, setForm] = useState({ username: '', password: '' })
  const [step, setStep] = useState('password') // password → (2단계 인증 등록 계정이면) mfa
  const [mfaCode, setMfaCode] = useState('')
  const [modalMessage, setModalMessage] = useState(getInitialNotice)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // 로그인 완료: 화면 표시용 관리자 정보 저장 후 상품 관리로 이동
  const completeLogin = (user) => {
    sessionStorage.setItem('adminCurrentUser', JSON.stringify(user))
    onNavigate(ADMIN_PRODUCTS_PATH, { replace: true })
  }

  // 비밀번호 단계로 돌아가 다시 시작
  const restart = (message = '') => {
    setStep('password')
    setMfaCode('')
    setForm((current) => ({ ...current, password: '' }))
    setModalMessage(message)
  }

  // 인증 앱 코드 또는 복구 코드 제출
  const handleMfaSubmit = async (event) => {
    event.preventDefault()
    if (!mfaCode.trim()) {
      setModalMessage('인증 코드를 입력해 주세요.')
      return
    }
    setIsSubmitting(true)
    try {
      const result = await verifyMfa({ code: mfaCode.trim() })
      completeLogin(result.user)
    } catch (error) {
      if (error.code === 'MFA_SESSION_EXPIRED') restart(error.message)
      else {
        setMfaCode('')
        setModalMessage(error.message)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!form.username.trim()) {
      setModalMessage('아이디를 입력해 주세요.')
      return
    }
    if (!form.password) {
      setModalMessage('비밀번호를 입력해 주세요.')
      return
    }

    setIsSubmitting(true)
    try {
      const result = await signIn({ username: form.username.trim(), password: form.password })
      if (result.mfa_required) {
        setStep('mfa')
        return
      }
      completeLogin(result.user)
    } catch (error) {
      setModalMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel auth-panel--login" aria-labelledby="login-title">
        <header className="auth-header">
          <p className="auth-eyebrow">PRODUCT MANAGEMENT</p>
          <h1 id="login-title">관리자 로그인</h1>
          <p className="auth-description">허가된 관리자 계정만 접근할 수 있습니다.</p>
        </header>
        {step === 'mfa' ? (
          <form className="auth-form auth-form--login" onSubmit={handleMfaSubmit} noValidate>
            <div className="form-field">
              <label htmlFor="login-mfa-code">2단계 인증 코드</label>
              <input id="login-mfa-code" name="mfaCode" type="text" inputMode="text" autoCapitalize="characters" autoCorrect="off" spellCheck={false} autoComplete="one-time-code" placeholder="인증 앱의 6자리 코드" value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} maxLength="20" autoFocus />
              <p className="auth-description">휴대폰을 사용할 수 없으면 복구 코드(XXXX-XXXX)를 입력하세요. 5분 안에 입력해야 합니다.</p>
            </div>
            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? '확인 중...' : '인증하고 로그인'}
            </button>
            <button className="back-button" type="button" onClick={() => restart()} disabled={isSubmitting}>
              처음으로
            </button>
          </form>
        ) : (
        <form className="auth-form auth-form--login" onSubmit={handleSubmit} noValidate>
          <div className="form-field">
            <label htmlFor="login-username">아이디</label>
            <input id="login-username" name="username" type="text" autoComplete="username" placeholder="관리자 아이디" value={form.username} onChange={updateField} maxLength="20" autoFocus />
          </div>
          <div className="form-field">
            <label htmlFor="login-password">비밀번호</label>
            <input id="login-password" name="password" type="password" autoComplete="current-password" placeholder="비밀번호를 입력하세요." value={form.password} onChange={updateField} maxLength="64" />
          </div>
          <button className="primary-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? '로그인 중...' : '로그인'}
          </button>
        </form>
        )}
      </section>
      <Modal isOpen={Boolean(modalMessage)} message={modalMessage} onClose={() => setModalMessage('')} />
    </main>
  )
}

export default AdminLoginPage
