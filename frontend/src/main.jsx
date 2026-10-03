// React 애플리케이션과 브라우저 루트 요소 연결(Sentry 초기화를 가장 먼저 불러옴)

import { Sentry } from './instrument.js'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import CrashFallback from './components/common/crash-fallback.jsx'

createRoot(document.getElementById('root'), {
  // React 19: ErrorBoundary 밖에서 잡히지 않은 오류도 Sentry로 전송(ErrorBoundary 안의 오류는 아래 경계가 전송)
  onUncaughtError: Sentry.reactErrorHandler(),
}).render(
  <StrictMode>
    <Sentry.ErrorBoundary fallback={<CrashFallback />}>
      <App />
    </Sentry.ErrorBoundary>
  </StrictMode>,
)
