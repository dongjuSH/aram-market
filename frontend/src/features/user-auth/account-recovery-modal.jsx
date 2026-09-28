// 고객 아이디·비밀번호 찾기 양식

import { useState } from 'react'
import { findUsername, requestPasswordReset } from '../../api/user-auth.js'
import Modal from '../../components/common/modal.jsx'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/ // 서버 요청 전에 확인하는 이메일 형식
const USERNAME_PATTERN = /^[A-Za-z0-9_]{4,20}$/ // 비밀번호 찾기 아이디 형식

// mode에 따른 아이디 찾기 또는 비밀번호 찾기 표시
function AccountRecoveryModal({ mode, onClose, initialValues = {} }) {
  const [form, setForm] = useState({
    username: initialValues.username || '',
    email: initialValues.email || '',
  })
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [resultMessage, setResultMessage] = useState('')
  const [isPending, setIsPending] = useState(false)

  if (!mode) return null

  const isUsernameMode = mode === 'username'
  const title = isUsernameMode
    ? '가입 이메일을 입력해 주세요. 일치하는 계정이 있으면 아이디를 이메일로 안내합니다.'
    : '아이디와 가입 이메일을 입력해 주세요. 일치하는 계정이 있으면 재설정 링크를 보내드립니다.'

  // 모달 입력값 갱신 및 수정 필드 오류 제거
  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: '' }))
    setFormError('')
  }

  // 입력 누락 및 이메일 형식을 필드별 오류 문구로 변환
  const validate = () => {
    const nextErrors = {}
    if (!isUsernameMode && !form.username.trim()) nextErrors.username = '* 아이디가 입력되지 않았습니다.'
    else if (!isUsernameMode && !USERNAME_PATTERN.test(form.username.trim())) nextErrors.username = '* 영문, 숫자, 밑줄 4~20자로 입력해 주세요.'
    if (!form.email.trim()) nextErrors.email = '* 이메일이 입력되지 않았습니다.'
    else if (!EMAIL_PATTERN.test(form.email.trim())) nextErrors.email = '* 올바른 이메일 형식으로 입력해 주세요.'
    return nextErrors
  }

  // 성공 결과 모달 표시 및 서버 오류 폼 하단 표시
  const submit = async () => {
    if (resultMessage) {
      onClose()
      return
    }

    const nextErrors = validate()
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return

    setFormError('')
    setIsPending(true)
    try {
      if (isUsernameMode) {
        const result = await findUsername({ email: form.email.trim().toLowerCase() })
        setResultMessage(result.message)
      } else {
        const result = await requestPasswordReset({
          username: form.username.trim(),
          email: form.email.trim().toLowerCase(),
        })
        setResultMessage(result.message)
      }
    } catch (error) {
      setFormError('* ' + error.message)
    } finally {
      setIsPending(false)
    }
  }

  return (
    <Modal
      isOpen
      message={resultMessage || title}
      onClose={onClose}
      onConfirm={submit}
      confirmLabel={resultMessage ? '확인' : isUsernameMode ? '아이디 찾기' : '재설정 메일 받기'}
      cancelLabel={resultMessage ? undefined : '취소'}
      isPending={isPending}
    >
      {!resultMessage && (
        <div className="recovery-fields">
          {!isUsernameMode && (
            <div className="modal-form-field">
              <label htmlFor="recovery-username">아이디</label>
              <input id="recovery-username" name="username" autoComplete="username" value={form.username} onChange={updateField} maxLength="20" placeholder="아이디를 입력하세요." aria-invalid={Boolean(errors.username)} />
              <p className="field-error" role="alert">{errors.username}</p>
            </div>
          )}
          <div className="modal-form-field">
            <label htmlFor="recovery-email">이메일</label>
            <input id="recovery-email" name="email" type="email" autoComplete="email" value={form.email} onChange={updateField} maxLength="254" placeholder="example@email.com" aria-invalid={Boolean(errors.email)} />
            <p className="field-error" role="alert">{errors.email}</p>
          </div>
          <p className="modal-form-error" role="alert">{formError}</p>
        </div>
      )}
    </Modal>
  )
}

export default AccountRecoveryModal
