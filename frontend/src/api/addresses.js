// 로그인 고객의 배송지 주소록 API 호출

import { request } from './user-auth.js'

// 화면의 camelCase 배송지를 서버 형식으로 변환
function toBody({ label, recipientName, recipientPhone, postcode, address, addressDetail, noAddressDetail = false, isDefault = false }) {
  return {
    label,
    recipient_name: recipientName,
    recipient_phone: recipientPhone,
    postcode,
    address,
    address_detail: addressDetail,
    no_address_detail: noAddressDetail,
    is_default: isDefault,
  }
}

// 내 배송지 목록(기본 배송지 먼저)과 최대 개수
export function getAddresses() {
  return request('/api/users/me/addresses', { method: 'GET' })
}

export function createAddress(address) {
  return request('/api/users/me/addresses', { body: toBody(address) })
}

export function updateAddress(addressId, address) {
  return request(`/api/users/me/addresses/${addressId}`, { method: 'PUT', body: toBody(address) })
}

export function setDefaultAddress(addressId) {
  return request(`/api/users/me/addresses/${addressId}/default`, { method: 'PUT' })
}

export function deleteAddress(addressId) {
  return request(`/api/users/me/addresses/${addressId}`, { method: 'DELETE' })
}
