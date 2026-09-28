// 추후 사용자 페이지에서 재사용할 회원가입 화면

import { useState } from 'react'
import { signUp } from '../../api/user-auth.js'
import Modal from '../../components/common/modal.jsx'

const INITIAL_FORM = { // 회원가입 폼의 초기값과 약관 기본 미동의 상태
  username: '',
  password: '',
  nickname: '',
  email: '',
  service_policy: false,
  privacy_policy: false,
}

const USERNAME_PATTERN = /^[A-Za-z0-9_]{4,20}$/ // 서버와 동일한 아이디 형식
const NICKNAME_PATTERN = /^[A-Za-z0-9_가-힣]{2,10}$/ // 서버와 동일한 닉네임 형식
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/ // 기본 이메일 형식

const POLICY_CONTENT = { // 약관 보기 모달에 표시하는 테스트 서비스 안내문
  service_policy: '서비스 이용약관\n\n본 약관은 서비스 이용 조건과 회원의 권리·의무를 정합니다. 회원은 정확한 정보를 제공하고 계정 정보를 안전하게 관리해야 하며, 서비스 운영을 방해하거나 타인의 권리를 침해해서는 안 됩니다. 약관 위반 시 이용이 제한될 수 있습니다.',
  privacy_policy: '개인정보 수집 및 이용 동의\n\n수집 항목: 아이디, 닉네임, 이메일, 비밀번호 해시\n이용 목적: 회원 식별, 계정 관리, 로그인 보안 및 계정 잠금 해제\n보유 기간: 회원 탈퇴 요청 후 7일간 복구를 위해 보관하며, 유예기간 종료 후 다음 한국시간 자정에 삭제합니다. 이 테스트 서비스는 거래·결제 정보를 수집하지 않습니다.',
}

// 서버 규칙과 동일한 형식의 전체 필드 오류 계산
function validate(form) {
  const errors = {}

  if (!form.username.trim()) errors.username = '* 아이디가 입력되지 않았습니다.'
  else if (!USERNAME_PATTERN.test(form.username)) errors.username = '* 영문, 숫자, 밑줄 4~20자로 입력해 주세요.'

  if (!form.password) errors.password = '* 비밀번호가 입력되지 않았습니다.'
  else if (form.password.length < 8 || form.password.length > 64) errors.password = '* 8~64자로 입력해 주세요.'
  else if (!/[A-Za-z]/.test(form.password) || !/\d/.test(form.password) || !/[^A-Za-z0-9]/.test(form.password) || /\s/.test(form.password)) {
    errors.password = '* 영문, 숫자, 특수문자를 각각 1개 이상 포함해 주세요.'
  }

  if (!form.nickname.trim()) errors.nickname = '* 닉네임이 입력되지 않았습니다.'
  else if (!NICKNAME_PATTERN.test(form.nickname)) errors.nickname = '* 한글, 영문, 숫자, 밑줄 2~10자로 입력해 주세요.'

  if (!form.email.trim()) errors.email = '* 이메일이 입력되지 않았습니다.'
  else if (!EMAIL_PATTERN.test(form.email)) errors.email = '* 올바른 이메일 형식으로 입력해 주세요.'

  if (!form.service_policy) errors.service_policy = '* 서비스 이용약관에 동의하지 않았습니다.'
  if (!form.privacy_policy) errors.privacy_policy = '* 개인정보 처리방침에 동의하지 않았습니다.'

  return errors
}

