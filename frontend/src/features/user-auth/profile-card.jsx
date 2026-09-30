// 마이 페이지 회원정보 카드: 조회, 닉네임·이름·휴대폰 수정, 이메일 변경(메일 확인 후 반영). 배송지는 배송지 관리에서 다룸

import { useState } from 'react'
import { requestEmailChange, storeUser, updateProfile } from '../../api/user-auth.js'

// 서버와 같은 기준의 입력 확인(첫 오류 문구 반환)
function validateProfile(form) {
  if (!/^[A-Za-z0-9_가-힣]{2,10}$/.test(form.nickname.trim())) return '닉네임은 한글, 영문, 숫자, 밑줄 2~10자로 입력해 주세요.'
  if (form.name.trim().length < 2) return '이름을 2자 이상 입력해 주세요.'
  if (!/^01[016789]\d{7,8}$/.test(form.phone.replace(/\D/g, ''))) return '휴대폰 번호를 010-1234-5678 형식으로 입력해 주세요.'
  return ''
}

// 값이 없으면 안내 문구를 보여주는 표시 값
function Value({ children, emptyText }) {
  return children ? <>{children}</> : <span className="profile-rows__empty">{emptyText}</span>
}

// 회원정보 보기·수정·이메일 변경 패널
function ProfileCard({ user, onUserChange, onNotice }) {
  const [mode, setMode] = useState('view') // view, edit, email
  const [form, setForm] = useState(null)
  const [emailForm, setEmailForm] = useState({ newEmail: '', password: '' })
  const [error, setError] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const startEdit = () => {
    setForm({
      nickname: user.nickname || '',
      name: user.name || '',
      phone: user.phone || '',
    })
    setError('')
    setMode('edit')
  }

  const startEmailChange = () => {
    setEmailForm({ newEmail: '', password: '' })
    setError('')
    setMode('email')
  }

  const cancel = () => {
    setMode('view')
    setError('')
  }

  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
  }

  // 수정한 회원정보 저장
  async function saveProfile(event) {
    event.preventDefault()
    const validationMessage = validateProfile(form)
    if (validationMessage) {
      setError(validationMessage)
      return
    }
    setIsSaving(true)
    setError('')
    try {
      const result = await updateProfile(form)
      onUserChange(result.user)
      storeUser(result.user)
      setMode('view')
      onNotice('회원정보가 저장되었습니다.')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSaving(false)
    }
  }

  // 새 이메일로 확인 메일 요청(메일의 링크를 눌러야 실제로 바뀜)
  async function submitEmailChange(event) {
    event.preventDefault()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailForm.newEmail.trim())) {
      setError('올바른 이메일 형식으로 입력해 주세요.')
      return
    }
    if (!emailForm.password) {
      setError('현재 비밀번호를 입력해 주세요.')
      return
    }
    setIsSaving(true)
    setError('')
    try {
      const result = await requestEmailChange({ newEmail: emailForm.newEmail.trim(), password: emailForm.password })
      setMode('view')
      onNotice(result.message)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <section className="my-page-card my-page-profile" aria-labelledby="profile-title">
      <div className="my-page-card__heading">
        <div>
          <p>ACCOUNT</p>
          <h2 id="profile-title">회원정보</h2>
        </div>
        {mode === 'view' && (
          <div className="profile-actions">
            <button type="button" onClick={startEdit}>정보 수정</button>
            <button type="button" onClick={startEmailChange}>이메일 변경</button>
          </div>
        )}
      </div>

      {mode === 'view' && (
        <dl className="profile-rows">
          <div><dt>닉네임</dt><dd>{user.nickname}</dd></div>
          <div><dt>이름</dt><dd><Value emptyText="미등록 (주문서 받는 분 자동 입력에 사용돼요)">{user.name}</Value></dd></div>
          <div><dt>휴대폰 번호</dt><dd><Value emptyText="미등록">{user.phone}</Value></dd></div>
          <div><dt>이메일</dt><dd>{user.email}</dd></div>
        </dl>
      )}

      {mode === 'edit' && (
        <form className="profile-form" onSubmit={saveProfile} noValidate>
          <label><span>닉네임</span><input name="nickname" value={form.nickname} maxLength={10} onChange={updateField} /></label>
          <label><span>이름</span><input name="name" value={form.name} maxLength={30} autoComplete="name" onChange={updateField} /></label>
          <label><span>휴대폰 번호</span><input name="phone" value={form.phone} maxLength={20} inputMode="tel" autoComplete="tel" placeholder="010-1234-5678" onChange={updateField} /></label>
          {error && <p className="profile-form__error" role="alert">{error}</p>}
          <div className="profile-form__actions">
            <button type="button" onClick={cancel}>취소</button>
            <button className="is-primary" type="submit" disabled={isSaving}>{isSaving ? '저장 중...' : '저장'}</button>
          </div>
        </form>
      )}

      {mode === 'email' && (
        <form className="profile-form" onSubmit={submitEmailChange} noValidate>
          <p className="profile-form__hint">현재 이메일: <strong>{user.email}</strong><br />새 이메일로 확인 메일이 발송되며, 메일의 링크를 누르면 이메일이 변경됩니다. 그 전까지는 기존 이메일이 유지돼요.</p>
          <label><span>새 이메일</span><input type="email" value={emailForm.newEmail} maxLength={254} inputMode="email" autoComplete="email" onChange={(event) => setEmailForm((current) => ({ ...current, newEmail: event.target.value }))} /></label>
          <label><span>현재 비밀번호</span><input type="password" value={emailForm.password} maxLength={64} autoComplete="current-password" onChange={(event) => setEmailForm((current) => ({ ...current, password: event.target.value }))} /></label>
          {error && <p className="profile-form__error" role="alert">{error}</p>}
          <div className="profile-form__actions">
            <button type="button" onClick={cancel}>취소</button>
            <button className="is-primary" type="submit" disabled={isSaving}>{isSaving ? '보내는 중...' : '확인 메일 보내기'}</button>
          </div>
        </form>
      )}
    </section>
  )
}

export default ProfileCard
