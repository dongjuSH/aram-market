import assert from 'node:assert/strict'
import test from 'node:test'

import { beforeBreadcrumb, beforeSend } from './sentry-scrub.js'

test('Sentry 이벤트 전체에서 URL 쿼리와 이메일·토큰을 제거한다', () => {
  const email = 'victim@example.com'
  const token = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlc2lnbmF0dXJl'
  const paymentKey = 'tgen_20261002ABCDEFGHIJKLMNOPQRSTUVWX'
  const event = {
    message: `failed ${email}`,
    exception: { values: [{ value: `token=${token}` }] },
    logentry: { formatted: `payment=${paymentKey}` },
    request: {
      url: `https://shop.example/payment?paymentKey=${paymentKey}`,
      query_string: `paymentKey=${paymentKey}`,
      data: { email },
      cookies: `session=${token}`,
      headers: { Referer: `https://shop.example/reset?token=${token}`, Authorization: `Bearer ${token}`, Accept: 'application/json' },
    },
    breadcrumbs: { values: [{ message: `user=${email}`, data: { url: `https://shop.example/reset?token=${token}` } }] },
  }

  const cleaned = beforeSend(event, {})
  const serialized = JSON.stringify(cleaned)
  for (const secret of [email, token, paymentKey, 'query_string', 'Authorization', 'Referer']) {
    assert.equal(serialized.includes(secret), false, secret)
  }
  assert.equal(cleaned.request.url, 'https://shop.example/payment')
  assert.equal(cleaned.request.headers.Accept, 'application/json')
})

test('4xx ApiError는 보내지 않고 breadcrumb 문자열도 정리한다', () => {
  assert.equal(beforeSend({}, { originalException: { name: 'ApiError', code: 'INVALID', status: 400 } }), null)
  const breadcrumb = beforeBreadcrumb({ message: 'victim@example.com', data: { to: '/reset?token=secret' } })
  assert.equal(breadcrumb.message, '[Filtered email]')
  assert.equal(breadcrumb.data.to, '/reset')
})

test('Sentry 식별자(event_id·trace_id·release)는 토큰 규칙에 걸려도 지우지 않는다', () => {
  const event = {
    event_id: 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6',
    release: '861ccc89baacf2b96bd37c2ecd07a4a90f157c91',
    contexts: { trace: { trace_id: '0123456789abcdef0123456789abcdef', span_id: '0123456789abcdef' } },
    exception: { values: [{ value: 'token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlc2lnbmF0dXJl' }] },
  }
  const cleaned = beforeSend(structuredClone(event), {})
  assert.equal(cleaned.event_id, event.event_id)
  assert.equal(cleaned.release, event.release)
  assert.equal(cleaned.contexts.trace.trace_id, event.contexts.trace.trace_id)
  assert.equal(cleaned.exception.values[0].value, 'token=[Filtered]')
})

test('식별자와 같은 키 이름의 임의 중첩 데이터는 정리를 우회하지 않는다', () => {
  const token = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlc2lnbmF0dXJlc2ln'
  const cleaned = beforeSend({ extra: { sid: token, release: token, event_id: token }, contexts: { custom: { trace_id: token } } }, {})
  assert.equal(JSON.stringify(cleaned).includes(token), false)
})
