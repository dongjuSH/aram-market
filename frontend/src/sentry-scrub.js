// Sentry 이벤트에 들어갈 수 있는 이메일·토큰·결제키와 URL 쿼리를 전송 직전에 제거

const EMAIL_PATTERN = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g
const TOKEN_PATTERN = /eyJ[\w-]+\.[\w-]+\.[\w-]+|\b[A-Za-z0-9_-]{32,}\b/g
const REMOVED_HEADERS = new Set(['referer', 'cookie', 'authorization', 'x-forwarded-for', 'x-real-ip'])
const TOP_LEVEL_SENTRY_IDS = new Set(['event_id', 'release', 'dist'])
const TRACE_CONTEXT_IDS = new Set(['trace_id', 'span_id', 'parent_span_id'])

export function scrubText(value) {
  if (typeof value !== 'string') return value
  return value.replace(EMAIL_PATTERN, '[Filtered email]').replace(TOKEN_PATTERN, '[Filtered]')
}

export function stripQuery(url) {
  if (typeof url !== 'string') return url
  return url.split(/[?#]/)[0]
}

// 같은 키 이름의 임의 사용자 데이터가 정리를 우회하지 않도록 Sentry 스키마의 실제 식별자 경로만 보존한다.
function isSentryIdentifier(path, key) {
  if (path.length === 0) return TOP_LEVEL_SENTRY_IDS.has(key)
  if (path.length === 2 && path[0] === 'contexts' && path[1] === 'trace') return TRACE_CONTEXT_IDS.has(key)
  if (path[0] === 'debug_meta' && key === 'debug_id') return true
  if (path.length === 2 && path[0] === 'contexts' && path[1] === 'session' && key === 'sid') return true
  return false
}

function scrubValue(value, path = []) {
  if (typeof value === 'string') return scrubText(value)
  if (Array.isArray(value)) return value.map((item, index) => scrubValue(item, [...path, index]))
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, isSentryIdentifier(path, key) ? item : scrubValue(item, [...path, key])]),
  )
}

export function scrubEvent(event) {
  if (event.request) {
    event.request.url = stripQuery(event.request.url)
    delete event.request.query_string
    delete event.request.cookies
    delete event.request.data
    if (event.request.headers) {
      event.request.headers = Object.fromEntries(
        Object.entries(event.request.headers).filter(([key]) => !REMOVED_HEADERS.has(key.toLowerCase())),
      )
    }
  }
  const breadcrumbs = Array.isArray(event.breadcrumbs) ? event.breadcrumbs : event.breadcrumbs?.values
  for (const breadcrumb of breadcrumbs || []) {
    if (!breadcrumb.data) continue
    for (const key of ['url', 'from', 'to']) {
      if (key in breadcrumb.data) breadcrumb.data[key] = stripQuery(breadcrumb.data[key])
    }
  }
  return scrubValue(event)
}

export function beforeSend(event, hint) {
  const error = hint?.originalException
  if (error?.name === 'ApiError') {
    if (error.code === 'NETWORK_ERROR' || (error.status > 0 && error.status < 500)) return null
    event.tags = { ...event.tags, api_status: String(error.status), api_code: error.code }
    event.fingerprint = ['api-error', error.code, String(error.status)]
  }
  return scrubEvent(event)
}

export function beforeBreadcrumb(breadcrumb) {
  const data = breadcrumb.data
  if (data) {
    for (const key of ['url', 'from', 'to']) {
      if (key in data) data[key] = stripQuery(data[key])
    }
  }
  return scrubValue(breadcrumb)
}
