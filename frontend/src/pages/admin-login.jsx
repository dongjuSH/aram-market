// 비공개 경로에서 단일 관리자 계정만 인증하는 로그인 화면

import { useState } from 'react'
import { signIn } from '../api/auth.js'
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
  const [modalMessage, setModalMessage] = useState(getInitialNotice)
  const [isSubmitting, setIsSubmitting] = useState(false)

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
      sessionStorage.setItem('adminAccessToken', result.access_token)
      sessionStorage.setItem('adminCurrentUser', JSON.stringify(result.user))
      onNavigate(ADMIN_PRODUCTS_PATH, { replace: true })
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
      </section>
      <Modal isOpen={Boolean(modalMessage)} message={modalMessage} onClose={() => setModalMessage('')} />
    </main>
  )
}

export default AdminLoginPage
