// 마이 페이지 배송지 관리: 주소록 목록, 추가·수정·삭제, 기본 배송지 지정(최대 10개)

import { useEffect, useState } from 'react'
import { createAddress, deleteAddress, getAddresses, setDefaultAddress, updateAddress } from '../../api/addresses.js'
import AddressFields from '../../components/user/address-fields.jsx'
import { EMPTY_ADDRESS, validateAddress } from '../../config/address.js'
import Modal from '../../components/common/modal.jsx'

const EMPTY_FORM = { label: '', ...EMPTY_ADDRESS, isDefault: false }

// 서버 응답의 주소를 폼 값으로 변환
function toForm(address) {
  return {
    label: address.label,
    recipientName: address.recipient_name,
    recipientPhone: address.recipient_phone,
    postcode: address.postcode,
    address: address.address,
    addressDetail: address.address_detail,
    isDefault: address.is_default,
  }
}

// 배송지 목록과 인라인 추가·수정 폼
function AddressBook() {
  const [data, setData] = useState({ addresses: [], max_addresses: 10 })
  const [isLoading, setIsLoading] = useState(true)
  const [editingId, setEditingId] = useState(null) // null=폼 닫힘, 'new'=추가, 숫자=수정 중인 배송지
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  useEffect(() => {
    let isMounted = true
    getAddresses()
      .then((result) => isMounted && setData(result))
      .catch((requestError) => isMounted && setError(requestError.message))
      .finally(() => isMounted && setIsLoading(false))
    return () => {
      isMounted = false
    }
  }, [])

  const isFull = data.addresses.length >= data.max_addresses

  const openForm = (address) => {
    setForm(address ? toForm(address) : { ...EMPTY_FORM, isDefault: data.addresses.length === 0 })
    setEditingId(address ? address.id : 'new')
    setError('')
  }

  const closeForm = () => {
    setEditingId(null)
    setError('')
  }

  const changeField = (name, value) => setForm((current) => ({ ...current, [name]: value }))

  // 추가 또는 수정 저장
  async function save(event) {
    event.preventDefault()
    const validationMessage = form.label.trim() ? validateAddress(form) : '배송지 명칭을 입력해 주세요. (예: 집, 회사)'
    if (validationMessage) {
      setError(validationMessage)
      return
    }
    setIsSaving(true)
    setError('')
    try {
      setData(editingId === 'new' ? await createAddress(form) : await updateAddress(editingId, form))
      setEditingId(null)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSaving(false)
    }
  }

  async function makeDefault(addressId) {
    setError('')
    try {
      setData(await setDefaultAddress(addressId))
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function confirmDelete() {
    const target = deleteTarget
    setDeleteTarget(null)
    try {
      setData(await deleteAddress(target.id))
      if (editingId === target.id) setEditingId(null)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <section className="my-page-card address-book" aria-labelledby="address-book-title">
      <div className="my-page-card__heading">
        <div>
          <p>ADDRESS</p>
          <h2 id="address-book-title">배송지 관리 <span className="address-book__count">{data.addresses.length}/{data.max_addresses}</span></h2>
        </div>
        {editingId === null && (
          <div className="profile-actions">
            <button type="button" disabled={isFull} title={isFull ? '배송지는 최대 10개까지 저장할 수 있어요' : undefined} onClick={() => openForm(null)}>배송지 추가</button>
          </div>
        )}
      </div>

      {error && editingId === null && <p className="profile-form__error" role="alert">{error}</p>}

      {editingId !== null && (
        <form className="profile-form address-book__form" onSubmit={save} noValidate>
          <label><span>배송지 명칭</span><input name="label" value={form.label} maxLength={20} placeholder="예: 집, 회사" onChange={(event) => changeField('label', event.target.value)} /></label>
          <AddressFields values={form} onChange={changeField} />
          <label className="address-book__default">
            <input type="checkbox" checked={form.isDefault} disabled={editingId !== 'new' && form.isDefault} onChange={(event) => changeField('isDefault', event.target.checked)} />
            <span>기본 배송지로 설정</span>
          </label>
          {error && <p className="profile-form__error" role="alert">{error}</p>}
          <div className="profile-form__actions">
            <button type="button" onClick={closeForm}>취소</button>
            <button className="is-primary" type="submit" disabled={isSaving}>{isSaving ? '저장 중...' : '저장'}</button>
          </div>
        </form>
      )}

      {isLoading ? (
        <p className="my-orders__note" role="status">배송지를 불러오고 있습니다.</p>
      ) : data.addresses.length === 0 && editingId === null ? (
        <div className="my-empty">
          <strong>저장된 배송지가 없어요</strong>
          <span>배송지를 추가하면 주문서에서 바로 불러올 수 있어요.</span>
        </div>
      ) : (
        <ul className="address-book__list">
          {data.addresses.map((address) => (
            <li key={address.id} className={address.is_default ? 'is-default' : ''}>
              <div className="address-book__head">
                <strong>{address.label}</strong>
                {address.is_default && <span className="address-book__badge">기본 배송지</span>}
              </div>
              <p>
                {address.recipient_name} · {address.recipient_phone}<br />
                {address.postcode ? `[${address.postcode}] ` : ''}{address.address} {address.address_detail}
              </p>
              <div className="address-book__actions">
                {!address.is_default && <button type="button" onClick={() => makeDefault(address.id)}>기본 배송지로 설정</button>}
                <button type="button" onClick={() => openForm(address)}>수정</button>
                <button type="button" onClick={() => setDeleteTarget(address)}>삭제</button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal
        isOpen={deleteTarget !== null}
        message={deleteTarget ? `'${deleteTarget.label}' 배송지를 삭제할까요?${deleteTarget.is_default && data.addresses.length > 1 ? ' 기본 배송지를 삭제하면 가장 최근에 추가한 배송지가 기본 배송지가 됩니다.' : ''}` : ''}
        confirmLabel="삭제"
        cancelLabel="취소"
        tone="danger"
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
      />
    </section>
  )
}

export default AddressBook
