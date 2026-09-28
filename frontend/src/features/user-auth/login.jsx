// 추후 사용자 페이지에서 재사용할 로그인·계정 찾기·탈퇴 복구 화면

import { useState } from 'react'
import { cancelWithdrawal, signIn } from '../../api/user-auth.js'
import Modal from '../../components/common/modal.jsx'
import AccountRecoveryModal from './account-recovery-modal.jsx'

// 회원가입·잠금 해제 후 전달된 일회성 안내 조회
function getInitialNotice() {
  const savedNotice = sessionStorage.getItem('authNotice')
  sessionStorage.removeItem('authNotice')
  if (savedNotice) return savedNotice

  const unlockStatus = new URLSearchParams(window.location.search).get('unlock')
  if (unlockStatus === 'success') return '계정 잠금이 해제되었습니다. 다시 로그인해 주세요.'
  if (unlockStatus === 'failed') return '잠금 해제 링크가 유효하지 않거나 만료되었습니다.'
  return ''
}

// 로그인 입력·계정 찾기 모달·탈퇴 복구 확인 상태 관리
function UserLoginPage({ onNavigate }) {
  const [form, setForm] = useState({ username: '', password: '' })
  const [modalMessage, setModalMessage] = useState(getInitialNotice)
  const [recoveryMode, setRecoveryMode] = useState(null)
  const [withdrawalPrompt, setWithdrawalPrompt] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // 입력값 변경을 로그인 폼 상태에 반영
  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
  }

  // 로그인 성공 정보 저장 및 상품 조회 화면 이동
  const finishLogin = (result) => {
    sessionStorage.setItem('userAccessToken', result.access_token)
    sessionStorage.setItem('userCurrentUser', JSON.stringify(result.user))
    onNavigate('/user', { replace: true })
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

  return (
    <main className="auth-page">
      <section className="auth-panel auth-panel--login" aria-labelledby="login-title">
        <header className="auth-header">
          <p className="auth-eyebrow">PRODUCT MANAGEMENT</p>
          <h1 id="login-title">관리자 로그인</h1>
          <p className="auth-description">본 시스템은 허가된 사용자만 접근할 수 있습니다.</p>
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
            <button type="button" onClick={() => onNavigate('/user/signup')}>회원 가입</button>
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

      <AccountRecoveryModal key={recoveryMode || 'closed'} mode={recoveryMode} onClose={() => setRecoveryMode(null)} />
    </main>
  )
}

export default UserLoginPage
