// 고객·관리자 API가 함께 쓰는 JSON 요청, 오류 형식 통일, 접근 토큰 만료 시 자동 재발급 클라이언트

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '') // 기본은 같은 출처 /api(개발 서버는 Vite 프록시)
const EXPIRED_ACCESS_CODES = new Set(['MISSING_ACCESS_TOKEN', 'INVALID_ACCESS_TOKEN'])

// 서버 오류 코드·상태·추가 데이터를 보존하는 프런트 전용 오류
class ApiError extends Error {
  constructor(message, code = 'UNKNOWN_ERROR', status = 0, data = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.data = data
  }
}

// 서버 오류(RFC 9457 Problem Details)를 프런트 오류 형식으로 통일: detail은 화면용 안내문, code는 분기용 코드
function normalizeError(payload, fallback) {
  if (typeof payload?.code === 'string' && typeof payload?.detail === 'string') {
    return { ...payload, message: payload.detail }
  }
  return { code: 'REQUEST_FAILED', message: payload?.detail || payload?.message || fallback }
}

// 재발급 경로와 로그인 표식 확인 방법만 다른 고객·관리자 요청 함수를 생성
export function createApiClient({ refreshPath, hasSession, onSessionEnd }) {
  let refreshPromise = null // 동시에 여러 요청이 만료돼도 재발급은 한 번만 수행

  // 리프레시 쿠키로 접근 토큰 재발급(성공 true, 세션이 끝났으면 false, 일시 장애·요청 제한이면 null)
  function refreshSession() {
    refreshPromise ??= request(refreshPath, { retryOnExpired: false })
      .then(() => true)
      .catch((error) => {
        // 다른 탭이 방금 재발급을 끝낸 경우 새 쿠키가 이미 있으므로 성공으로 취급
        if (error.code === 'REFRESH_IN_PROGRESS') return true
        return error.status === 401 ? false : null // 429·네트워크·서버 오류로는 로그인 표식을 지우지 않음
      })
      .finally(() => {
        refreshPromise = null
      })
    return refreshPromise
  }

  // JSON 요청·네트워크 장애·HTTP 오류 변환 공통 처리(접근 토큰 만료 시 재발급 후 1회 재시도)
  async function request(path, { method = 'POST', body, keepalive = false, retryOnExpired = true } = {}) {
    let response
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        credentials: 'include', // HttpOnly 인증 쿠키 자동 전송
        headers: { 'Content-Type': 'application/json' },
        ...(body ? { body: JSON.stringify(body) } : {}),
        keepalive,
      })
    } catch {
      throw new ApiError('서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.', 'NETWORK_ERROR')
    }

    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      const error = normalizeError(payload, '요청을 처리하지 못했습니다.')
      if (retryOnExpired && response.status === 401 && EXPIRED_ACCESS_CODES.has(error.code) && hasSession()) {
        const refreshed = await refreshSession()
        if (refreshed) return request(path, { method, body, keepalive, retryOnExpired: false })
        if (refreshed === false) onSessionEnd?.() // 리프레시까지 만료되어 로그인 표식도 정리
      }
      throw new ApiError(error.message, error.code, response.status, error)
    }
    return payload
  }

  return request
}
