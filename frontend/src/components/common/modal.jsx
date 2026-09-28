// 경고·안내·입력 폼 공통 접근성 모달 UI

import { useEffect, useRef } from 'react'

// Escape 닫기·포커스 고정·이전 포커스 복원·확인·취소 공통 처리
function Modal({
  isOpen,
  message,
  onClose,
  onConfirm = onClose,
  confirmLabel = '확인',
  cancelLabel,
  isPending = false,
  tone = 'default',
  messageClassName = '',
  children,
}) {
  const modalRef = useRef(null)
  const confirmRef = useRef(null)
  const previousFocusRef = useRef(null)
  const formattedMessage = String(message || '').replace(/\.\s+/g, '.\n') // 마침표 다음 문장을 새 줄로 분리

  // 모달이 열리면 확인 버튼으로 이동하고 닫히면 기존 요소로 포커스 복원
  useEffect(() => {
    if (!isOpen) return undefined

    previousFocusRef.current = document.activeElement
    confirmRef.current?.focus()
    return () => previousFocusRef.current?.focus()
  }, [isOpen])

  // Escape 닫기 및 Tab 키가 모달 밖으로 빠져나가지 않도록 포커스 순환
  useEffect(() => {
    if (!isOpen) return undefined

    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !isPending) onClose()
      if (event.key !== 'Tab') return

      const focusableElements = modalRef.current?.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      )
      if (!focusableElements?.length) return

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault()
        firstElement.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isPending, onClose])

  if (!isOpen) return null

  return (
    <div className="modal-overlay" role="presentation">
      <section ref={modalRef} className="modal" role="alertdialog" aria-modal="true" aria-describedby="modal-message">
        <button className="modal-close" type="button" aria-label="팝업 닫기" onClick={onClose} disabled={isPending}>
          <span aria-hidden="true" />
        </button>

        <div className="modal-content">
          <p
            id="modal-message"
            className={[
              'modal-message',
              formattedMessage.length > 120 ? 'modal-message--long' : '',
              messageClassName,
            ].filter(Boolean).join(' ')}
          >
            {formattedMessage}
          </p>
          {children}
        </div>

        <div className="modal-actions">
          {cancelLabel && (
            <button className="modal-cancel" type="button" onClick={onClose} disabled={isPending}>
              {cancelLabel}
            </button>
          )}
          <button
            ref={confirmRef}
            className={'modal-confirm modal-confirm--' + tone}
            type="button"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? '처리 중...' : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  )
}

export default Modal
