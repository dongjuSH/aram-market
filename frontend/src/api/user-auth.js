// 추후 사용자 페이지에서 재사용할 가입·인증·계정 복구·탈퇴 API

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '') // IPv4 로컬 백엔드 주소

// 서버 오류 코드·상태·추가 데이터를 보존하는 프런트 전용 오류
export class ApiError extends Error {
  constructor(message, code = 'UNKNOWN_ERROR', status = 0, data = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.data = data
  }
}

// FastAPI 문자열·구조화·검증 오류의 프런트 오류 형식 통일
function normalizeError(payload, fallback) {
  if (typeof payload?.detail === 'string') {
    return { code: 'REQUEST_FAILED', message: payload.detail }
  }

  if (payload?.detail?.message) {
    return {
      ...payload.detail,
      code: payload.detail.code || 'REQUEST_FAILED',
      message: payload.detail.message,
    }
  }

  if (Array.isArray(payload?.detail)) {
    const message = payload.detail
      .map((error) => error.msg?.replace(/^Value error, /, ''))
      .filter(Boolean)
      .join('\n')
    return { code: 'VALIDATION_ERROR', message: message || fallback }
  }

  return { code: 'REQUEST_FAILED', message: payload?.message || fallback }
}

// JSON 요청·네트워크 장애·HTTP 오류 변환 공통 처리
export async function request(path, { method = 'POST', body, token } = {}) {
  let response

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
  } catch {
    throw new ApiError('서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.', 'NETWORK_ERROR')
  }

  const payload = await response.json().catch(() => ({}))

  if (!response.ok) {
    const error = normalizeError(payload, '요청을 처리하지 못했습니다.')
    throw new ApiError(error.message, error.code, response.status, error)
  }

  return payload
}

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
    token: sessionStorage.getItem('userAccessToken'),
    body: {
      current_password: currentPassword,
      new_password: newPassword,
    },
  })
}

// 저장된 접근 토큰 검증 및 현재 로그인 사용자 정보 조회
export function getCurrentUser() {
  return request('/api/users/me', {
    method: 'GET',
    token: sessionStorage.getItem('userAccessToken'),
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
    token: sessionStorage.getItem('userAccessToken'),
    body: {
      password,
      confirmation: '회원 탈퇴',
    },
  })
}