// 회원정보 입력·필드 오류·약관 안내·가입 요청 상태 관리
function UserSignupPage({ onNavigate }) {
  const [form, setForm] = useState(INITIAL_FORM)
  const [errors, setErrors] = useState({})
  const [modalMessage, setModalMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // 텍스트·체크박스 변경값 반영 및 해당 필드 오류 초기화
  const updateField = (event) => {
    const { name, value, checked, type } = event.target
    setForm((current) => ({ ...current, [name]: type === 'checkbox' ? checked : value }))
    setErrors((current) => ({ ...current, [name]: '' }))
  }

  // 필수 약관 전체 동의 일괄 변경
  const toggleAllPolicies = (event) => {
    const { checked } = event.target
    setForm((current) => ({
      ...current,
      service_policy: checked,
      privacy_policy: checked,
    }))
    setErrors((current) => ({ ...current, service_policy: '', privacy_policy: '' }))
  }

  // 클라이언트 검증 후 가입 요청 및 중복 오류 입력칸 연결
  const handleSubmit = async (event) => {
    event.preventDefault()
    const nextErrors = validate(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return

    setIsSubmitting(true)
    try {
      await signUp({
        ...form,
        username: form.username.trim(),
        nickname: form.nickname.trim(),
        email: form.email.trim().toLowerCase(),
      })
      sessionStorage.setItem('authNotice', '관리자 가입 신청이 완료되었습니다. 기존 관리자의 승인 후 로그인할 수 있습니다.')
      onNavigate('/user/login', { replace: true })
    } catch (error) {
      const fieldByCode = {
        USERNAME_EXISTS: 'username',
        NICKNAME_EXISTS: 'nickname',
        EMAIL_EXISTS: 'email',
      }
      const field = fieldByCode[error.code]
      if (field) setErrors((current) => ({ ...current, [field]: '* ' + error.message }))
      else setModalMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  const allPoliciesChecked = form.service_policy && form.privacy_policy

  return (
    <main className="auth-page auth-page--signup">
      <section className="auth-panel auth-panel--signup" aria-labelledby="signup-title">
        <header className="auth-header auth-header--compact">
          <p className="auth-eyebrow">ADMIN REGISTRATION</p>
          <h1 id="signup-title">회원 가입</h1>
          <p className="auth-description">가입 후 기존 관리자의 승인이 완료되어야 로그인할 수 있습니다.</p>
        </header>

        <form className="auth-form auth-form--signup" onSubmit={handleSubmit} noValidate>
          <div className="form-field">
            <label htmlFor="signup-username">아이디</label>
            <input id="signup-username" name="username" type="text" autoComplete="username" placeholder="영문, 숫자, 밑줄 4~20자" value={form.username} onChange={updateField} maxLength="20" aria-invalid={Boolean(errors.username)} autoFocus />
            <p className="field-error" role="alert">{errors.username}</p>
          </div>

          <div className="form-field">
            <label htmlFor="signup-password">비밀번호</label>
            <input id="signup-password" name="password" type="password" autoComplete="new-password" placeholder="영문·숫자·특수문자 포함 8~64자" value={form.password} onChange={updateField} maxLength="64" aria-invalid={Boolean(errors.password)} />
            <p className="field-error" role="alert">{errors.password}</p>
          </div>

          <div className="form-field">
            <label htmlFor="signup-nickname">닉네임</label>
            <input id="signup-nickname" name="nickname" type="text" autoComplete="nickname" placeholder="한글, 영문, 숫자, 밑줄 2~10자" value={form.nickname} onChange={updateField} maxLength="10" aria-invalid={Boolean(errors.nickname)} />
            <p className="field-error" role="alert">{errors.nickname}</p>
          </div>

          <div className="form-field">
            <label htmlFor="signup-email">이메일</label>
            <input id="signup-email" name="email" type="email" autoComplete="email" inputMode="email" placeholder="example@email.com" value={form.email} onChange={updateField} maxLength="254" aria-invalid={Boolean(errors.email)} />
            <p className="field-error" role="alert">{errors.email}</p>
          </div>

          <fieldset className="policy-fieldset">
            <legend>약관 동의</legend>
            <label className="policy-all">
              <input type="checkbox" checked={allPoliciesChecked} onChange={toggleAllPolicies} />
              <span>전체 동의</span>
            </label>
            <div className="policy-list">
              <div className="policy-item">
                <label>
                  <input name="service_policy" type="checkbox" checked={form.service_policy} onChange={updateField} />
                  <span>[필수] 서비스 이용약관 동의</span>
                </label>
                <button type="button" className="policy-view" onClick={() => setModalMessage(POLICY_CONTENT.service_policy)}>보기</button>
              </div>
              <div className="policy-item">
                <label>
                  <input name="privacy_policy" type="checkbox" checked={form.privacy_policy} onChange={updateField} />
                  <span>[필수] 개인정보 수집 및 이용 동의</span>
                </label>
                <button type="button" className="policy-view" onClick={() => setModalMessage(POLICY_CONTENT.privacy_policy)}>보기</button>
              </div>
            </div>
            <p className="field-error" role="alert">{errors.service_policy}</p>
            <p className="field-error" role="alert">{errors.privacy_policy}</p>
          </fieldset>

          <div className="signup-actions">
            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? '신청 중...' : '관리자 가입 신청'}
            </button>
            <button className="back-button" type="button" onClick={() => onNavigate('/user/login')}>로그인 화면으로 돌아가기</button>
          </div>
        </form>
      </section>

      <Modal isOpen={Boolean(modalMessage)} message={modalMessage} onClose={() => setModalMessage('')} />
    </main>
  )
}

export default UserSignupPage
