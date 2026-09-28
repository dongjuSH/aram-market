// 추후 사용자 페이지에서 재사용할 7일 유예 회원 탈퇴 모달

import { useState } from 'react'
import { deleteAccount } from '../../api/user-auth.js'
import Modal from '../../components/common/modal.jsx'

// 탈퇴 안내·현재 비밀번호 검증 오류·서버 요청 상태 관리
function DeleteAccountModal({ isOpen, onClose, onDeleted }) {
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [isPending, setIsPending] = useState(false)

  // 비밀번호 확인 후 계정을 7일 탈퇴 대기 상태로 전환
  const submit = async () => {
    if (!password) {
      setErrorMessage('* 비밀번호가 입력되지 않았습니다.')
      return
    }

    setIsPending(true)
    try {
      const result = await deleteAccount({ password })
      onDeleted(result.message)
    } catch (error) {
      setErrorMessage('* ' + error.message)
    } finally {
      setIsPending(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      message={'회원 탈퇴를 신청하면 즉시 로그아웃됩니다.\n7일 이내 다시 로그인하면 탈퇴를 취소할 수 있습니다.'}
      onClose={onClose}
      onConfirm={submit}
      confirmLabel="회원 탈퇴 신청"
      cancelLabel="취소"
      isPending={isPending}
      tone="danger"
    >
      <div className="recovery-fields">
        <div className="modal-form-field">
          <label htmlFor="delete-password">현재 비밀번호</label>
          <input
            id="delete-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value)
              setErrorMessage('')
            }}
            maxLength="64"
            placeholder="비밀번호를 입력하세요."
            aria-invalid={Boolean(errorMessage)}
          />
          <p className="field-error" role="alert">{errorMessage}</p>
        </div>
      </div>
    </Modal>
  )
}

export default DeleteAccountModal
