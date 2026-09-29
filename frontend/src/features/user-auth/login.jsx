// 고객 로그인·계정 찾기·탈퇴 복구 화면

import { useState } from 'react'
import { cancelWithdrawal, resendVerificationEmail, signIn, storeUser } from '../../api/user-auth.js'
import Modal from '../../components/common/modal.jsx'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'
import { getSafeRedirectPath } from '../../config/routes.js'
import AccountRecoveryModal from './account-recovery-modal.jsx'

// 회원가입 후 전달된 일회성 안내 조회
function getInitialNotice() {
  const savedNotice = sessionStorage.getItem('authNotice')
  sessionStorage.removeItem('authNotice')
  if (savedNotice) return savedNotice
  return ''
}

// 로그인 입력·계정 찾기 모달·탈퇴 복구 확인 상태 관리
function UserLoginPage({ onNavigate }) {
  const [form, setForm] = useState({ username: '', password: '' })
  const [modalMessage, setModalMessage] = useState(getInitialNotice)
  const [recoveryMode, setRecoveryMode] = useState(null)
  const [withdrawalPrompt, setWithdrawalPrompt] = useState(null)
  const [verificationPrompt, setVerificationPrompt] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // 입력값 변경을 로그인 폼 상태에 반영
  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
  }

  // 로그인 화면으로 오기 전 보던 화면(next)과 회원가입 이동 시 유지할 검색 문자열
  const nextParam = new URLSearchParams(window.location.search).get('next')
  const nextQuery = nextParam ? `?next=${encodeURIComponent(nextParam)}` : ''

  // 로그인 성공 표식 저장 후 이전 화면(없으면 메인) 이동, 인증 쿠키는 서버가 발급
  const finishLogin = (result) => {
    storeUser(result.user)
    onNavigate(getSafeRedirectPath(nextParam), { replace: true })
  }

  // 필수값 확인 및 서버 인증 결과 모달 표시
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
      const result = await signIn({
        username: form.username.trim(),
        password: form.password,
      })
      finishLogin(result)
    } catch (error) {
      if (error.code === 'WITHDRAWAL_PENDING') {
        setWithdrawalPrompt({ message: error.message, token: error.data.recovery_token })
      } else if (error.code === 'EMAIL_NOT_VERIFIED') {
        setVerificationPrompt({ message: error.message, email: error.data.email })
      } else {
        setModalMessage(error.message)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // 탈퇴 유예 계정 복구 토큰 기반 탈퇴 취소 및 로그인
  const restoreAccount = async () => {
    setIsSubmitting(true)
    try {
      const result = await cancelWithdrawal(withdrawalPrompt.token)
      setWithdrawalPrompt(null)
      finishLogin(result)
    } catch (error) {
      setWithdrawalPrompt(null)
      setModalMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  // 인증 메일 재발송 요청 후 결과 안내
  const resendVerification = async () => {
    const { email } = verificationPrompt
    setIsSubmitting(true)
    try {
      const result = await resendVerificationEmail(email)
      setVerificationPrompt(null)
      setModalMessage(result.message)
    } catch (error) {
      setVerificationPrompt(null)
      setModalMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <CustomerAccountShell onNavigate={onNavigate} className="customer-account-page--auth" hideLogin>
      <section className="auth-panel auth-panel--login" aria-labelledby="login-title">
        <header className="auth-header">
          <p className="auth-eyebrow">WELCOME TO ARAM MARKET</p>
          <h1 id="login-title">로그인</h1>
          <p className="auth-description">아람 마켓의 좋은 상품과 나의 주문을 편리하게 만나보세요.</p>
        </header>

        <form className="auth-form auth-form--login" onSubmit={handleSubmit} noValidate>
          <div className="form-field">
            <label htmlFor="login-username">아이디</label>
            <input
              id="login-username"
              name="username"
              type="text"
              autoComplete="username"
              placeholder="아이디를 입력하세요."
              value={form.username}
              onChange={updateField}
              maxLength="20"
              autoFocus
            />
          </div>

          <div className="form-field">
            <label htmlFor="login-password">비밀번호</label>
            <input
              id="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              placeholder="비밀번호를 입력하세요."
              value={form.password}
              onChange={updateField}
              maxLength="64"
            />
          </div>

          <div className="auth-links" aria-label="계정 메뉴">
            <button type="button" onClick={() => onNavigate(`/user/signup${nextQuery}`)}>회원 가입</button>
            <span aria-hidden="true" />
            <button type="button" onClick={() => setRecoveryMode('username')}>아이디 찾기</button>
            <span aria-hidden="true" />
            <button type="button" onClick={() => setRecoveryMode('password')}>비밀번호 찾기</button>
          </div>

          <button className="primary-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? '로그인 중...' : '로그인'}
          </button>
        </form>
      </section>

      <Modal
        isOpen={Boolean(modalMessage)}
        message={modalMessage}
        onClose={() => setModalMessage('')}
      />

      <Modal
        isOpen={Boolean(withdrawalPrompt)}
        message={withdrawalPrompt?.message || ''}
        onClose={() => setWithdrawalPrompt(null)}
        onConfirm={restoreAccount}
        confirmLabel="탈퇴 취소"
        cancelLabel="탈퇴 유지"
        isPending={isSubmitting}
      />

      <Modal
        isOpen={Boolean(verificationPrompt)}
        message={verificationPrompt?.message || ''}
        onClose={() => setVerificationPrompt(null)}
        onConfirm={resendVerification}
        confirmLabel="인증 메일 다시 받기"
        cancelLabel="닫기"
        isPending={isSubmitting}
      />

      <AccountRecoveryModal key={recoveryMode || 'closed'} mode={recoveryMode} onClose={() => setRecoveryMode(null)} />
    </CustomerAccountShell>
  )
}

export default UserLoginPage
