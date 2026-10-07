// React 변환 기반 Vite 개발·빌드 설정

import { sentryVitePlugin } from '@sentry/vite-plugin'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 셸 환경변수에 토큰이 있을 때만 소스맵을 만들어 Sentry에 올리고 dist에서는 지움(토큰은 VITE_ 접두사 금지: 번들에 박힘)
const sentryAuthToken = process.env.SENTRY_AUTH_TOKEN

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    sentryAuthToken && sentryVitePlugin({
      org: 'my-portfolio-bg',
      project: 'aram-market-web',
      authToken: sentryAuthToken,
      telemetry: false,
      sourcemaps: { filesToDeleteAfterUpload: ['./dist/**/*.map'] },
    }),
  ],
  build: {
    sourcemap: sentryAuthToken ? 'hidden' : false, // hidden: 번들에 소스맵 주소를 남기지 않음
  },
  server: {
    // 로그인 쿠키가 같은 출처(localhost:5173)로 저장되도록 개발 서버가 API 요청을 백엔드로 전달
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
