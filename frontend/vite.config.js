// React 변환 기반 Vite 개발·빌드 설정

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 로그인 쿠키가 같은 출처(localhost:5173)로 저장되도록 개발 서버가 API 요청을 백엔드로 전달
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
