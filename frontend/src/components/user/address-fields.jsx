// 배송지 입력 칸(받는 분·휴대폰·우편번호·주소·상세주소): 주소록 관리와 주문서 새 배송지가 함께 사용

// 입력값은 부모가 들고 있고, 칸이 바뀔 때마다 onChange(name, value) 호출
function AddressFields({ values, onChange }) {
  const handleChange = (event) => onChange(event.target.name, event.target.value)
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
      <label>
        <span>우편번호 (선택)</span>
        <input name="postcode" value={values.postcode} maxLength={10} autoComplete="postal-code" onChange={handleChange} />
      </label>
      <label>
        <span>주소</span>
        <input name="address" value={values.address} maxLength={200} autoComplete="street-address" onChange={handleChange} />
      </label>
      <label>
        <span>상세 주소 (선택)</span>
        <input name="addressDetail" value={values.addressDetail} maxLength={100} onChange={handleChange} />
      </label>
    </>
  )
}

export default AddressFields
