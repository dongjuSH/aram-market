// 배송지 입력 칸(받는 분·휴대폰·우편번호·주소·상세주소): 주소록 관리와 주문서 새 배송지가 함께 사용

import { useRef, useState } from 'react'
import PostcodeSearchModal from './postcode-search-modal.jsx'

// 입력값은 부모가 들고 있고, 칸이 바뀔 때마다 onChange(name, value) 호출
// 우편번호·기본 주소는 주소 검색으로만 채우고 상세 주소만 직접 입력
function AddressFields({ values, onChange }) {
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const searchButtonRef = useRef(null)
  const detailRef = useRef(null)
  const handleChange = (event) => onChange(event.target.name, event.target.value)

  // 주소를 고르면 우편번호·주소를 채우고 상세 주소 칸으로 이동
  const selectAddress = ({ postcode, address }) => {
    onChange('postcode', postcode)
    onChange('address', address)
    setIsSearchOpen(false)
    requestAnimationFrame(() => (values.noAddressDetail ? searchButtonRef.current : detailRef.current)?.focus())
  }

  const closeSearch = () => {
    setIsSearchOpen(false)
    searchButtonRef.current?.focus()
  }

  // 상세 주소 없음을 고르면 입력해 둔 상세 주소를 비움
  const toggleNoDetail = (event) => {
    onChange('noAddressDetail', event.target.checked)
    if (event.target.checked) onChange('addressDetail', '')
  }

  return (
    <>
      <label>
        <span>받는 분</span>
        <input name="recipientName" value={values.recipientName} maxLength={30} autoComplete="name" onChange={handleChange} />
      </label>
      <label>
        <span>휴대폰 번호</span>
        <input name="recipientPhone" value={values.recipientPhone} maxLength={20} inputMode="tel" autoComplete="tel" placeholder="010-1234-5678" onChange={handleChange} />
      </label>
      <div className="address-search">
        <label>
          <span>우편번호</span>
          <input name="postcode" value={values.postcode} readOnly placeholder="주소 검색으로 입력" onClick={() => setIsSearchOpen(true)} />
        </label>
        <button ref={searchButtonRef} type="button" onClick={() => setIsSearchOpen(true)}>
          {values.postcode ? '주소 다시 검색' : '주소 검색'}
        </button>
      </div>
      <label>
        <span>주소</span>
        <input name="address" value={values.address} readOnly placeholder="주소 검색으로 입력" onClick={() => setIsSearchOpen(true)} />
      </label>
      <label>
        <span>상세 주소</span>
        <input
          ref={detailRef}
          name="addressDetail"
          value={values.addressDetail}
          maxLength={100}
          placeholder={values.noAddressDetail ? '상세 주소 없음' : '동·호수 등 나머지 주소'}
          disabled={Boolean(values.noAddressDetail)}
          onChange={handleChange}
        />
      </label>
      <label className="address-search__no-detail">
        <input type="checkbox" checked={Boolean(values.noAddressDetail)} onChange={toggleNoDetail} />
        <span>상세 주소 없음 (단독주택 등)</span>
      </label>
      {isSearchOpen && <PostcodeSearchModal onClose={closeSearch} onSelect={selectAddress} />}
    </>
  )
}

export default AddressFields
