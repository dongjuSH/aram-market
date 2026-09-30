// 배송지 입력 초기값과 검증 규칙(주소록 관리·주문서 새 배송지 공통, 서버 core/address.py와 같은 기준)

export const EMPTY_ADDRESS = { recipientName: '', recipientPhone: '', postcode: '', address: '', addressDetail: '' }

// 첫 오류 문구 반환(없으면 빈 문자열)
export function validateAddress(values) {
  if (values.recipientName.trim().length < 2) return '받는 분 이름을 2자 이상 입력해 주세요.'
  if (!/^01[016789]\d{7,8}$/.test(values.recipientPhone.replace(/\D/g, ''))) return '휴대폰 번호를 010-1234-5678 형식으로 입력해 주세요.'
  if (values.address.trim().length < 5) return '주소를 5자 이상 입력해 주세요.'
  return ''
}
