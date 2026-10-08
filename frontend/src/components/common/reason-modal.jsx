// 주문 취소·환불 사유 선택(목록 + '기타' 직접 입력) 또는 사유 직접 입력(관리자 거절)을 받는 공용 모달

import { useState } from 'react'
import Modal from './modal.jsx'
import { REASON_DETAIL_MAX_LENGTH } from '../../config/refund.js'

// reasons가 있으면 목록에서 고르고 '기타'일 때만 입력, 없으면 입력 칸 하나(필수, textMaxLength자 이하)
// onSubmit({ reasonCode, reasonDetail })이 실패하면 오류 문구를 모달 안에 보여 주고, 성공하면 부모가 닫음
function ReasonModal({ isOpen, message, reasons, textLabel = '사유', textMaxLength = REASON_DETAIL_MAX_LENGTH, confirmLabel, tone = 'default', onClose, onSubmit }) {
  const [reasonCode, setReasonCode] = useState('')
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [isPending, setIsPending] = useState(false)
  const needsText = !reasons || reasonCode === 'other'

  const submit = async () => {
    if (reasons && !reasonCode) return setError('사유를 선택해 주세요.')
    if (needsText && !text.trim()) return setError(reasons ? '기타 사유를 입력해 주세요.' : `${textLabel}를 입력해 주세요.`)
    setIsPending(true)
    try {
      await onSubmit({ reasonCode, reasonDetail: needsText ? text.trim() : '' })
    } catch (submitError) {
      setError(submitError.message || '요청을 처리하지 못했습니다.')
    } finally {
      setIsPending(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      message={message}
      onClose={onClose}
      onConfirm={submit}
      confirmLabel={confirmLabel}
      cancelLabel="닫기"
      isPending={isPending}
      tone={tone}
    >
      <div className="reason-modal">
        {reasons && (
          <fieldset className="reason-modal__options">
            <legend>사유 선택</legend>
            {reasons.map((reason) => (
              <label key={reason.code}>
                <input
                  type="radio"
                  name="reason-code"
                  value={reason.code}
                  checked={reasonCode === reason.code}
                  onChange={() => {
                    setReasonCode(reason.code)
                    setError('')
                  }}
                  disabled={isPending}
                />
                <span>{reason.label}</span>
              </label>
            ))}
          </fieldset>
        )}
        {needsText && (
          <label className="reason-modal__text">
            <span>{reasons ? '기타 사유' : textLabel}</span>
            <textarea
              value={text}
              maxLength={textMaxLength}
              rows={3}
              onChange={(event) => {
                setText(event.target.value)
                setError('')
              }}
              disabled={isPending}
              aria-invalid={Boolean(error)}
            />
            <small>{text.length} / {textMaxLength}</small>
          </label>
        )}
        <p className="field-error" role="alert">{error}</p>
      </div>
    </Modal>
  )
}

export default ReasonModal
