// 비로그인 고객이 찜 기능을 쓰려 할 때 로그인 이동을 안내하는 공통 모달

import Modal from './modal.jsx'

// 확인을 누르면 onConfirm(로그인 페이지 이동), 취소·Escape는 onClose
function WishlistLoginModal({ isOpen, onClose, onConfirm }) {
  return (
    <Modal
      isOpen={isOpen}
      message="찜하기는 로그인 후 이용할 수 있어요. 확인을 누르면 로그인 페이지로 이동합니다."
      confirmLabel="로그인하기"
      cancelLabel="취소"
      onClose={onClose}
      onConfirm={onConfirm}
    />
  )
}

export default WishlistLoginModal
