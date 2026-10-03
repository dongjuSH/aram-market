// Sentry 오류 수집 초기화: 화면을 깨뜨리는 오류와 우리 코드의 예외만 보내고, 이미 화면에 안내한 오류·외부 스크립트 오류는 거름

import * as Sentry from '@sentry/react'
import { beforeBreadcrumb, beforeSend } from './sentry-scrub.js'

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN // 비우면 수집하지 않음

// 브라우저·네트워크 환경 때문에 생기는, 고칠 수 없는 오류 문구(기술 블로그 방식: 의미 없는 오류는 전송 전에 차단)
const IGNORED_ERRORS = [
  'Failed to fetch dynamically imported module', // 새 배포 직후 옛 화면에서 지난 파일을 부를 때(새로고침으로 해결)
  'Importing a module script failed',
  'ResizeObserver loop', // 브라우저 레이아웃 경고(실제 오류 아님)
  'Load failed', // Safari 네트워크 끊김
  'Failed to fetch',
  'NetworkError when attempting to fetch resource',
]

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.PROD ? 'production' : 'development',
    release: import.meta.env.VITE_SENTRY_RELEASE || undefined,
    sendDefaultPii: false, // IP·쿠키·사용자 정보 미전송
    tracesSampleRate: 0, // 성능 추적·세션 녹화 미사용(무료 한도 절약)
    allowUrls: [window.location.origin], // 브라우저 확장 프로그램·외부 스크립트에서 난 오류 제외
    ignoreErrors: IGNORED_ERRORS,
    beforeSend,
    beforeBreadcrumb,
  })
}

export { Sentry }
