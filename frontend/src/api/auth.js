// 단일 관리자 로그인과 세션 확인 API

import { createApiClient } from './http.js'

export const request = createApiClient({
  refreshPath: '/api/admins/token/refresh',
  hasSession: () => Boolean(sessionStorage.getItem('adminCurrentUser')),
})

// 고정 관리자 아이디와 비밀번호 로그인 요청
export function signIn({ username, password }) {
  return request('/api/admins/signin', { body: { username, password } })
}

// 인증 쿠키 기반 현재 관리자 확인
export function getCurrentUser() {
  return request('/api/admins/me', { method: 'GET' })
}

// 서버에서 관리자 인증 쿠키를 삭제하고 화면 표시용 정보 제거
export async function signOut() {
  sessionStorage.removeItem('adminCurrentUser')
  try {
    await request('/api/admins/signout')
  } catch {
    // 네트워크 실패여도 화면 정보는 이미 제거됨
  }
}
