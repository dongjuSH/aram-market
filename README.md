# 🛒 아람 마켓 (Aram Market)

React와 FastAPI로 구현한 생활용품 쇼핑몰입니다.  
고객의 상품 탐색부터 결제·배송·환불까지의 구매 흐름과, 상품·주문·문의를 관리하는 운영자 기능을 하나의 풀스택 프로젝트로 구성했습니다.

**서비스** https://aram-market.duckdns.org

> 포트폴리오용 서비스이며, 결제는 토스페이먼츠 테스트 환경에서만 작동합니다.

## 주요 기능

- **상품** — 목록·상세 조회, 검색, 관련 상품, 재고·품절 표시
- **회원** — 이메일 인증 회원가입, 로그인, 아이디 찾기, 비밀번호 재설정, 회원 탈퇴·복구
- **쇼핑** — 장바구니, 찜 목록, 배송지 주소록, 주문서
- **주문·결제** — 토스페이먼츠 테스트 결제, 주문 내역, 배송 상태, 취소·환불
- **고객 참여** — 구매 후기, 상품 문의, 비밀글과 관리자 답변
- **관리자** — TOTP 2단계 인증, 상품 CRUD·재고, 주문·배송·환불, 문의 관리

## 기술 스택

| 구분 | 기술 |
|---|---|
| Frontend | React 19, Vite 8, JavaScript, Tiptap |
| Backend | FastAPI, Python 3.14, SQLAlchemy, asyncpg |
| DB · Storage | Supabase PostgreSQL, Supabase Storage |
| Auth · Payment | JWT(HttpOnly Cookie), TOTP, Toss Payments |
| Infra | Oracle Cloud, Nginx, systemd, DuckDNS, Let's Encrypt |
| Monitoring | Sentry |

## 구현 포인트

- React에서 DB로 직접 접근하지 않고 `React → FastAPI → Supabase` 구조로 인증·권한·데이터 규칙을 백엔드에서 관리합니다.
- 고객·관리자 토큰의 용도를 분리하고, 접근·리프레시 토큰 회전과 재사용 탐지를 적용했습니다.
- 결제 승인·환불과 재고 차감·복구 사이의 실패·중복 요청을 고려해 주문 상태를 관리합니다.
- 상품은 소프트 삭제·복원 방식을 사용하고, 변경 감사 로그와 Storage 임시 이미지 정리 주기를 두었습니다.
- 단일 도메인에서 Nginx가 정적 프런트엔드를 제공하고 `/api` 요청을 FastAPI로 프록시합니다.

## 폴더 구조

```text
backend/   FastAPI API, 도메인 로직, DB 마이그레이션·검수 스크립트
frontend/  React 고객용 쇼핑몰·관리자 화면
deploy/    Nginx·systemd 설정과 Oracle Cloud 배포 기록
```

## 로컬 실행

Python 3.14와 Node.js 24가 필요합니다. 환경변수 파일은 보안을 위해 저장소에 포함하지 않습니다.

- `backend/.env`: `DATABASE_URL`, `AUTH_SECRET_KEY`, Supabase Storage, SMTP, Toss Payments 서버 키 등
- `frontend/.env.local`: `VITE_ADMIN_BASE_PATH`, `VITE_TOSS_CLIENT_KEY` 등

실제 비밀값은 절대 커밋하지 않습니다.

```powershell
# 백엔드
cd backend
uv venv --python 3.14 .venv
uv pip install --python .venv -r requirements.txt
$env:PYTHONPATH=(Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m uvicorn main:app --reload

# 프런트엔드 (별도 터미널)
cd frontend
npm ci
npm run dev
```

## 검증

```powershell
# 백엔드
cd backend
$env:PYTHONPATH=(Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q main.py src scripts

# 프런트엔드
cd frontend
npm run lint
npm test
npm run build
```

운영 배포 구성과 재배포 절차는 [deploy/README.md](deploy/README.md)를 참고하세요.
