// 로그인 사용자의 현재 비밀번호 확인과 새 비밀번호 변경 모달

import { useState } from 'react'
import { changePassword } from '../../api/user-auth.js'
import Modal from '../../components/common/modal.jsx'


function ChangePasswordModal({ isOpen, onClose, onChanged }) {
  const [form, setForm] = useState({ currentPassword: '', newPassword: '', passwordConfirm: '' })
  const [errors, setErrors] = useState({})
  const [isPending, setIsPending] = useState(false)

  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: '', form: '' }))
  }

  const submit = async () => {
    const nextErrors = {}
    if (!form.currentPassword) nextErrors.currentPassword = '* 현재 비밀번호를 입력해 주세요.'
    if (!form.newPassword) nextErrors.newPassword = '* 새 비밀번호를 입력해 주세요.'
    else if (
      form.newPassword.length < 8
      || !/[A-Za-z]/.test(form.newPassword)
      || !/\d/.test(form.newPassword)
      || !/[^A-Za-z0-9]/.test(form.newPassword)
      || /\s/.test(form.newPassword)
    ) nextErrors.newPassword = '* 영문, 숫자, 특수문자를 포함한 8~64자로 입력해 주세요.'
    if (!form.passwordConfirm) nextErrors.passwordConfirm = '* 새 비밀번호를 다시 입력해 주세요.'
    else if (form.newPassword !== form.passwordConfirm) nextErrors.passwordConfirm = '* 새 비밀번호가 일치하지 않습니다.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return

    setIsPending(true)
    try {
      const result = await changePassword({
        currentPassword: form.currentPassword,
        newPassword: form.newPassword,
      })
      onChanged(result.message)
    } catch (error) {
      setErrors((current) => ({ ...current, form: '* ' + error.message }))
    } finally {
      setIsPending(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      message="안전한 계정 이용을 위해 현재 비밀번호와 새 비밀번호를 입력해 주세요."
      onClose={onClose}
      onConfirm={submit}
      confirmLabel="비밀번호 변경"
      cancelLabel="취소"
      isPending={isPending}
    >
      <div className="recovery-fields">
        <div className="modal-form-field">
          <label htmlFor="change-current-password">현재 비밀번호</label>
          <input id="change-current-password" name="currentPassword" type="password" autoComplete="current-password" value={form.currentPassword} onChange={updateField} maxLength="64" aria-invalid={Boolean(errors.currentPassword)} />
          <p className="field-error" role="alert">{errors.currentPassword}</p>
        </div>
        <div className="modal-form-field">
          <label htmlFor="change-new-password">새 비밀번호</label>
          <input id="change-new-password" name="newPassword" type="password" autoComplete="new-password" value={form.newPassword} onChange={updateField} maxLength="64" placeholder="영문·숫자·특수문자 포함 8~64자" aria-invalid={Boolean(errors.newPassword)} />
          <p className="field-error" role="alert">{errors.newPassword}</p>
        </div>
        <div className="modal-form-field">
          <label htmlFor="change-password-confirm">새 비밀번호 확인</label>
          <input id="change-password-confirm" name="passwordConfirm" type="password" autoComplete="new-password" value={form.passwordConfirm} onChange={updateField} maxLength="64" aria-invalid={Boolean(errors.passwordConfirm)} />
          <p className="field-error" role="alert">{errors.passwordConfirm}</p>
        </div>
        <p className="modal-form-error" role="alert">{errors.form}</p>
      </div>
    </Modal>
  )
}

export default ChangePasswordModal
