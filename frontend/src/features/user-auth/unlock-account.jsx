// 잠금 해제 메일 링크에서 열리며 버튼을 눌렀을 때만 계정 잠금을 해제하는 화면

import { useState } from 'react'
import { unlockAccount } from '../../api/user-auth.js'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'

// 확인 전(ready)·처리 중(loading)·완료(success)·실패(failed) 상태를 표시
function UserUnlockAccountPage({ onNavigate }) {
  const token = new URLSearchParams(window.location.search).get('token') || ''
  const [state, setState] = useState(token ? { status: 'ready', message: '' } : { status: 'failed', message: '잠금 해제 링크가 올바르지 않습니다.' })

  // 메일 링크를 미리 열어보는 것만으로는 해제되지 않도록 버튼 클릭 시에만 POST 요청
  const handleUnlock = async () => {
    setState({ status: 'loading', message: '' })
    try {
      const result = await unlockAccount(token)
      setState({ status: 'success', message: result.message })
    } catch (error) {
      setState({ status: 'failed', message: error.message })
    }
  }

  return (
    <CustomerAccountShell onNavigate={onNavigate} className="customer-account-page--auth">
      <section className="auth-panel auth-panel--login" aria-labelledby="unlock-title">
        <header className="auth-header">
          <p className="auth-eyebrow">ACCOUNT UNLOCK</p>
          <h1 id="unlock-title">
            {state.status === 'success' ? '잠금 해제 완료' : state.status === 'failed' ? '잠금 해제 실패' : '계정 잠금 해제'}
          </h1>
          <p className="auth-description" role="status">
            {state.status === 'ready' && '본인의 로그인 시도였다면 아래 버튼을 눌러 계정 잠금을 해제해 주세요.'}
            {state.status === 'loading' && '잠금을 해제하고 있습니다.'}
            {(state.status === 'success' || state.status === 'failed') && state.message}
          </p>
        </header>
        <div className="signup-actions">
          {state.status === 'ready' && (
            <button className="primary-button" type="button" onClick={handleUnlock}>계정 잠금 해제</button>
          )}
          {(state.status === 'success' || state.status === 'failed') && (
            <button className="primary-button" type="button" onClick={() => onNavigate('/user/login', { replace: true })}>로그인 화면으로 이동</button>
          )}
        </div>
      </section>
    </CustomerAccountShell>
  )
}

export default UserUnlockAccountPage
