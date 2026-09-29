// 고객 회원가입 화면

import { useEffect, useState } from 'react'
import { getPolicies, signUp } from '../../api/user-auth.js'
import Modal from '../../components/common/modal.jsx'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'

const INITIAL_FORM = { // 회원가입 폼의 초기값과 약관 기본 미동의 상태
  username: '',
  password: '',
  password_confirm: '',
  nickname: '',
  email: '',
  service_policy: false,
  privacy_policy: false,
  marketing_consent: false,
}

const USERNAME_PATTERN = /^[A-Za-z0-9_]{4,20}$/ // 서버와 동일한 아이디 형식
const NICKNAME_PATTERN = /^[A-Za-z0-9_가-힣]{2,10}$/ // 서버와 동일한 닉네임 형식
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/ // 기본 이메일 형식

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

  if (!form.password_confirm) errors.password_confirm = '* 비밀번호 확인이 입력되지 않았습니다.'
  else if (form.password !== form.password_confirm) errors.password_confirm = '* 비밀번호가 일치하지 않습니다.'

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
  const nextParam = new URLSearchParams(window.location.search).get('next') // 로그인 뒤 돌아갈 화면을 로그인 화면까지 전달
  const nextQuery = nextParam ? `?next=${encodeURIComponent(nextParam)}` : ''
  const [form, setForm] = useState(INITIAL_FORM)
  const [errors, setErrors] = useState({})
  const [modalMessage, setModalMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [policies, setPolicies] = useState({}) // 약관 종류별 현재 시행 버전과 본문

  // 서버가 관리하는 현재 시행 약관과 버전 조회
  useEffect(() => {
    getPolicies()
      .then((result) => setPolicies(Object.fromEntries(result.policies.map((policy) => [policy.type, policy]))))
      .catch((error) => setModalMessage(`약관을 불러오지 못했습니다. ${error.message}`))
  }, [])

  // 텍스트·체크박스 변경값 반영 및 해당 필드 오류 초기화
  const updateField = (event) => {
    const { name, value, checked, type } = event.target
    setForm((current) => ({ ...current, [name]: type === 'checkbox' ? checked : value }))
    setErrors((current) => ({ ...current, [name]: '', ...(name === 'password' ? { password_confirm: '' } : {}) }))
  }

  // 필수 약관 전체 동의 일괄 변경
  const toggleAllPolicies = (event) => {
    const { checked } = event.target
    setForm((current) => ({
      ...current,
      service_policy: checked,
      privacy_policy: checked,
      marketing_consent: checked,
    }))
    setErrors((current) => ({ ...current, service_policy: '', privacy_policy: '' }))
  }

  // 클라이언트 검증 후 가입 요청 및 중복 오류 입력칸 연결
  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!policies.service || !policies.privacy || !policies.marketing) {
      setModalMessage('약관을 불러오는 중입니다. 잠시 후 다시 시도해 주세요.')
      return
    }
    const nextErrors = validate(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return

    setIsSubmitting(true)
    try {
      const result = await signUp({
        ...form,
        username: form.username.trim(),
        nickname: form.nickname.trim(),
        email: form.email.trim().toLowerCase(),
        // 화면에서 동의한 약관의 버전(서버가 현재 시행 버전과 대조)
        policy_versions: Object.fromEntries(Object.values(policies).map((policy) => [policy.type, policy.version])),
      })
      sessionStorage.setItem(
        'authNotice',
        result.email_verification_sent
          ? `회원 가입이 완료되었습니다. ${form.email.trim().toLowerCase()}로 발송된 인증 링크를 열어 이메일 인증을 완료해 주세요.`
          : '회원 가입이 완료되었습니다. 인증 메일을 보내지 못했으니 로그인을 시도해 인증 메일을 다시 요청해 주세요.',
      )
      onNavigate(`/user/login${nextQuery}`, { replace: true })
    } catch (error) {
      if (error.code === 'POLICY_VERSION_MISMATCH') {
        getPolicies().then((latest) => setPolicies(Object.fromEntries(latest.policies.map((policy) => [policy.type, policy])))).catch(() => {})
        setForm((current) => ({ ...current, service_policy: false, privacy_policy: false, marketing_consent: false }))
      }
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

  const allPoliciesChecked = form.service_policy && form.privacy_policy && form.marketing_consent

  return (
    <CustomerAccountShell onNavigate={onNavigate} className="customer-account-page--auth customer-account-page--signup">
      <section className="auth-panel auth-panel--signup" aria-labelledby="signup-title">
        <header className="auth-header auth-header--compact">
          <p className="auth-eyebrow">JOIN ARAM MARKET</p>
          <h1 id="signup-title">회원 가입</h1>
          <p className="auth-description">필수 정보를 입력하고 아람 마켓의 회원 서비스를 시작해 보세요.</p>
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
            <label htmlFor="signup-password-confirm">비밀번호 확인</label>
            <input id="signup-password-confirm" name="password_confirm" type="password" autoComplete="new-password" placeholder="비밀번호를 한 번 더 입력하세요." value={form.password_confirm} onChange={updateField} maxLength="64" aria-invalid={Boolean(errors.password_confirm)} />
            <p className="field-error" role="alert">{errors.password_confirm}</p>
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
                <button type="button" className="policy-view" onClick={() => setModalMessage(policies.service?.content || '약관을 불러오는 중입니다.')}>보기</button>
              </div>
              <div className="policy-item">
                <label>
                  <input name="privacy_policy" type="checkbox" checked={form.privacy_policy} onChange={updateField} />
                  <span>[필수] 개인정보 수집 및 이용 동의</span>
                </label>
                <button type="button" className="policy-view" onClick={() => setModalMessage(policies.privacy?.content || '약관을 불러오는 중입니다.')}>보기</button>
              </div>
              <div className="policy-item">
                <label>
                  <input name="marketing_consent" type="checkbox" checked={form.marketing_consent} onChange={updateField} />
                  <span>[선택] 마케팅 정보 수신 동의</span>
                </label>
                <button type="button" className="policy-view" onClick={() => setModalMessage(policies.marketing?.content || '약관을 불러오는 중입니다.')}>보기</button>
              </div>
            </div>
            <p className="field-error" role="alert">{errors.service_policy}</p>
            <p className="field-error" role="alert">{errors.privacy_policy}</p>
          </fieldset>

          <div className="signup-actions">
            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? '가입 중...' : '회원 가입'}
            </button>
            <button className="back-button" type="button" onClick={() => onNavigate(`/user/login${nextQuery}`)}>로그인 화면으로 돌아가기</button>
          </div>
        </form>
      </section>

      <Modal
        isOpen={Boolean(modalMessage)}
        message={modalMessage}
        messageClassName="modal-message--policy"
        onClose={() => setModalMessage('')}
      />
    </CustomerAccountShell>
  )
}

export default UserSignupPage
