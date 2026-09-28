// 단일 관리자 로그인과 세션 확인 API

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

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
  if (typeof payload?.detail === 'string') return { code: 'REQUEST_FAILED', message: payload.detail }
  if (payload?.detail?.message) {
    return { ...payload.detail, code: payload.detail.code || 'REQUEST_FAILED', message: payload.detail.message }
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
export async function request(path, { method = 'POST', body, token, keepalive = false } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
      keepalive,
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

// 고정 관리자 아이디와 비밀번호 로그인 요청
export function signIn({ username, password }) {
  return request('/api/admins/signin', { body: { username, password } })
}

// 저장된 관리자 접근 토큰 검증
export function getCurrentUser() {
  return request('/api/admins/me', {
    method: 'GET',
    token: sessionStorage.getItem('adminAccessToken'),
  })
}
