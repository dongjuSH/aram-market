// 이메일 인증 링크의 토큰을 서버에 확인하고 결과를 안내하는 화면

import { useEffect, useRef, useState } from 'react'
import { confirmEmailChange, verifyEmail } from '../../api/user-auth.js'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'

// 링크 토큰 검증 상태(loading, success, failed)를 표시
function UserVerifyEmailPage({ onNavigate }) {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token') || ''
  const isEmailChange = params.get('type') === 'email-change' // 마이 페이지 이메일 변경 확인 링크 여부
  const [state, setState] = useState(token ? { status: 'loading', message: '' } : { status: 'failed', message: '인증 링크가 올바르지 않습니다.' })
  const requestedRef = useRef(false) // 개발 모드 이중 실행에도 토큰 확인은 한 번만 요청

  useEffect(() => {
    if (!token || requestedRef.current) return
    requestedRef.current = true
    const confirmation = isEmailChange ? confirmEmailChange(token) : verifyEmail(token)
    confirmation
      .then((result) => setState({ status: 'success', message: result.message }))
      .catch((error) => setState({ status: 'failed', message: error.message }))
  }, [token, isEmailChange])

  return (
    <CustomerAccountShell onNavigate={onNavigate} className="customer-account-page--auth">
      <section className="auth-panel auth-panel--login" aria-labelledby="verify-title">
        <header className="auth-header">
          <p className="auth-eyebrow">EMAIL VERIFICATION</p>
          <h1 id="verify-title">
            {state.status === 'loading' && (isEmailChange ? '이메일 변경 확인 중' : '이메일 인증 중')}
            {state.status === 'success' && (isEmailChange ? '이메일 변경 완료' : '이메일 인증 완료')}
            {state.status === 'failed' && (isEmailChange ? '이메일 변경 실패' : '이메일 인증 실패')}
          </h1>
          <p className="auth-description" role="status">
            {state.status === 'loading' ? '링크를 확인하고 있습니다.' : state.message}
          </p>
        </header>
        {state.status !== 'loading' && (
          <div className="signup-actions">
            <button className="primary-button" type="button" onClick={() => onNavigate(isEmailChange ? '/user' : '/user/login', { replace: true })}>
              {isEmailChange ? '마이 페이지로 이동' : '로그인 화면으로 이동'}
            </button>
          </div>
        )}
      </section>
    </CustomerAccountShell>
  )
}

export default UserVerifyEmailPage
