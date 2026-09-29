// 고객 회원가입·인증·계정 복구·탈퇴 API

import { createApiClient } from './http.js'

const USER_STORAGE_KEY = 'userCurrentUser' // 토큰이 아닌 화면 표시용 로그인 상태 표식
export const USER_AUTH_CHANGE_EVENT = 'user-auth-change' // 같은 탭에서 로그인·로그아웃 표식이 바뀌었음을 알리는 이벤트

// 다른 탭에서도 로그인 상태를 표시할 수 있도록 비밀 값이 없는 회원 표식 조회
export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_STORAGE_KEY) || 'null')
  } catch {
    return null
  }
}

// 로그인·정보 갱신 후 화면 표시용 회원 정보 저장
export function storeUser(user) {
  try {
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify({ id: user.id, nickname: user.nickname }))
  } catch {
    // 저장소 사용 불가 시에도 쿠키 인증은 유지됨
  }
  window.dispatchEvent(new Event(USER_AUTH_CHANGE_EVENT))
}

// 화면 표시용 로그인 표식 제거
export function clearStoredUser() {
  try {
    localStorage.removeItem(USER_STORAGE_KEY)
  } catch {
    // 저장소 사용 불가 시 무시
  }
  window.dispatchEvent(new Event(USER_AUTH_CHANGE_EVENT))
}

export const request = createApiClient({
  refreshPath: '/api/users/token/refresh',
  hasSession: () => Boolean(getStoredUser()),
  onSessionEnd: () => clearStoredUser(),
})

// 아이디 및 비밀번호 로그인 요청
export function signIn({ username, password }) {
  return request('/api/users/signin', {
    body: { username, password },
  })
}

// 회원정보 및 약관 동의값 기반 가입 요청
export function signUp(form) {
  return request('/api/users/signup', {
    body: form,
  })
}

// 계정 존재 여부를 노출하지 않는 아이디 안내 요청
export function findUsername({ email }) {
  return request('/api/users/find-username', { body: { email } })
}

// 아이디·이메일 확인 후 비밀번호 재설정 메일 요청
export function requestPasswordReset({ username, email }) {
  return request('/api/users/password-reset/request', { body: { username, email } })
}

// 메일 단기 토큰 및 새 비밀번호 전달
export function resetPassword({ token, newPassword }) {
  return request('/api/users/password-reset/confirm', {
    body: { token, new_password: newPassword },
  })
}

// 로그인 사용자의 현재 비밀번호 확인 후 즉시 비밀번호 변경
export function changePassword({ currentPassword, newPassword }) {
  return request('/api/users/me/password', {
    method: 'PUT',
    body: {
      current_password: currentPassword,
      new_password: newPassword,
    },
  })
}

// 인증 쿠키 검증 및 현재 로그인 사용자 정보 조회
export function getCurrentUser() {
  return request('/api/users/me', {
    method: 'GET',
  })
}

// 로그인 사용자의 선택 마케팅 수신 동의 상태 저장
export function updateMarketingConsent(marketingConsent) {
  return request('/api/users/me/marketing-consent', {
    method: 'PUT',
    body: { marketing_consent: marketingConsent },
  })
}

// 탈퇴 유예 계정 복구 토큰 기반 탈퇴 취소
export function cancelWithdrawal(recoveryToken) {
  return request('/api/users/withdrawal/cancel', {
    body: { recovery_token: recoveryToken },
  })
}

// 로그인 계정을 탈퇴 대기 상태로 전환
export function deleteAccount({ password }) {
  return request('/api/users/me', {
    method: 'DELETE',
    body: {
      password,
      confirmation: '회원 탈퇴',
    },
  })
}

// 서버에서 인증 쿠키를 삭제하고 화면 표시용 로그인 표식 제거
export async function signOut() {
  clearStoredUser()
  try {
    await request('/api/users/signout')
  } catch {
    // 네트워크 실패여도 표식은 이미 제거됨
  }
}

// 회원가입 화면에 표시할 현재 시행 약관과 버전 조회
export function getPolicies() {
  return request('/api/users/policies', { method: 'GET' })
}

// 이메일 인증 링크 토큰 확인
export function verifyEmail(token) {
  return request('/api/users/email-verification/confirm', { body: { token } })
}

// 미인증 계정의 인증 메일 재발송 요청
export function resendVerificationEmail(email) {
  return request('/api/users/email-verification/resend', { body: { email } })
}

// 잠금 해제 메일 화면에서 버튼을 눌렀을 때 토큰 확인(POST)
export function unlockAccount(token) {
  return request('/api/users/unlock', { body: { token } })
}
