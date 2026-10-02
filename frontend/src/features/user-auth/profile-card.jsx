// 마이 페이지 회원정보 카드: 조회, 닉네임 수정, 이메일 변경(메일 확인 후 반영), 마케팅 수신 설정. 받는 분 이름·연락처는 배송지 관리에서 다룸

import { useState } from 'react'
import { requestEmailChange, storeUser, updateMarketingConsent, updateProfile } from '../../api/user-auth.js'

// 서버와 같은 기준의 닉네임 확인(오류 문구 반환)
function validateNickname(nickname) {
  return /^[A-Za-z0-9_가-힣]{2,10}$/.test(nickname.trim()) ? '' : '닉네임은 한글, 영문, 숫자, 밑줄 2~10자로 입력해 주세요.'
}

// 회원정보 보기·닉네임 수정·이메일 변경·수신 설정 패널
function ProfileCard({ user, onUserChange, onNotice }) {
  const [mode, setMode] = useState('view') // view, edit, email
  const [form, setForm] = useState(null)
  const [emailForm, setEmailForm] = useState({ newEmail: '', password: '' })
  const [error, setError] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isSavingMarketing, setIsSavingMarketing] = useState(false)

  const startEdit = () => {
    setForm({ nickname: user.nickname || '' })
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

  // 마케팅 정보 수신 동의 변경(동의·철회 이력은 서버가 기록)
  async function changeMarketingConsent(event) {
    const nextValue = event.target.checked
    setIsSavingMarketing(true)
    try {
      const result = await updateMarketingConsent(nextValue)
      onUserChange(result.user)
      storeUser(result.user)
      onNotice(nextValue ? '마케팅 정보 수신에 동의했습니다.' : '마케팅 정보 수신 동의를 철회했습니다.')
    } catch (requestError) {
      onNotice(requestError.message)
    } finally {
      setIsSavingMarketing(false)
    }
  }

  // 수정한 닉네임 저장
  async function saveProfile(event) {
    event.preventDefault()
    const validationMessage = validateNickname(form.nickname)
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
      </div>

      {mode === 'view' && (
        <>
          <dl className="profile-rows">
            <div>
              <dt>닉네임</dt>
              <dd>
                <span>{user.nickname}</span>
                <span className="profile-actions"><button type="button" onClick={startEdit}>닉네임 변경</button></span>
              </dd>
            </div>
            <div>
              <dt>이메일</dt>
              <dd>
                <span>{user.email}</span>
                <span className="profile-actions"><button type="button" onClick={startEmailChange}>이메일 변경</button></span>
              </dd>
            </div>
          </dl>
          <label className="my-page-switch">
            <span>
              <strong>[선택] 마케팅 정보 수신 동의</strong>
              <small>신상품, 혜택 및 이벤트 안내를 이메일로 받아봅니다.</small>
            </span>
            <input type="checkbox" role="switch" checked={Boolean(user.marketing_consent)} onChange={changeMarketingConsent} disabled={isSavingMarketing} />
          </label>
        </>
      )}

      {mode === 'edit' && (
        <form className="profile-form" onSubmit={saveProfile} noValidate>
          <label><span>닉네임</span><input name="nickname" value={form.nickname} maxLength={10} onChange={updateField} /></label>
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
