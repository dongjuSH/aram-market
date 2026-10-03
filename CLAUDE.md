# Product Management 개발 인수인계

## 이 문서의 목적

이 문서는 Claude Code가 현재 작업을 바로 이어가기 위한 기준 문서다. 작업을 시작할 때 전체를 먼저 읽고, 실제 코드와 충돌하면 추측하지 말고 코드·DB 읽기 결과를 기준으로 이 문서를 함께 갱신한다.

사용자는 React와 FastAPI의 동작을 직접 이해하면서 구현하는 것이 목표다. 요청하지 않은 전체 코드 생성이나 대규모 구조 변경은 피하고, 기존 코드 기준으로 원인과 개념을 먼저 설명한 뒤 필요한 범위만 수정한다. 새로운 폴더·계층·라이브러리는 실제 필요가 생겼을 때 먼저 제안한다.

## 지금 이어서 할 일 (2026-10-03 인계: 대여 노트북 → 개인 PC)

이전 작업은 대여 노트북(macOS)에서 했고, 그 노트북은 포맷 후 반납한다. 대화 기록과 Claude 기억 파일은 넘어오지 않으므로 이 문서가 유일한 인계 자료다. 사용자는 개인 PC(Windows로 예상, 확인 필요)에서 이어서 작업한다.

현재 상태:

- 배포 전 코드 작업·Claude↔Codex 교차 검수 완료, 마지막 커밋 `66dac65`(원격 `main` 푸시 완료) 이후 이 인계 문서만 갱신됨.
- DB 마이그레이션 001~030 모두 실제 Supabase 적용 완료. 관리자 2단계 인증은 노트북의 로컬 `AUTH_SECRET_KEY` 기준으로 등록돼 있음(운영 키로 바꾸면 재등록 필요).
- 다음 단계는 **배포**다. 호스팅·도메인·절차는 아래 '배포 계획' 절에 확정돼 있다.

개인 PC 첫 설정(사용자가 할 일 포함):

1. Git, Python 3.14, Node 24 설치 → `git clone https://github.com/dongjuSH/product-management.git`.
2. 노트북에서 옮겨 온 `backend/.env`, `frontend/.env.local`을 같은 위치에 둔다(Git·채팅·메신저로 옮기지 않는다. 비밀번호 관리자 보안 메모나 USB 사용). 값을 다시 받을 수 있는 것: `DATABASE_URL`·Supabase 키(Supabase 대시보드), `SENTRY_DSN`·`VITE_SENTRY_DSN`(Sentry 프로젝트 `aram-market-api`·`aram-market-web`의 Client Keys), 토스 테스트 키(토스 개발자센터). `VITE_ADMIN_BASE_PATH`는 노트북 값을 그대로 쓰거나 새로 정한다(문서·커밋에 남기지 않는다).
3. 백엔드: `cd backend` → `python -m venv .venv` → 가상환경 활성화 → `pip install -r requirements.txt` → **`pip install "fastapi[standard]"`**(로컬 `fastapi dev` 명령용 개발 도구라 `requirements.txt`에는 없다. 없으면 "To use the fastapi command, please install fastapi[standard]" 오류. 대신 `uvicorn main:app --reload --host 127.0.0.1`로 띄워도 된다).
4. 프런트: `cd frontend` → `npm ci` → `npm run dev`.
5. 확인: 아래 '검증 명령'의 백엔드 테스트·`npm test`·`npm run lint`·`npm run build`, 로컬 화면에서 로그인·상품 상세 동작.
6. 새 SSH 키는 **개인 PC에서 생성**한다(배포 서버 접속용, 개인키는 PC 밖으로 옮기지 않는다).

Claude가 지킬 사용자 선호(이전 기억 파일에서 옮김):

- 커밋·푸시는 사용자가 요청할 때만 한다. 커밋 요청에 푸시를 자동으로 붙이지 않는다.
- 관리자 화면은 노트북 이상 데스크톱 기준이며 모바일 대응은 하지 않는다.
- 쓰이지 않는 코드·CSS는 작업할 때마다 제거한다(재사용 가능성이 있으면 먼저 확인).
- 결제·인증·동시성 변경은 아래 '작업 원칙'의 검증 원칙 1~7을 따른다.
- **실제 배포 때 반드시 다시 안내할 것**: 운영(https)에서는 `ADMIN_MFA_REQUIRED`가 자동으로 켜지고 운영용 새 `AUTH_SECRET_KEY`로 기존 MFA 등록이 무효가 되므로, 배포 직후 관리자 로그인 전에 서버에서 `scripts/setup_admin_mfa.py`로 재등록해야 한다(안 하면 503 `ADMIN_MFA_NOT_CONFIGURED`로 관리자 로그인 불가).

## 배포 계획 (2026-10-03 확정, 아직 진행 전)

무료 조건(포트폴리오)에서 고른 구성. 근거로 확인한 공식 자료: Render 무료 웹 서비스는 2025-09부터 SMTP 25·465·587 차단(유료는 465·587 허용), Railway는 무료·Trial·Hobby에서 SMTP 차단(Pro부터 허용), Oracle Always Free는 포트 25만 기본 차단이며 Email Delivery 월 3,000통 무료.

| 항목 | 결정 |
|---|---|
| 서버 | Oracle Cloud Always Free, **홈 리전 오사카**(무료 VM은 홈 리전에서만 생성 가능). 사용자의 다른 프로젝트가 같은 계정에서 AMD 무료 VM 1대를 쓰고 있으므로 **새 VM을 따로** 만든다(무료 한도: AMD `VM.Standard.E2.1.Micro` 최대 2대·각 1GB 메모리, ARM A1 총 2코어·12GB, 디스크 총 200GB·VM당 최소 47GB). ARM이 용량 부족이면 AMD Micro + 스왑 2GB |
| OS·런타임 | Ubuntu 24.04, 시간대 Asia/Seoul, Python 3.14(uv로 설치), 서버에는 Node를 두지 않음 |
| 프런트 | 개인 PC에서 `npm run build`(운영 `VITE_*` 값으로) → `frontend/dist`만 서버로 업로드(1GB VM에서 빌드하면 메모리 부족 위험) |
| 백엔드 | systemd 서비스로 `uvicorn main:app --host 127.0.0.1 --port 8000`(작업 디렉터리 `backend`, 워커 1개, `Restart=always`). 8000은 외부에 열지 않음 |
| 웹 서버 | nginx 한 대가 같은 도메인에서 정적 파일(`dist`)과 `/api` 프록시를 함께 처리하고, 그 밖의 경로는 `index.html`로 돌려줌(SPA fallback). 외부 공개 포트는 80·443만(Oracle 보안 목록 + 서버 방화벽) |
| 도메인·HTTPS | DuckDNS 무료 서브도메인(공용 접미사 목록에 있어 Let's Encrypt 발급 한도 문제 없음) + certbot(Let's Encrypt, 자동 갱신) |
| 메일 | 기존 SMTP(587) 유지. 서버에서 587 연결이 막히면 Oracle Email Delivery로 전환 |
| DB·이미지 | 기존 Supabase 프로젝트 그대로(개발·운영 겸용, '실제 상용화 시 DB 분리' 절 참고) |
| 오류 수집 | Sentry 기존 프로젝트, 배포 후 두 프로젝트의 Inbound Filters에서 Localhost 필터 켜기 |

배포 순서:

1. (사용자) 개인 PC에서 SSH 키 생성 → Oracle 콘솔(오사카)에서 VM 생성(Ubuntu 24.04, 공인 IP, 공개키 등록). 생성 화면을 Claude에게 보여 주면 값을 안내한다.
2. (사용자) DuckDNS 서브도메인 생성 → VM 공인 IP 연결.
3. (함께) 서버 기본 설정: 패키지 업데이트, 스왑, 시간대, 방화벽(80·443), Python 3.14(uv)·백엔드 코드 배치·가상환경, systemd 서비스, nginx, certbot.
4. (함께) 서버에서 SMTP 587 연결 테스트 → SMTP 유지 또는 Email Delivery 전환.
5. (사용자) 서버 `backend/.env`에 운영 값 입력: 새 `AUTH_SECRET_KEY`(32자 이상), `FRONTEND_URL=https://<도메인>`, `TRUSTED_PROXY_IPS=127.0.0.1`(같은 서버 nginx), 나머지는 로컬과 같음. `.env` 권한 600. 운영에서는 `API_DOCS_ENABLED`·`AUTH_COOKIE_SECURE`·`ADMIN_MFA_REQUIRED`·`SENTRY_ENVIRONMENT`가 https 기준으로 자동 설정된다.
6. (함께) nginx에 보안 헤더(HSTS, `X-Content-Type-Options: nosniff`, `frame-ancestors`, `Referrer-Policy`)와 CSP(토스 `js.tosspayments.com`, 카카오 우편번호 `t1.kakaocdn.net`, Supabase Storage, Sentry `*.ingest.us.sentry.io` 허용, 처음엔 Report-Only로 확인 후 적용).
7. (사용자) **관리자 2단계 인증 재등록**: 서버에서 `PYTHONPATH=src .venv/bin/python scripts/setup_admin_mfa.py`(새 `AUTH_SECRET_KEY` 기준). 이전 복구 코드는 무효가 된다.
8. (함께) 배포 후 확인: `/docs`·`/redoc`·`/openapi.json` 404, `/api/health` 200, 인증 쿠키 `Secure`, 고객 로그인·관리자 2단계 로그인·토스 테스트 결제·메일 링크가 운영 도메인인지, 직접 주소 접속·새로고침(SPA fallback), 로그인 실패 제한이 실제 접속자 IP 기준인지, Sentry `production` 이벤트 수신.
9. (사용자) Sentry Localhost 필터 켜기, (선택) 소스맵 업로드(`@sentry/vite-plugin`, 조직 slug `my-portfolio-bg`, `SENTRY_AUTH_TOKEN`).

알려진 위험: Oracle 문서상 7일간 CPU(95백분위)·네트워크·메모리(A1만) 사용률이 모두 20% 미만이면 Always Free VM이 회수될 수 있다(유료 계정 예외 언급 없음). 서버 설정을 이 문서와 Git으로 재현 가능하게 유지하고, 데이터는 Supabase에 있으므로 VM이 사라져도 다시 만들면 된다. 배포 중 확정되는 nginx·systemd 설정은 저장소에 함께 기록한다(실제 도메인 외 비밀값 제외).

## 현재 기준 상태

2026-10-03 기준 구현 범위:

- 고객용 아람 마켓 상품 목록과 상품 상세 페이지
- 고객 회원가입(비밀번호 확인, 이메일 소유 인증, 약관 버전·동의 이력), 로그인(이전 화면 복귀), 아이디 찾기, 비밀번호 재설정, 마이페이지
- 고객·관리자 인증 토큰은 HttpOnly 쿠키로만 전달(JS·sessionStorage에 토큰 없음). 고객·관리자 모두 접근 토큰+리프레시 토큰(회전·재사용 탐지) 사용
- 고객 비밀번호 변경, 마케팅 수신 동의 변경, 7일 유예 회원 탈퇴·복구
- 고정 아이디 `admin` 한 개만 사용하는 관리자 로그인(TOTP 2단계 인증, Google Authenticator 등)
- 관리자 상품 목록·검색·등록·수정·소프트 삭제·복원
- 고객 장바구니(로그인 시 DB 저장), 찜 목록(`/wishlist`), 토스페이먼츠 테스트 결제(주문 생성·서버 승인·주문 내역)
- 상품 후기(배송완료된 구매 고객만)·문의(로그인 고객, 비밀글, 관리자 답변)
- 주문서(배송지 입력)·배송 상태(결제완료 → 상품준비중 → 배송중 → 배송완료, 관리자 변경)·마이 페이지 배송 현황
- 고객 헤더: 상단 회원가입·로그인(로그인 시 닉네임·로그아웃), 우측 찜 목록·장바구니·마이 페이지 아이콘(컬리 방식)
- 찜 목록 전용 페이지(`/wishlist`), 배송지 주소록(마이 페이지 관리·주문서 선택, 최대 10개), 마이 페이지 회원정보 수정·이메일 변경(메일 확인 후 반영), 상세 상단 개편(컬리·쿠팡형 정보 행)
- 관리자 화면: 상품 관리·주문 관리·문의 관리(헤더에 세 메뉴를 항상 표시, 현재 화면 메뉴는 강조·클릭 불가, 상품 등록·수정 화면에서는 '상품 관리'가 강조되지만 목록으로 이동 가능). 주문 관리의 다음 단계 버튼 문구는 `config/delivery.js`의 `action`
- Supabase PostgreSQL 및 Supabase Storage 연결
- 상품 변경 감사 로그와 이미지 임시 업로드 정리
- 계정 보안 보강: 로그인 상태 비밀번호 확인 실패 제한(회원당 15분 5회), 비밀번호 변경·재설정·이메일 변경·탈퇴 신청 보안 알림 메일, 이메일 변경 시 이전 재설정 링크 무효화, 잠금 해제 링크 1회용
- 결제 승인 누락 보정(결제키 선저장 + 정리 작업의 토스 결제 조회), 리프레시 토큰 동시 재발급 행 잠금, 상세 HTML 이미지는 자사 Storage 주소만 허용
- 운영 준비: API 문서 https 자동 차단, CORS `FRONTEND_URL` 한정, 플랫폼 환경변수 우선, `/api/health`, 실행 버전 고정(Python 3.14·Node 24·패키지 `==`), Supabase 트랜잭션 풀러(6543) 자동 대응, Sentry 오류 수집(백엔드·프런트)

실제 Supabase 상태:

- `admin_accounts`: 활성 `admin` 계정 1건, 2단계 인증 등록 완료(로컬 `AUTH_SECRET_KEY` 기준이라 운영 키로 바꾸면 배포 후 재등록, 2026-10-02 복구 코드 1개 사용 테스트로 9개 남음)
- `users`: 테스트 회원 5건(`testuser01~05`), `marketing_consent`·`email_verified_at`·`email_verification_sent_at` 컬럼 적용 완료(기존 회원은 인증 완료 처리). 예전 주소 컬럼(`postcode`·`address`·`address_detail`)과 이름·휴대폰(`name`·`phone`, 028)은 주소록으로 대체되어 제거됨
- `user_policy_consents`: 약관 종류·버전·동의 여부·시각 이력(기존 회원은 v1.0 이력 백필)
- `products`: 총 30건(활성 29건, 삭제 1건)이며 소프트 삭제 상품도 보존
- 마이그레이션 029로 `admin_accounts`에 2단계 인증 컬럼 4개 추가(적용 완료). 마이그레이션 017~026으로 추가된 테이블: `user_refresh_tokens`, `admin_refresh_tokens`, `rate_limit_events`, `cart_items`, `wishlist_items`, `orders`(배송 컬럼 포함), `order_items`, `product_reviews`, `product_inquiries`, `user_addresses` (모두 적용 완료, 검수 스크립트로 확인)
- 마이그레이션 030(주문의 실제 결제 승인 시도 시각 `orders.payment_attempted_at`과 인덱스)은 2026-10-03 실제 Supabase에 적용 완료(2회 실행 확인, 확인 스크립트 종료 코드 0). 당시 주문 7건은 모두 결제 완료라 시도 시각을 각자의 `paid_at`으로 채웠다.
- 상품 대표·상세 이미지는 모두 새 Storage 경로로 이전 완료
- `products.image_data`, 상품 관리자 ID, 감사 로그 관리자 ID 같은 중복 컬럼 제거 완료

자동 검증 기준:

- 백엔드 단위 테스트 134개 통과(`tests/test_api_routes.py`가 앱 조립·인증 필요 경로·ID 범위·헬스 체크·검색어 이스케이프를 DB 없이 확인)
- 프런트 Node 단위 테스트 6개 통과(`npm test`: Sentry 이벤트 민감정보 제거·정상 식별자 보존·같은 키 이름의 임의 데이터 정리, 결제 불확정 화면 상태)
- Python `compileall` 통과
- 프런트 `oxlint` 통과
- Vite 프로덕션 빌드 통과
- (배포 전 점검 때 추가 확인) `ruff`(F·E9·B·ASYNC, 백엔드 전체), `vulture`, `pip-audit`, `pip check`, `npm audit --omit=dev` 이상 없음

## 작업 원칙

- 파일명은 kebab-case, React 컴포넌트 함수명은 PascalCase를 사용한다. Vite 기본 `App.jsx`, `main.jsx`는 유지한다.
- 파일 첫 줄에는 역할을 설명하는 한 줄 주석을 둔다.
- 함수·클래스 설명은 선언 바로 위의 짧은 `#` 주석으로 작성한다.
- 사용자가 만든 변경을 임의로 되돌리거나 구조를 크게 바꾸지 않는다.
- 진단 요청은 원인과 근거만 제시하고, 수정 요청이 있을 때 구현한다.
- DB 스키마 변경은 SQL 마이그레이션과 적용 스크립트를 함께 추가하며 기존 데이터를 먼저 확인한다.
- `Base.metadata.create_all()`은 기존 테이블을 변경하지 않으므로 마이그레이션을 대신할 수 없다.
- 상품·계정 삭제는 현재 정책에 맞는 소프트 삭제 또는 유예 삭제를 사용하고 직접 영구 삭제하지 않는다.
- 새 라우터는 인증 쿠키 이름·접근 토큰 의존성을 `core/dependencies.py`(`require_user_token`·`require_admin_token`·`optional_user_token`)에서 가져오고, 구조화된 오류는 `core/errors.py`의 `api_error`로 만든다(라우터·서비스마다 복사해 쓰지 않는다). 공통 별·하트 아이콘은 `components/common/icons.jsx`를 쓴다.
- 더 이상 쓰이지 않는 코드·CSS는 작업할 때마다 제거한다(재사용 가능성이 있으면 삭제 전에 사용자에게 확인). 마이그레이션 이력과 관리·검수 스크립트는 삭제하지 않는다.
- 문서가 바뀌면 루트 `CLAUDE.md`만 갱신한다. 별도 README를 임의로 추가하지 않는다.
- 검증 원칙(2026-10-03, 교차 검수에서 20건 이상이 Claude 단독 검수를 통과했던 원인 분석 후 결정):
  1. 결제·인증·동시성 변경은 코딩 전에 외부 호출·커밋 지점마다 실패 시나리오(타임아웃, 깨진 응답, 4xx·409·429·5xx, 중복·동시 요청, 단계 사이 중단, 커밋 실패)를 표로 정리하고 각 칸에 처리 방법과 테스트를 대응시킨다.
  2. 외부 API의 오류 코드·상태값은 공식 문서로 확인하고 출처를 남긴다(기억에 의존하지 않는다).
  3. 응답 형식·오류 코드를 바꾸면 그것을 쓰는 프런트·스크립트·테스트를 검색해 같은 변경에서 함께 고친다.
  4. 버그 유형 하나를 고치면 같은 구조의 코드를 모두 찾아 "수정/해당 없음" 목록으로 보고한다.
  5. 수정마다 원래 버그와 인접 경우의 회귀 테스트를 추가하고 전체 검증을 다시 실행한다.
  6. 검증 결과는 실행한 명령·범위·결과·실행하지 못한 것을 함께 적는다(범위가 불분명한 "이상 없음" 금지).
  7. 결제·인증 변경은 작은 묶음으로 나누고 자체 검토를 거친 뒤 Codex 교차 검수를 받는다.

## 보안 및 Git 절대 규칙

다음 파일과 값은 절대 Git에 올리지 않는다.

- `backend/.env`, 루트 `.env`, 모든 `.env.local`
- DB 비밀번호와 실제 `DATABASE_URL`
- `AUTH_SECRET_KEY`, SMTP 앱 비밀번호
- `SUPABASE_SERVICE_ROLE_KEY`
- 관리자 비공개 URL인 실제 `VITE_ADMIN_BASE_PATH`
- `.venv`, `node_modules`, `dist`, `__pycache__`, `*.pyc`, 로그
- 관리자·사용자 실제 비밀번호와 접근 토큰

현재 `.gitignore`는 위 환경파일과 생성물을 제외한다. 업로드 전에는 반드시 다음을 확인한다.

```powershell
git status --short --untracked-files=all
git diff --check
git status --ignored --short
git ls-files | rg '(^|/)(\.env($|\.)|node_modules|dist|\.venv|__pycache__|.*\.pyc$|.*\.log$)'
```

커밋·푸시는 터미널 Git 명령으로 진행한다. `git reset --hard`, 강제 푸시, 사용자 변경 삭제는 명시적 요청 없이는 금지한다.

## 기술 구성

- 프런트엔드: React 19, Vite 8, JavaScript, CSS, Tiptap
- 백엔드: Python, FastAPI, SQLAlchemy Async, Pydantic
- DB: Supabase PostgreSQL
- 이미지: Supabase Storage 공개 `product-images` 버킷
- 인증: PBKDF2-SHA256 비밀번호 해시, 표준 JWT(HS256, PyJWT: `iss`·`aud`=토큰 용도·`sub`·`iat`·`exp`·`jti`, 알고리즘 서버 고정) 접근 토큰을 HttpOnly 쿠키(`user_access_token`, `admin_access_token`, Path=/api)로 전달. 리프레시 토큰 쿠키는 만료 시각이 없는 세션 쿠키라 브라우저를 닫으면 로그인이 풀린다(서버 쪽 최대 유지기간은 DB 만료로 유지). 리프레시 토큰은 무작위 불투명 값이며 고객은 `user_refresh_token`(Path=/api/users), 관리자는 `admin_refresh_token`(Path=/api/admins) 쿠키로만 전달하고 DB에는 SHA-256 해시만 저장
- 메일: SMTP, HTML·텍스트 멀티파트
- 메일 종류: 아이디 안내, 비밀번호 재설정, 계정 잠금 해제, 가입 이메일 인증, 이메일 변경 확인, 계정 보안 알림(`security_notice.html`: 비밀번호 변경·재설정, 이메일 변경(바뀌기 전 주소로, 새 주소는 일부 가림), 탈퇴 신청 시 발송. 발송 실패는 요청 결과에 영향 없음). SMTP 연결·인증(`scripts/check_smtp.py`)과 잠금 해제·가입 인증 메일의 실제 발송·링크 동작은 사용자가 기능 구현 시 직접 테스트해 정상 확인함
- 시간대: DB 요청과 프런트 표시 모두 `Asia/Seoul`
- 오류 응답: 모든 오류는 RFC 9457 Problem Details(`application/problem+json`)로 통일한다(`core/problems.py`). 필드: `type`(`/problems/{code-kebab}`), `title`, `status`, `detail`(화면에 그대로 보여줄 한국어 안내), `code`(프런트 분기용 안정 코드), `instance`, 추가 정보(`retry_after`, `recovery_token`, `email`, 입력 오류의 `errors[{field,message}]`)는 최상위 확장 필드. 입력 검증 오류는 422 `VALIDATION_ERROR`이며 메시지는 한국어로 변환한다. 프런트는 `api/http.js`의 `normalizeError`가 `detail`→`message`로 읽는다. 서버에서 새 오류를 만들 때는 `api_error(status, code, message, **extra)`만 사용한다
- 요청 제한: DB(`rate_limit_events`, IP·이메일은 HMAC 해시) 슬라이딩 윈도우. Redis 등 별도 인프라는 쓰지 않는다

## 주요 구조

```text
product-management/
├─ backend/
│  ├─ main.py
│  ├─ migrations/                 # 001~030 스키마·데이터 변경 이력
│  ├─ scripts/                    # 마이그레이션·검수·관리 스크립트
│  ├─ tests/
│  └─ src/backend/
│     ├─ core/                    # 설정, DB, 토큰·비밀번호 보안, 공통 오류(errors)·인증 쿠키 의존성(dependencies)·요청 제한·배송지(받는 분 이름·휴대폰·주소) 검증(address, validators)
│     └─ domain/
│        ├─ admins/               # 단일 관리자 인증
│        ├─ carts/                # 로그인 고객 서버 장바구니
│        ├─ inquiries/            # 상품 문의와 관리자 답변
│        ├─ orders/               # 주문·결제(토스페이먼츠)
│        ├─ reviews/              # 구매 고객 상품 후기
│        ├─ wishlists/            # 로그인 고객 찜 목록
│        ├─ products/             # 관리자 CRUD와 고객 공개 조회
│        └─ users/                # 고객 인증·계정 생명주기
├─ frontend/
│  ├─ public/                     # favicon, 브랜드 SVG, 카탈로그 히어로 이미지
│  └─ src/
│     ├─ api/                     # 관리자·고객·상품 API 호출
│     ├─ components/              # 공통, 상품, 고객 레이아웃
│     ├─ config/routes.js         # 공개·고객·비공개 관리자 경로
│     ├─ features/user-auth/      # 고객 인증과 마이페이지
│     ├─ features/cart/           # 장바구니·찜 저장소(shopping-store)와 장바구니 화면
│     ├─ features/checkout/       # 주문서·결제창(토스)·결제 결과 화면
│     ├─ features/product-feedback/ # 상품 후기·문의 구역
│     └─ pages/                   # 상품과 관리자 페이지
├─ .gitignore
└─ CLAUDE.md
```

현재 파일 검수 결과 `frontend/public`의 세 이미지, 001~015 마이그레이션, 적용·검수 스크립트, 고객 인증 소스는 모두 실제 코드 또는 DB 재현에 필요하다. 단순히 현재 런타임에서 직접 import되지 않는다는 이유로 마이그레이션 이력이나 관리 스크립트를 삭제하지 않는다.

## 로컬 실행

백엔드와 프런트를 서로 다른 터미널에서 실행한다. `fastapi dev`는 `pip install "fastapi[standard]"`가 설치돼 있어야 한다(개발 도구라 `requirements.txt`에 넣지 않음). macOS·Linux에서는 가상환경이 활성화돼도 시스템 Python의 `fastapi`가 먼저 잡힐 수 있으니 `.venv/bin/fastapi dev main.py --host 127.0.0.1`처럼 가상환경 경로로 실행한다.

```powershell
cd backend
fastapi dev main.py --host 127.0.0.1
```

```powershell
cd frontend
npm run dev
```

- 고객 상품 목록: `http://localhost:5173/`
- 고객 로그인: `http://localhost:5173/user/login`
- API: `http://127.0.0.1:8000`
- API 문서: `http://127.0.0.1:8000/docs`(`API_DOCS_ENABLED` 기본값: `FRONTEND_URL`이 http면 공개, https면 `/docs`·`/redoc`·`/openapi.json` 모두 끔)
- 헬스 체크: `GET /api/health`(DB `SELECT 1` 성공 시 200 `{"status":"ok"}`, 실패 시 503 `DATABASE_UNAVAILABLE`). 예전 `/`(hello world)는 제거
- 관리자 화면: 로컬 `VITE_ADMIN_BASE_PATH` 뒤에 `/login`

프런트는 API를 같은 출처 `/api`로 호출하고 Vite 개발 서버가 `http://127.0.0.1:8000`으로 프록시한다(쿠키가 `localhost:5173` 출처로 저장되도록). 배포 시에도 리버스 프록시로 프런트와 `/api`를 같은 출처에 둔다.

`frontend/.env.local`에 `/`로 시작하는 12자 이상의 `VITE_ADMIN_BASE_PATH`가 없으면 프런트가 의도적으로 시작·빌드되지 않는다. 실제 경로는 문서나 커밋에 남기지 않는다.

## 환경변수

실제 백엔드 값은 Git 제외 대상인 `backend/.env`, 관리자 프런트 경로는 `frontend/.env.local`에 둔다.

우선순위: `core/config.py`는 `load_dotenv(override=False)`라 **이미 설정된 환경변수(배포 플랫폼·셸) > `backend/.env` > 코드 기본값** 순이다(2026-10-02 변경). 설정은 서버 시작 시 한 번 읽으므로 바꾸면 재시작한다. 프런트 `VITE_` 값은 빌드 시 JS에 고정되므로 바꾸면 다시 빌드한다.

백엔드 주요 변수:

- `DATABASE_URL`
- `AUTH_SECRET_KEY`: 최소 32자
- `ACCESS_TOKEN_EXPIRE_MINUTES`: 접근 토큰 유효시간(기본 15분, 로컬 `backend/.env`도 15로 설정 확인됨)
- `ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES`(기본 15; 고객 `ACCESS_TOKEN_EXPIRE_MINUTES`와 별개 설정), `ADMIN_REFRESH_TOKEN_EXPIRE_HOURS`(기본 12, 관리자 로그인 유지 최대시간)
- `REFRESH_TOKEN_EXPIRE_DAYS`(기본 14, 로그인 유지 최대기간), `REFRESH_REUSE_GRACE_SECONDS`(기본 10, 동시 탭 재발급 경합 유예)
- `UNLOCK_TOKEN_EXPIRE_MINUTES`
- `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`
- `WITHDRAWAL_GRACE_DAYS`: 현재 7일
- `WITHDRAWAL_RETENTION_DAYS`: 현재 0일
- `FRONTEND_URL`(메일 링크·쿠키 Secure·API 문서 공개 여부·CORS 기본값 판단에 사용)
- `CORS_ORIGINS`(선택, 쉼표 구분, 기본은 `FRONTEND_URL` 하나). 개발은 Vite 프록시로 같은 출처라 CORS가 필요 없다
- `API_DOCS_ENABLED`(선택, 기본: `FRONTEND_URL`이 https가 아니면 true)
- `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES`(기본 1440, 미인증 계정 보관시간), `EMAIL_VERIFICATION_RESEND_SECONDS`(기본 60)
- `TOSS_SECRET_KEY`: 토스페이먼츠 시크릿 키(서버 전용, 현재 문서용 테스트 키 `test_sk_...`, 실제 결제 없음), `TOSS_API_BASE`(기본 https://api.tosspayments.com). 프런트 `frontend/.env.local`의 `VITE_TOSS_CLIENT_KEY`(공개 클라이언트 키, 테스트 `test_ck_...`). 운영 전 실제 가맹점 키로 교체하며 시크릿 키는 절대 Git에 올리지 않는다
- `TRUSTED_PROXY_IPS`: X-Forwarded-For를 신뢰할 리버스 프록시 IP·대역(쉼표 구분, 기본 빈 값=직접 접속 IP만 사용). 프록시 뒤에 배포하면 반드시 설정
- `AUTH_COOKIE_SECURE`(기본: `FRONTEND_URL`이 https이면 true), `AUTH_COOKIE_SAMESITE`(기본 lax; none은 Secure 필수)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `SMTP_USE_TLS`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`
- `ADMIN_MFA_REQUIRED`(기본: `FRONTEND_URL`이 https면 true). true면 관리자 2단계 인증이 등록되지 않은 상태에서 비밀번호만으로 로그인할 수 없다(503 `ADMIN_MFA_NOT_CONFIGURED`). 로컬에서만 false로 둔다
- `SENTRY_DSN`(백엔드 프로젝트 `aram-market-api`, 비우면 수집 끔), `SENTRY_ENVIRONMENT`(기본: `FRONTEND_URL`이 https면 `production`, 아니면 `development`), `SENTRY_RELEASE`(선택, 커밋 해시). 프런트는 `frontend/.env.local`의 `VITE_SENTRY_DSN`(프로젝트 `aram-market-web`, 공개돼도 되는 값)과 선택 `VITE_SENTRY_RELEASE`

## 오류 수집(Sentry)

무료 Developer 플랜(조직 전체 월 5,000건 에러, 키별 전송 상한은 Business 이상만 가능)이라 고칠 필요가 있는 오류만 보내도록 코드에서 거른다(우아한형제들 기술블로그 21604의 필터링 방식 참고).

- 백엔드 `core/monitoring.py`(`main.py`가 앱 생성 전에 `init_sentry()` 호출): 5xx(처리하지 못한 예외)와 `logger.error` 이상만 이슈로 보내고, 4xx `HTTPException`·사용자 연결 끊김은 `before_send`에서 버리며 `warning` 이하 로그는 오류 직전 흐름(breadcrumb)으로만 남긴다. 결제 수동 확인(`apply_payment_lookup`의 "needs manual review"), 메일 발송 실패, 정리 작업 실패가 ERROR 로그라 이슈가 된다.
- 개인정보: `send_default_pii=False`, `max_request_body_size="never"`(로그인·가입 본문 미전송), `include_local_variables=False`(기본값이면 스택 지역 변수에 요청 본문·쿠키가 실려 나가는 것을 2026-10-02 테스트로 확인해 끔). 성능 추적은 끔(`traces_sample_rate=0`).
- 토큰·이메일 제거(2026-10-02~03 Codex 검수 반영): 백엔드 `before_send`의 `scrub_event`가 요청 주소의 쿼리·`query_string`·쿠키·본문, `Referer`·`Cookie`·`Authorization`·`X-Forwarded-For` 헤더를 지우고, 예외 메시지·로그 메시지·흐름 기록의 이메일과 토큰 형태 문자열(JWT, 32자 이상 무작위 값)을 `[Filtered]`로 바꾼다. 프런트도 `sentry-scrub.js`의 `beforeSend`·`beforeBreadcrumb`가 같은 형태의 이메일·토큰을 이벤트 전체에서 가린다. 정상 Sentry 식별자는 최상위 `event_id`·`release`·`dist`, `contexts.trace`의 추적 ID, `debug_meta`의 `debug_id`, `contexts.session.sid`처럼 실제 스키마 경로에 있을 때만 보존하며, `extra.sid`처럼 이름만 같은 임의 데이터는 정리한다. 요청 본문·쿠키·민감 헤더와 주소·화면 이동 기록의 쿼리·해시도 지운다(메일 링크 `?token=`, 결제 결과 `paymentKey`·`orderId`·`amount`). 주소창의 쿼리를 `history.replaceState`로 지우는 방식은 결제 결과 화면 새로고침(멱등 재승인)이 쿼리에 의존해 쓰지 않았다. 백엔드 가짜 전송기 테스트와 프런트 Node 테스트에서 직렬화한 이벤트 전체에 가짜 토큰·이메일·결제키가 없는지 확인한다.
- 프런트 `src/instrument.js`(`main.jsx`가 가장 먼저 import): 서버 4xx·`NETWORK_ERROR` `ApiError`는 버리고(화면에 이미 안내함, 5xx는 백엔드가 수집), 동적 import 실패·`ResizeObserver`·네트워크 끊김 문구는 `ignoreErrors`, 우리 도메인 스크립트만 `allowUrls`. 서버 오류는 `api-error`+코드+상태로 묶는다(fingerprint). 성능 추적·세션 녹화 없음. React 19 `createRoot`의 `onUncaughtError: Sentry.reactErrorHandler()`와 전체를 감싼 `Sentry.ErrorBoundary`(대체 화면 `components/common/crash-fallback.jsx`).
- 테스트는 실제 DSN으로 보내지 않는다(`tests/test_monitoring.py`는 가짜 전송기, `test_api_routes.py`는 `SENTRY_DSN=""`).
- Sentry 화면 설정: 두 프로젝트의 Project Settings → Inbound Filters에서 브라우저 확장·구형 브라우저·크롤러 필터를 켜고(걸러진 건 한도 미차감), 배포 후 Localhost 필터를 켠다. 프런트 번들이 gzip 약 32KB 늘었다.
- 배포 시 CSP `connect-src`에 Sentry 수집 주소(`https://*.ingest.us.sentry.io`)를 허용한다. 소스맵 업로드(`@sentry/vite-plugin`, `SENTRY_AUTH_TOKEN`)는 아직 하지 않았다.

## 라우팅

고객 화면:

- `/`: 상품 목록, 검색, 카테고리, 페이지네이션. 카테고리 메뉴를 누르면 검색어가 초기화되고 검색은 항상 전체 상품에서 수행한다. 페이지를 넘기면 목록 제목이 보이도록 스크롤하고 첫 번째 상품에 포커스를 둔다
- `/products/{id}`: 변경되지 않는 내부 상품 ID 기반 상세
- `/products`: 기존 주소 호환용으로 `/` 이동
- `/products/detail?id={id}`: 기존 주소 호환용으로 `/products/{id}` 이동
- `/user/login`: 고객 로그인과 아이디·비밀번호 찾기
- `/user/signup`: 고객 회원가입
- `/user/reset-password?token=...`: 이메일 토큰 기반 재설정
- `/user/verify-email?token=...`: 가입 이메일 인증 확인(`&type=email-change`면 마이 페이지 이메일 변경 확인)
- `/user/login?next=...`: 로그인 후 `next`(고객 화면만 허용, `getSafeRedirectPath`)로 복귀. 장바구니 화면을 만들면 `config/routes.js`의 허용 목록에 추가
- `/user`: 로그인 고객 마이페이지(주문·배송 → 회원정보(닉네임·이메일·마케팅 수신 설정) → 배송지 관리 → 계정 관리 순서, 로그아웃 버튼은 헤더 상단에만 있음). 주문·배송은 최근 3건(`RECENT_ORDER_COUNT`)만 보이고 '전체 보기'로 `/user/orders`에 이동
- `/user/orders?months=3&page=1` 또는 `?from=YYYY-MM-DD&to=YYYY-MM-DD&page=1`: 주문 내역 페이지(로그인 필요). 조회 기간 3개월(기본)·6개월·1년 버튼과 '기간 설정'(시작일·종료일 직접 지정, 한국 시간 기준 오늘부터 5년 전 같은 날까지만 선택 가능, 브라우저 기본 날짜 입력), 한 페이지 5건 이전·다음 페이지네이션. 주문 카드의 상품을 누르면 상품 상세로 이동한다(마이 페이지 공용 `OrderList`, 상품 행이 삭제돼 `product_id`가 없으면 이동하지 않음). 기간·페이지는 주소에 담아 뒤로가기·새로고침에도 유지되며 범위 밖 페이지는 마지막 페이지로 이동
- `/wishlist`: 찜한 상품 페이지(로그인 필요, 카테고리 칩은 줄바꿈 없이 가로 스크롤이며 모바일에서는 화면 끝까지 넓혀 다음 칩이 잘려 보임, 이미지 위 하트로 찜 해제, 담기 버튼)
- `/cart`: 장바구니(로그인 없이 조회·수정 가능, 주문하기는 로그인 필요)
- `/user/unlock?token=...`: 잠금 해제 메일 링크. 화면의 버튼을 눌러야 POST로 해제
- `/checkout`: 주문서(주문 상품 확인·배송지 선택 또는 새 배송지 입력·배송 요청사항·결제하기, 로그인 필요). 상세 '구매하기'와 장바구니 '주문하기'가 주문 초안(상품 id·이름·가격·이미지·수량만)을 `sessionStorage`에 저장하고 이 화면으로 이동한다(로그아웃·세션 만료 시 초안 삭제). 기본 배송지가 미리 선택되고 '배송지 변경'으로 주소록에서 고르거나 '새 배송지 입력'으로 전환한다. 주소록이 비어 있으면 새 배송지 입력으로 시작한다(받는 분·연락처 자동 입력 없음). 새 배송지는 '이 배송지를 주소록에 저장' 체크박스(주소록 여유가 있을 때 기본 체크, 명칭 입력 필요, 가득 차면 안내만 표시)를 켜면 **결제 승인 성공 후에만** `/payment/success`가 주소록에 추가한다(기존 배송지는 바뀌지 않으므로 교체 경고·확인 모달은 없음, 저장 실패는 결제 결과에 영향 없음). 입력·선택은 주문 초안에 보관돼 결제 취소 후 돌아와도 유지된다. '이전으로'는 장바구니 주문이면 장바구니로, 바로 구매면 해당 상품 상세로 돌아간다.
- `/payment/success?paymentKey&orderId&amount`: 결제창 성공 리다이렉트(로그인 필요, 서버 승인 후 결과 표시), `/payment/fail?code=`: 결제 실패·취소 안내. 주소의 `message`는 누구나 바꿔 넣을 수 있어 쓰지 않고 `code`별 고정 문구(`payment-result.jsx`의 `PAYMENT_FAIL_MESSAGES`, 없으면 기본 문구)와 형식이 올바른 코드만 표시
- 브라우저 탭 제목: `config/routes.js`의 `getPageTitle`이 `화면 이름 | 아람 마켓`으로 정하고(App이 경로 변경 때 설정), 상품 상세는 상품을 불러온 뒤 상품명으로 바꾼다

관리자 화면:

- `${VITE_ADMIN_BASE_PATH}/inquiries?status=pending|answered&q=...&page=1`: 상품 문의 답변 관리(탭·검색어·페이지를 주소에 유지)
- `${VITE_ADMIN_BASE_PATH}/orders`: 결제 완료 주문의 배송지 확인·배송 상태 변경
- `${VITE_ADMIN_BASE_PATH}/login`
- `${VITE_ADMIN_BASE_PATH}/products`
- `${VITE_ADMIN_BASE_PATH}/products/new`
- `${VITE_ADMIN_BASE_PATH}/products/edit?id={id}`

관리자 URL 비공개 처리는 탐색 억제일 뿐 보안 경계가 아니다. 실제 접근 통제는 `/api/admin/products`의 `admin_access` 토큰 검증이 담당한다.

## 고객 인증

`public.users` 주요 컬럼:

- `username`, `password`, `nickname`, `email`
- `created_at`, `is_active`
- `login_fail_count`, `locked_until`
- `status`: `active`, `pending_deletion`, `withdrawn`
- `withdrawn_at`, `auth_version`
- `service_policy`, `privacy_policy`
- `marketing_consent`: 선택 이메일 수신 동의
- 회원 테이블에는 이름·휴대폰이 없다(028에서 제거). 받는 분 이름·연락처·주소는 `user_addresses`(주소록)와 주문 배송지에만 있다

정책:

- 아이디는 영문·숫자·밑줄 4~20자이며 소문자로 정규화한다.
- 비밀번호는 영문·숫자·특수문자를 포함한 8~64자다.
- 비밀번호 5회 실패 시 1시간 잠그고 SMTP 설정 시 잠금 해제 메일을 보낸다. 잠금 해제 토큰에는 잠금 시각(`lock`)이 들어 있어, 해제 후(잠금 시각 삭제)나 다시 잠긴 뒤에는 이전 링크가 400 `INVALID_UNLOCK_TOKEN`이 된다(1회용).
- 로그인 상태의 현재 비밀번호 확인(비밀번호 변경·이메일 변경 요청·탈퇴 신청)은 `UserService._lock_and_confirm_password`가 회원별로 15분에 5회 실패까지 허용하고 초과 시 429 `RATE_LIMITED`(버킷 `password-confirm-user`, `PASSWORD_CONFIRM_LIMIT`). 순서: 시도 예약(커밋) → 회원 행 `FOR UPDATE`(최신 값으로 다시 읽음) → 그 사이 `auth_version`이 바뀌었으면 401 `INVALID_ACCESS_TOKEN`(예약 삭제) → 잠근 최신 해시로 확인(틀리면 예약 유지) → 성공이면 예약 삭제를 계정 변경과 같은 커밋으로 반영. 같은 로그인으로 비밀번호 변경을 동시에 보내도 먼저 커밋한 요청만 반영된다.
- 메일 링크 토큰으로 계정을 바꾸는 요청(이메일 인증·비밀번호 재설정·이메일 변경 확정·잠금 해제·탈퇴 취소)은 `_get_user_for_update`로 회원 행을 `FOR UPDATE` 잠근 뒤 토큰 상태를 확인해, 같은 링크를 동시에 보내도 한 번만 통과한다. 이메일 변경 토큰에는 요청 당시 이메일(`current_email`)이 있어 다른 이메일 변경이 먼저 끝나면 오래된 링크는 400 `INVALID_EMAIL_CHANGE_TOKEN`.
- 메일 발송 실패 로그는 예외 종류만 남긴다(`SMTPRecipientsRefused` 등 예외 문자열에 수신 주소가 들어가므로).
- 비밀번호 재설정 토큰에는 발송 당시 이메일(`email`)이 들어 있어, 이메일을 바꾸면 이전 주소로 보낸 재설정 링크는 400 `INVALID_RESET_TOKEN`이 된다(로그인 세션은 유지).
- 존재하지 않는 아이디·오류 비밀번호·잠긴 계정은 같은 `INVALID_CREDENTIALS` 응답을 사용한다.
- 고객 토큰 용도는 `user_access`이며 `admin_access`와 교차 사용할 수 없다.
- 토큰은 로그인 응답 본문에 넣지 않고 HttpOnly 쿠키로만 발급한다. 프런트는 토큰 대신 `localStorage.userCurrentUser`(id·닉네임 표식)로 로그인 표시만 하며 실제 인증은 서버가 쿠키로 검증한다. 로그아웃은 `POST /api/users/signout`.
- CSRF는 SameSite 쿠키(기본 lax)와 JSON 요청·CORS 허용 출처 제한에 의존한다. 별도 CSRF 토큰은 없으므로 SameSite를 none으로 바꾸려면 CSRF 토큰을 먼저 도입한다.
- 회원가입에서는 이름·휴대폰·주소를 받지 않는다(개인정보 최소 수집: 주문에 필요한 값은 주문서에서 필수로 받고, 인증하지 않는 휴대폰 번호를 가입 필수로 받을 이유가 없음). 휴대폰 번호 인증(문자)은 구현하지 않는다(휴대폰은 배송 연락용일 뿐이며 본인 확인은 이메일 인증으로 한다). 회원정보에도 이름·휴대폰을 두지 않는다(주소록과 중복되고, 닉네임만 바꿀 때도 필수 입력이 되는 문제가 있어 2026-10-01 제거).
- 마이 페이지 회원정보 수정(`PUT /api/users/me/profile`): 닉네임만 수정한다(중복 불가 409 `NICKNAME_EXISTS`, 후기·문의 등 공개 표시명). 받는 분 이름·연락처·주소는 배송지 주소록에서 관리한다. 마케팅 수신 동의 스위치는 회원정보 카드 안에 있다. 이메일 변경은 현재 비밀번호를 확인한 뒤 새 이메일로 확인 링크(`user_email_change` 토큰, 새 이메일·`auth_version` 포함)를 보내고, 링크 확인(`POST /api/users/email-change/confirm`) 전까지 기존 이메일이 유지된다. 이미 가입된 이메일은 409 `EMAIL_EXISTS`, 발송은 메일 발송 제한(IP·대상 이메일)을 따른다.
- 약관 v1.1(2026-10-01): 이용약관에 테스트 사이트 고지·가입/인증·잠금·탈퇴 유예·주문/결제(토스페이먼츠)·배송 단계·장바구니/찜·후기/문의 규칙, 개인정보 동의에 선택 항목(주소록)·주문 배송정보·후기/문의·자동 생성 정보(동의 이력·쿠키·HMAC 변환 IP)·항목별 보유기간(주문·결제·배송 기록 5년)·처리 위탁(토스페이먼츠·Supabase(서버 소재지 대한민국, 국외 이전 없음)·메일 발송)·쿠키·이용자 권리를 추가했다. 마케팅 동의는 v1.0 유지. 기존 활성 회원 4명(testuser01·02·04·05)은 마이그레이션 027로 v1.1 동의 이력을 자동 추가했다(탈퇴 유예 중인 testuser03 제외, 복구해도 v1.1 이력은 없음). 재동의 화면은 없다. 약관 보기 모달은 긴 본문을 `.modal-content` 안에서 스크롤한다.
- 회원가입은 `password_confirm` 일치 검증(프런트·서버 모두)과 `policy_versions`(화면이 동의한 약관 버전) 검증을 거친다. 약관 본문·버전은 `services/policies.py`가 관리하며 본문을 바꾸면 버전을 올린다.
- 동의·철회 이력은 `user_policy_consents`에 행을 추가해 남긴다(가입 시 service/privacy/marketing, 마이페이지 마케팅 변경 시 marketing).
- 가입 직후 이메일 인증 링크(`user_email_verify` 토큰, 24시간)를 보내며 인증 전에는 올바른 비밀번호여도 `EMAIL_NOT_VERIFIED`로 로그인할 수 없다. 재발송은 60초 간격이며 응답은 계정 존재 여부를 숨긴다.
- 인증 유효시간이 지난 미인증 계정은 가입 시점·매시간 정리 작업에서 삭제되어 아이디·이메일 선점을 막는다. 아이디 찾기·비밀번호 재설정은 인증된 이메일에만 발송한다.
- 로그인 시 접근 토큰(짧은 수명)과 리프레시 토큰을 함께 HttpOnly 쿠키로 발급한다. 접근 토큰이 만료되면 프런트 `api/user-auth.js`의 `request`가 `POST /api/users/token/refresh`로 재발급한 뒤 원래 요청을 1회 재시도한다(동시 요청은 재발급 1회로 합침).
- 리프레시 토큰은 사용할 때마다 새 값으로 회전하고 이전 값은 폐기한다(`user_refresh_tokens`, 로그인 1회 = family 1개). 토큰은 48바이트 난수이고 `token_hash`가 고유 인덱스라 다른 회원과 겹치지 않는다. 같은 회원이 여러 창에서 동시에 재발급하면 재발급 조회가 해당 행을 `FOR UPDATE`로 잠가 차례로 처리하고, 늦은 쪽은 `REFRESH_IN_PROGRESS`(프런트는 성공으로 취급)가 된다(관리자도 동일). 이미 폐기된 토큰을 유예시간(10초) 뒤에 다시 쓰면 탈취로 보고 그 family를 전부 폐기한다. 유예시간 안의 재사용은 `REFRESH_IN_PROGRESS`로만 거부하고 쿠키는 지우지 않는다.
- 접근 토큰에는 `sid`(로그인 세션 = 리프레시 family)가 들어 있고 서버가 요청마다 해당 세션이 폐기·만료되지 않았는지 DB로 확인한다. 로그아웃·비밀번호 변경·탈퇴 즉시 기존 접근 토큰도 401이 된다(요청마다 조회 1회 비용).
- 비밀번호 변경·재설정·탈퇴 신청은 `auth_version`을 올리고 해당 회원의 모든 리프레시 토큰을 폐기한다. 로그아웃은 해당 로그인 세션(family)을 폐기한다. 만료 후 하루 지난 행은 매시간 정리 작업이 삭제한다.
- 비밀번호 변경·재설정 후 `auth_version`을 증가시켜 기존 토큰을 무효화한다.
- 탈퇴 요청은 `pending_deletion`으로 바꾸고 7일 이내 로그인 시 복구할 수 있다.
- FastAPI lifespan 작업(`main.py`의 `run_cleanup_once`)이 매시간 만료 고객 계정·미인증 계정·만료 리프레시 토큰·요청 제한 기록·미결제 주문(결제키 없는 것만)·5년 지난 결제 주문을 한 트랜잭션으로 정리한다. Postgres `pg_try_advisory_xact_lock`으로 서버가 여러 대여도 한 대만 실행한다. 이어서 잠금·트랜잭션 밖에서 `reconcile_unconfirmed_payments`가 승인 결과가 저장되지 않은 주문을 토스에 조회한다(주문·결제 절 참고).
- 요청 제한(`core/rate_limit.py`, 2026-10-02 Codex 검수 반영): 버킷마다 `pg_advisory_xact_lock(hashtextextended(버킷, 0))`으로 "횟수 확인 + 이번 시도 기록"을 한 트랜잭션에서 직렬화하는 `reserve_attempt`를 쓴다. 실패만 세는 요청(로그인 실패·토큰 확인·로그인 상태 비밀번호 확인)은 먼저 예약하고 실패가 아니면 `release_attempt`로 지운다(`guard_failures`, 실패 기준은 `is_failure`로 지정). 동시 요청 10개에 한도 5를 걸면 정확히 5개만 통과하는 것을 실제 DB로 확인했다. 로그인 실패는 접속 IP당 15분에 20회(공용 IP를 고려해 넉넉하게, 올바른 로그인은 세지 않음), 메일 발송 요청(가입·재발송·아이디 찾기·비밀번호 재설정)은 IP당 시간당 15회·대상 이메일당 시간당 5회, 가입은 IP당 시간당 10회다. 초과 시 429 `RATE_LIMITED`와 `Retry-After`. 토큰 확인 계열(재발급·이메일 인증 확정·비밀번호 재설정 확정·잠금 해제·탈퇴 취소, 관리자 재발급은 별도 버킷)은 접속 IP당 15분에 4xx 실패 30회까지이며 정상 요청과 동시 탭 경합(`REFRESH_IN_PROGRESS`)은 세지 않는다. 접속 IP는 `core/client_ip.py`가 `TRUSTED_PROXY_IPS`에 든 프록시가 붙인 `X-Forwarded-For`에서만 계산한다.
- 계정 잠금 해제는 메일 링크가 `/user/unlock` 화면을 열고 버튼을 눌러야 `POST /api/users/unlock`이 실행된다(메일 링크 미리보기로 해제되지 않도록).
- 마케팅 수신 동의는 회원가입과 마이페이지에서 변경할 수 있다.

고객 API:

| 방식 | 경로 | 기능 |
|---|---|---|
| `POST` | `/api/users/signup` | 회원가입 |
| `POST` | `/api/users/signin` | 로그인(HttpOnly 쿠키 발급) |
| `POST` | `/api/users/signout` | 로그아웃(리프레시 세션 폐기, 쿠키 삭제) |
| `POST` | `/api/users/token/refresh` | 리프레시 토큰으로 접근·리프레시 토큰 재발급 |
| `GET` | `/api/users/policies` | 현재 시행 약관과 버전 |
| `POST` | `/api/users/email-verification/confirm` | 이메일 인증 토큰 확인 |
| `POST` | `/api/users/email-verification/resend` | 인증 메일 재발송 |
| `POST` | `/api/users/find-username` | 아이디 안내 메일 요청 |
| `POST` | `/api/users/password-reset/request` | 재설정 메일 요청 |
| `POST` | `/api/users/password-reset/confirm` | 새 비밀번호 저장 |
| `POST` | `/api/users/unlock` | 잠금 해제 메일 화면의 버튼으로 토큰 확인 후 해제 |
| `GET` | `/api/users/me` | 현재 고객 조회 |
| `PUT` | `/api/users/me/password` | 비밀번호 변경 |
| `PUT` | `/api/users/me/marketing-consent` | 마케팅 동의 변경 |
| `PUT` | `/api/users/me/profile` | 닉네임 수정 |
| `POST` | `/api/users/me/email-change` | 이메일 변경 요청(비밀번호 확인 후 새 이메일로 확인 메일) |
| `POST` | `/api/users/email-change/confirm` | 확인 링크 토큰으로 이메일 변경 완료 |
| `DELETE` | `/api/users/me` | 7일 유예 탈퇴 신청 |
| `POST` | `/api/users/withdrawal/cancel` | 탈퇴 취소 |

장바구니: 로그인 고객은 서버 DB(`cart_items`, 가격은 저장하지 않고 조회 시 현재 상품 가격·이름·이미지 사용, 판매 종료 상품은 목록에서 제외, 삭제 전까지 유지)에 저장하고, 비로그인은 브라우저 메모리에만 있어 새로고침하면 초기화된다. 로그인 직후 비로그인 장바구니는 `POST /api/cart/merge`로 계정에 합쳐지고 로그아웃하면 화면 상태를 비운다(`features/cart/shopping-store.js`). 찜(♡)은 장바구니와 별개 기능이며 현재는 상품 상세 화면에서만 할 수 있다. 로그인 고객만 상세 화면의 ♡로 찜할 수 있고(`wishlist_items`, 삭제 전까지 유지) 비로그인이면 안내 **모달**을 띄운 뒤 확인 시 로그인 페이지로 이동하며(로그인 후 상세로 복귀) 찜 저장소 함수 `toggleWishlist`는 로그인 고객 전용이다. 찜한 상품은 별도 `/wishlist` 페이지(헤더 하트 아이콘)에서 보고 장바구니 담기·찜 해제를 한다(마이 페이지에는 찜 영역이 없다). API: `GET /api/wishlist`, `PUT`·`DELETE /api/wishlist/{product_id}`.

장바구니 API(로그인 고객, 수량은 상품당 1~99, 판매 중이 아닌 상품은 담기 거부·병합 시 건너뜀): `GET /api/cart`(목록), `POST /api/cart/items`(담기, 이미 있으면 수량 합산), `PUT /api/cart/items/{product_id}`(수량 변경), `DELETE /api/cart/items`(본문 `product_ids` 최대 100개 삭제), `POST /api/cart/merge`(로그인 직후 비로그인 장바구니 병합, 최대 100줄).

### 배송지 주소록

- 회원당 최대 10개(`MAX_ADDRESSES`, 초과 409 `ADDRESS_LIMIT_REACHED`). 항목: 명칭(1~20자)·받는 분·연락처·우편번호·주소·상세주소·기본 배송지 여부. 받는 분·연락처·주소 검증은 주문 배송지와 같은 공통 모델(`core/address.py`의 `AddressFields`)을 쓴다. 우편번호(숫자 5자리)·주소·상세주소는 필수이며, 단독주택처럼 상세주소가 없으면 '상세 주소 없음'(`no_address_detail`, DB 컬럼 없이 요청에만 있고 저장된 상세주소가 비어 있으면 화면이 체크 상태로 복원)을 골라야 비울 수 있다. 우편번호·기본 주소는 카카오(다음) 우편번호 서비스(`components/user/postcode-search-modal.jsx`, 스크립트 `t1.kakaocdn.net/.../postcode.v2.js`, API 키 없음)를 화면 안 모달로 띄워 검색으로만 채우고(읽기 전용 칸), 도로명 주소에 법정동·아파트명을 괄호로 붙인다. 서버는 값이 검색으로 채워졌는지 알 수 없어 형식만 검증한다. 필수화 이전에 저장된 배송지를 주문서에서 고르면 주문 전에 보완 안내를 띄운다(2026-10-01 testuser01의 기존 주문·주소록은 시청 주소로 보정해 남은 불완전 데이터 없음).
- 첫 배송지는 자동으로 기본 배송지이고, 기본 배송지는 DB 부분 고유 인덱스(`uq_user_addresses_default`)로 회원당 1개를 보장한다. 기본 배송지를 삭제하면 가장 최근에 추가한 배송지가 기본이 된다. 기본 배송지를 수정할 때 기본 해제는 무시된다(다른 배송지를 기본으로 지정해야 바뀜). 개수 확인·기본 지정은 회원 행을 `FOR UPDATE`로 잠가 동시 요청에도 지켜진다. 남의 배송지는 404.
- 마이 페이지 '배송지 관리'(`features/user-auth/address-book.jsx`)에서 추가·수정·삭제(삭제 확인 모달)·기본 지정을 하고, 주문서와 입력 칸·검증을 공유한다(`components/user/address-fields.jsx`, `config/address.js`). 주문은 배송지를 주문 기록에 복사해 저장하므로 주소록을 바꾸거나 지워도 지난 주문은 그대로다.
- API: `GET/POST /api/users/me/addresses`, `PUT/DELETE /api/users/me/addresses/{id}`, `PUT /api/users/me/addresses/{id}/default`.

### 고객 헤더

- `components/products/catalog-header.jsx`: 상단 한 줄에 비로그인이면 `회원가입 | 로그인`, 로그인이면 `{닉네임}님 | 로그아웃`(마이 페이지를 거치지 않고 바로 로그아웃). 주 줄 우측에 아이콘 버튼 `찜 목록`(`/wishlist`, 비로그인이면 안내 모달(`components/common/wishlist-login-modal.jsx`, 상세 찜하기와 공용) 후 확인 시 로그인 페이지로 이동)·`장바구니`(담긴 상품 종류 수 배지)·`마이 페이지`(로그인 시에만). 로그인 화면(`hideLogin`)에서는 비로그인 상단 링크를 숨긴다. 상단 줄은 아래 헤더와 같은 좌우 여백·최대 폭(1280px)을 쓰고 오른쪽 끝을 아이콘 오른쪽 끝에 맞춘다(1440·1024·700·375px에서 1px 이내로 확인). 이 정렬은 `.catalog-utility`의 패딩과 헤더 패딩(16/20px)을 함께 바꿔야 유지된다.

### 상품 상세 화면

- 판매 중이 아닌 상품(삭제·비노출·카테고리 비활성)의 상세는 404 `PRODUCT_NOT_ON_SALE` '판매가 종료된 상품입니다.', 없는 번호는 404 `PRODUCT_NOT_FOUND`. 주문 내역에서 판매 종료 상품을 눌렀을 때 이 안내가 보인다.
- 상단: 이미지(좌) · 상품명, 별점(후기 실데이터), 가격, 배송비, 정보 행(배송·판매자·수량), 총 상품금액, `찜 | 장바구니 | 구매하기`. 브레드크럼은 없다. 배송 요약 문구는 `config/shop-policy.js`의 `DELIVERY_SUMMARY`.
- 하단: 고정 탭(상품설명·상세정보·후기·문의, 활성 밑줄이 구분선과 겹치게 `margin-bottom:-1px`)과 구역. 페이지 배경은 다른 고객 화면과 같은 흰색 단일 톤이며 상세용 CSS는 `index.css` 끝의 '상품 상세' 블록 하나로 통합돼 있다.

### 후기·문의

- 후기: 해당 상품을 `paid` 주문으로 사고 그 주문이 배송완료(`delivery_status=delivered`)된 로그인 고객만 작성(쿠팡·컬리처럼 배송완료 후 작성. 서버가 주문 내역으로 확인, 미구매 403 `REVIEW_NOT_PURCHASED`, 배송 전 403 `REVIEW_NOT_DELIVERED`, 작성 자격 조회 `reason`은 `ok`·`not_purchased`·`not_delivered`·`already_reviewed`). 고객당 상품 1건이며 본인 후기만 수정·삭제한다. 별점 1~5, 내용 10~1000자. 작성자는 닉네임 첫 글자만 보이고 탈퇴 회원은 '탈퇴한 회원'으로 표시한다. 목록·평점 요약(개수·평균·최근 6개월 평균)은 비로그인도 조회할 수 있고 상세 상단 별점·탭 개수에 그대로 쓴다. API: `GET/POST /api/products/{id}/reviews`, `GET /api/products/{id}/reviews/eligibility`, `PUT/DELETE /api/reviews/{id}`.
- 문의: 로그인 고객 누구나 작성(5~1000자, 비밀글 선택), 본인 문의만 삭제. 비밀글은 작성자 본인에게만 내용·답변이 보이고 다른 사람에게는 '비밀글입니다.'로 표시한다. 관리자는 `/inquiries` 화면(`GET /api/admin/inquiries?status=pending|answered&q=&page=&page_size=`, `PUT /api/admin/inquiries/{id}/answer`)에서 전체 내용을 보고 답변한다. 탭은 답변 대기(오래된 순)·답변 완료(최근 답변 순)이며 응답 `counts`로 탭별 건수(검색어 적용)를 보여 준다. 검색 `q`(최대 100자)는 상품명·문의 내용·작성자 닉네임 부분 일치(ILIKE, `%`·`_`는 글자 그대로)다. 목록은 20건 단위 요약 행이고 행을 펼쳐 답변하며, 하단은 관리자 공용 `ProductPagination`(처음·이전·번호·다음·마지막)을 쓴다. 수십만 건으로 늘면 `pg_trgm` 인덱스를 검토한다. 작성은 IP당 시간당 20회로 제한한다. 고객 문의 API: `GET /api/products/{id}/inquiries`(비로그인도 조회, 비밀글은 본인만 내용 표시), `POST /api/products/{id}/inquiries`(로그인), `DELETE /api/inquiries/{id}`(본인 문의만, 남의 문의는 404).
- 후기·문의 내용은 텍스트로만 렌더링한다(HTML 미허용).
- 배송·교환·반품·환불 안내 문구는 `frontend/src/config/shop-policy.js`에 있으며 포트폴리오용 테스트 사이트라는 유의사항을 포함한다.

### 주문·결제(토스페이먼츠 테스트 모드)

- 흐름: 상세 '구매하기' 또는 장바구니 '주문하기'(로그인 필요) → 주문서(`/checkout`)에서 배송지 입력 → `POST /api/orders`(배송지 포함, 미입력·형식 오류 422)가 상품 가격을 서버에서 다시 조회해 금액을 계산하고, 카드 결제 지원 범위(100~2,147,483,647원)를 확인한 뒤 `pending` 주문(주문번호 `ARAM-YYYYMMDD-...`)을 만든다 → 프런트가 토스 결제창(SDK `https://js.tosspayments.com/v2/standard`, `features/checkout/toss-payments.js`)을 연다 → 성공 시 `/payment/success`가 `POST /api/orders/confirm`으로 서버 승인 요청 → 서버가 주문의 본인 여부·금액 일치를 확인하고 토스 승인 API(`/v1/payments/confirm`, 주문번호를 `Idempotency-Key`로 사용)를 호출한다. 승인 완료 결과를 받으면 주문 행을 다시 잠가 최신 상태·결제키를 확인하고 로컬 커밋까지 성공한 뒤에만 완료를 응답하며, 이 구간의 오류는 결제 실패가 아니라 `PAYMENT_CONFIRMATION_PENDING`으로 재확인하게 한다. 완료 시 장바구니 주문에 포함된 상품만 장바구니에서 제거한다.
- 토스 승인 오류 처리(2026-10-02 Codex 검수 반영): `toss.confirm_payment` 오류에는 토스 HTTP 상태(`gateway_status`)와 코드(`gateway_code`)가 담긴다. 4xx이면서 409·429가 아니고, 토스 오류 코드가 있으며, 그 코드가 `TOSS_UNCERTAIN_CODES`(`IDEMPOTENT_REQUEST_PROCESSING`·`ALREADY_PROCESSING_REQUEST`·`ALREADY_PROCESSED_PAYMENT`·내부 처리 오류 등)가 아닌 확정 거절만 `failed`로 바꾼다(결제키는 남김). 승인 응답이 200인데 JSON 객체가 아니면(깨진 본문·배열) `PAYMENT_RESPONSE_INVALID`, 그 밖의 예상 못 한 예외도 모두 불확정으로 처리한다. 그 밖의 오류(처리 중·이미 처리됨·5xx·429·연결 실패)나 200인데 응답이 주문과 다르면 실패로 확정하지 않고 즉시 `get_payment`로 조회해, 상태 `DONE`이고 주문번호·결제키·금액이 모두 맞으면(`payment_matches`) 완료 처리하고, 아니면 `pending` 그대로 503 `PAYMENT_CONFIRMATION_PENDING`("결제 결과를 확인하고 있습니다…")을 돌려준다.
- 결제 승인 누락 보정: 서버는 토스 승인 요청 **직전에** `payment_key`와 첫 `payment_attempted_at`을 주문에 먼저 저장·커밋한다(토스 응답을 기다리는 동안 주문 행 잠금을 쥐지 않음, 동시 승인은 주문번호 멱등 키가 한 번만 처리. 같은 주문에 다른 결제키면 409 `PAYMENT_KEY_MISMATCH`). 매시간 정리 작업은 두 단계다(외부 호출 동안 DB 트랜잭션·연결·정리 잠금을 쥐지 않음). ① `run_cleanup_once`가 advisory xact lock 아래 짧은 트랜잭션으로 계정·토큰·요청 기록·주문을 정리하고 커밋, ② `reconcile_unconfirmed_payments`가 **주문 생성 시각이 아니라 승인 시도 시각 기준** 10분(`RECONCILE_AFTER`)이 지났는데 결제키가 남은 `pending`·`failed` 주문만 읽고, 잠금 없이 `GET /v1/payments/{paymentKey}`를 호출한 뒤 주문별 `FOR UPDATE` 짧은 트랜잭션으로 반영한다. `payment_matches`면 `paid`로 복구하며 이전 `failure_message`도 지운다. `ABORTED`·`EXPIRED`·`CANCELED`는 즉시 미결제로 확정하지만 404는 승인 직후 조회 지연일 수 있어 `payment_attempted_at`부터 하루(`NOT_FOUND_FINAL_AFTER`) 동안 결제키를 보존해 재조회하고, 그 뒤에도 404일 때만 `failed`·결제키 제거한다. `READY`·`IN_PROGRESS`도 다음 주기에 재확인하고 그 밖의 상태는 ERROR 로그로 수동 확인한다. 삭제는 하루 지난 미결제 주문 중 **결제키가 없는 것만** 대상으로 한다. `PAYMENT_CONFIRMATION_PENDING` 화면은 실패로 표시하지 않고 재주문 금지 안내와 동일 주문 재확인 버튼을 보여 준다.
- 결제 금액 범위(2026-10-03 Codex 검수 반영): 상품 가격·주문 합계·결제 확인 금액·관리자 가격 입력을 모두 `core/validators.py`의 `MIN_CARD_PAYMENT_AMOUNT`(100원)~`MAX_ORDER_PAYMENT_AMOUNT`(2,147,483,647원)로 통일했다. 주문 합계가 범위를 벗어나면 결제창을 열기 전에 409 `ORDER_AMOUNT_NOT_SUPPORTED`. 금액 컬럼은 `BigInteger`다.
- 금액·상품명은 클라이언트 값을 믿지 않는다. 금액 불일치는 주문을 `failed`로 바꾸고 거부한다. 같은 결제 승인 요청을 다시 보내도(새로고침) 이미 `paid`이고 `payment_key`가 같으면 같은 결과를 돌려준다.
- 주문 테이블은 가격·상품명·이미지 스냅샷을 저장하고, 회원·상품이 삭제돼도 거래 기록이 남도록 `ON DELETE SET NULL`이다. 결제하지 않은 `pending`·`failed` 주문은 하루 뒤 정리 작업이 삭제한다. 주문 생성은 IP당 시간당 30회로 제한한다.
- 고객 주문 조회 `GET /api/orders?months=&page=&page_size=`: 결제 완료 주문만 최신순, `months`는 3·6·12만 허용(라우터는 `int`로 받고 서비스가 검증해 그 외는 422 `INVALID_ORDER_PERIOD`; `Literal[3, 6, 12]`로 선언하면 쿼리 문자열 "3"이 거부되므로 쓰지 않는다, 한국 시간 기준 N개월 전 같은 날 0시부터, 생략 시 전체 기간), `page_size` 기본 5·최대 20, `from`·`to`(쿼리 이름, YYYY-MM-DD)는 둘 다 지정해야 하며 시작일 ≤ 종료일, 최근 5년(`ORDER_HISTORY_MONTHS=60`) 안, 미래 불가, `months`와 함께 쓸 수 없다(위반 시 422 `INVALID_ORDER_DATE_RANGE`·`INVALID_ORDER_PERIOD`, 검증은 `order_period_range`). 응답 `orders`·`total`·`page`. 마이 페이지는 `page_size=3`으로 최근 3건, 주문 내역 페이지는 기간·페이지 단위로 조회한다. 전자상거래법상 대금결제·재화 공급 기록은 5년 보관 대상이므로 결제 완료 주문은 5년간 보관하고 그 뒤 정리 작업이 삭제한다.
- 배송: 결제 승인 시 `delivery_status=paid`(결제완료)이며 관리자가 주문 관리 화면(`GET /api/admin/orders`, `PUT /api/admin/orders/{order_number}/delivery-status`)에서 상품준비중 → 배송중 → 배송완료로 **한 단계씩만** 변경한다(건너뛰기·되돌리기 409 `INVALID_DELIVERY_TRANSITION`). 배송중·배송완료 시각을 기록하고 마이 페이지 주문 내역에 4단계 진행 표시와 배송지를 보여준다. 실제 택배사·송장 연동은 없다(포트폴리오용 더미 배송). 배송지 입력 기능 이전 주문은 배송지가 없다.
- 보관기간: 결제 완료 주문은 5년 보관 후 매시간 정리 작업(`purge_expired_orders`)이 삭제한다(한국 시간 5년 전 같은 날 0시 이전 결제, 고객 날짜 지정 조회 하한과 같음, 주문 상품은 CASCADE).
- 같은 상품을 결제완료·상품준비중·배송중인 상태에서 다시 주문해도 막거나 안내하지 않는다(2026-10-02 결정: 재구매는 대부분 정상 구매이고 실수 중복 결제는 주문번호 멱등 처리로 이미 막힘. 필요해지면 주문서 상품 줄에 막지 않는 한 줄 안내로 추가).
- 아직 없는 것: 환불·결제 취소 API, 재고 관리, 토스 웹훅(토스 대시보드 취소 등 외부 변경 동기화. 승인 누락 보정은 위 정리 작업이 대신함), 영수증. 실제 결제 전 이 항목과 전자상거래법상 거래기록 보관 정책을 설계한다.

## 단일 관리자 인증

`public.admin_accounts`에는 `id`, 고정 `username=admin`, `password`, `created_at`, `is_active`, `auth_version`과 2단계 인증 컬럼(`mfa_secret_encrypted`, `mfa_enabled_at`, `mfa_last_used_step`, `mfa_recovery_code_hashes`, 029)만 유지한다.

- 관리자 토큰 용도는 `admin_access`다. 로그인 시 접근 토큰(15분)과 리프레시 토큰(12시간, 회전·재사용 탐지, `admin_refresh_tokens`)을 HttpOnly 쿠키로 발급하고 프런트 `api/auth.js`의 `request`가 만료 시 `POST /api/admins/token/refresh`로 재발급 후 1회 재시도한다. 관리자 비밀번호 재설정(`auth_version` 증가)이나 계정 비활성화 시 기존 리프레시 토큰은 무효가 된다.
- 관리자 비밀번호는 채팅·소스·환경파일에 넣지 않고 `scripts/create_admin.py`의 `getpass`로 생성·재설정한다.
- 2단계 인증(TOTP, `domain/admins/services/mfa.py`): 등록되어 있으면 `POST /api/admins/signin`은 비밀번호가 맞아도 로그인 쿠키 대신 `mfa_required`와 5분짜리 대기 토큰(`admin_mfa_token` HttpOnly 쿠키, Path=/api/admins, 용도 `admin_mfa_pending`, `auth_version` 포함)만 준다. `POST /api/admins/signin/mfa`에 인증 앱 6자리 코드 또는 1회용 복구 코드(`XXXX-XXXX`)를 보내면 로그인 쿠키를 발급하고 대기 쿠키를 지운다.
  - 코드: Google Authenticator 기본값(SHA1·6자리·30초), 앞뒤 30초 허용. 통과한 30초 단계를 `mfa_last_used_step`에 저장해 같은 코드(또는 이전 코드) 재사용을 막고, 검증 중 관리자 행을 `FOR UPDATE`로 잠근다.
  - 실패 제한: 코드 실패는 기존 메모리 제한기(IP·`IP+admin`)에 기록되어 비밀번호 실패와 같은 단계적 제한(5번째부터 30초→…→1시간)을 받는다. 2단계 인증이 등록된 계정은 비밀번호가 맞아도 제한 기록을 초기화하지 않아(코드까지 통과해야 초기화) 비밀번호를 아는 공격자가 코드 대입 제한을 풀 수 없다.
  - 저장: TOTP 비밀값은 `AUTH_SECRET_KEY`에서 파생한 키로 Fernet 암호화해 저장하고, 복구 코드는 `AUTH_SECRET_KEY` HMAC 해시만 저장한다. **`AUTH_SECRET_KEY`를 바꾸면 2단계 인증을 다시 등록해야 한다**(복호화 실패 시 503 `MFA_UNAVAILABLE`).
  - 미등록 정책(2026-10-02 Codex 검수 반영, fail-closed): `ADMIN_MFA_REQUIRED=true`(https 운영 기본)면 미등록 관리자는 비밀번호가 맞아도 503 `ADMIN_MFA_NOT_CONFIGURED`, 등록 시각·비밀값 중 하나만 있는 부분 상태는 설정과 무관하게 503(ERROR 로그). `false`(로컬)이고 완전 미등록일 때만 비밀번호 로그인(WARNING 로그). 운영 첫 배포 직후 관리자 로그인 전에 등록 스크립트를 실행한다(헬스 체크에는 넣지 않음: 등록 전에도 서버는 떠야 하므로).
  - 등록·해제·확인: `scripts/setup_admin_mfa.py [enroll|disable|status] [--dark-terminal]`. 등록은 비밀값 생성 → 터미널 QR(검은 배경 터미널은 `--dark-terminal`)과 설정 키 표시 → 앱의 현재 코드로 확인 → 복구 코드 10개를 한 번만 표시 → 저장(`auth_version` 증가로 기존 관리자 세션 종료). 휴대폰과 복구 코드를 모두 잃으면 `disable` 후 다시 등록한다. 비밀값·복구 코드는 채팅·문서·커밋에 남기지 않는다.
  - 화면: `pages/admin-login.jsx`가 `mfa_required`를 받으면 코드 입력 단계로 바뀌고(입력칸은 복구 코드 영문 입력을 위해 `inputMode="text"`·대문자 자동), `MFA_SESSION_EXPIRED`면 처음(비밀번호) 단계로 돌아간다.
- 서버 메모리에서 IP 버킷과 `IP+아이디` 버킷을 분리해 로그인 실패를 제한한다. 접속 IP는 `TRUSTED_PROXY_IPS` 프록시가 붙인 `X-Forwarded-For`에서만 읽는다.
- 다섯 번째 실패부터 `30초 → 1분 → 5분 → 1시간` 제한과 `Retry-After`를 적용한다.
- 원문 IP 대신 HMAC 지문을 기록하며 임의 `X-Forwarded-For`를 신뢰하지 않는다.
- 관리자 제한기는 단일 프로세스 메모리 기반이라 서버 재시작·다중 서버에서는 초기화·분리된다(관리자는 1명이고 로그인 시도가 드물어 유지). 서버를 여러 대로 늘리면 `core/rate_limit.py`의 DB 방식으로 옮긴다.

```powershell
cd backend
$env:PYTHONPATH=(Resolve-Path .\src).Path
.\.venv\Scripts\python.exe scripts\create_admin.py
```

관리자 API:

| 방식 | 경로 | 기능 |
|---|---|---|
| `POST` | `/api/admins/signin` | 관리자 로그인(2단계 인증 등록 시 `mfa_required`와 대기 쿠키만) |
| `POST` | `/api/admins/signin/mfa` | 인증 앱 코드·복구 코드 확인 후 로그인 쿠키 발급 |
| `GET` | `/api/admins/me` | 관리자 쿠키·활성 상태 확인 |
| `POST` | `/api/admins/signout` | 관리자 로그아웃(리프레시 세션 폐기, 쿠키 삭제) |
| `POST` | `/api/admins/token/refresh` | 리프레시 토큰으로 접근·리프레시 토큰 재발급 |

## 상품과 Storage

- 상품은 관리자 개인 소유가 아닌 전역 카탈로그다.
- 고객에게는 `status=active`, `visible=true`, 활성 카테고리 상품만 노출한다.
- 활성 상품코드와 노출순서는 전역 고유값이다.
- 삭제는 `status=deleted`, `visible=false`, `deleted_at`을 기록하는 소프트 삭제다.
- 관리자 목록은 판매 상품과 삭제 상품을 분리하며 삭제 상품을 복원할 수 있다.
- 복원 상품은 `visible=false`로 시작하고 충돌 노출순서는 마지막 순서로 자동 조정한다.
- 감사 로그는 상품·동작(`created`, `updated`, `deleted`, `restored`)·변경값·시각을 보존한다.
- 상품 대표 이미지와 상세 이미지는 Supabase Storage에 저장한다.
- 저장 경로는 `products/{category_code}/{YYYY-MM-DD}/{main|detail}-{uuid}.확장자`다.
- 상세 이미지는 저장 전 `products/_drafts/{upload_session_id}/...`에 올리고 저장·취소 시 정리한다.
- 비정상 종료 임시 파일은 `cleanup_product_image_drafts.py --retention-hours 24`로 정리한다.
- 카테고리 변경 시 이미지 경로도 이동하며 DB 실패 시 원래 경로로 롤백한다.
- 상세 HTML은 서버 허용 목록으로 다시 정리한다. `<img>`는 자사 Supabase Storage 상품 이미지 버킷 주소(`product_storage.public_url("")`로 시작, `..` 불가)만 남기고 외부 이미지는 제거한다(2026-10-02 기존 상세 이미지 30개 모두 자사 주소 확인). 로고·배너는 프런트 `public/` 정적 파일이라 해당 없다.
- 경로·본문의 모든 정수 ID(상품·문의·후기·주소·장바구니·관련 상품 등)는 1~`MAX_DB_ID`(2,147,483,647, PostgreSQL integer 상한) 범위만 받는다. 범위 밖 번호는 DB 오류(500) 대신 422 `VALIDATION_ERROR`(`tests/test_api_routes.py`가 확인).
- 상품·문의 검색어의 `%`·`_`·`\`는 와일드카드가 아닌 글자로 찾는다(`core/validators.py`의 `escape_like` + `ilike(..., escape="\\")`).
- 상품 시각 API는 `+09:00`, 프런트 표시는 `Asia/Seoul` 기준이다.

관리자 상품 API:

| 방식 | 경로 | 기능 |
|---|---|---|
| `GET`, `POST` | `/api/admin/products` | 목록·등록 |
| `GET`, `PUT`, `DELETE` | `/api/admin/products/{id}` | 상세·수정·삭제 |
| `POST` | `/api/admin/products/{id}/restore` | 복원 |
| `GET` | `/api/admin/products/categories` | 카테고리 |
| `GET` | `/api/admin/products/related-candidates` | 관련 상품 후보 |
| `POST` | `/api/admin/products/editor-images` | 상세 임시 이미지 업로드 |
| `DELETE` | `/api/admin/products/editor-image-drafts/{upload_session_id}` | 임시 세션 정리 |

고객 공개 상품 API:

| 방식 | 경로 | 기능 |
|---|---|---|
| `GET` | `/api/products` | 검색·카테고리·페이지 조회 |
| `GET` | `/api/products/categories` | 활성 카테고리 |
| `GET` | `/api/products/{id}` | 상품 상세와 관련 상품 |

## DB 마이그레이션

- `001`~`002`: 초기 사용자 인증과 탈퇴 생명주기
- `003`~`006`: 상품·Storage·소프트 삭제·전역 카탈로그
- `007`: 과거 사용자형 관리자 승인 구조 전환 이력
- `008`: 단일 `admin` 계정 구조로 축소
- `009`: 관리자 DB 잠금 컬럼 제거와 IP 제한 전환
- `010`~`011`: 상품·감사 로그의 중복 관리자 ID 제거
- `012`: 한국 시간대 설정 시도. Supabase Pooler 때문에 요청 세션에서도 별도 설정
- `013`: 상품 복원 감사 유형
- `014`: `products.image_data` 제거와 `image_path` 필수화
- `015`: 고객 `marketing_consent` 추가, 실제 DB 적용 완료
- `029`: `admin_accounts`에 2단계 인증 컬럼 4개 추가(컬럼 추가만, 재실행 안전, 기존 관리자는 미등록 상태), 2026-10-02 실제 DB 적용 완료(2회 실행 확인). 적용: `scripts/apply_admin_mfa.py`, 확인: `scripts/check_admin_mfa.py`(비밀값 미출력). `check_auth_schema.py`의 기대 컬럼도 함께 갱신
- `030`: `orders.payment_attempted_at`과 조회 인덱스 추가. 결제키가 있는 기존 주문은 결제 완료면 `paid_at`, 미확정이면 실제 시도 시각을 알 수 없어 마이그레이션 시각으로 백필(하루 유예가 그때부터 시작). 재실행 안전, 2026-10-03 실제 DB 적용 완료(2회 실행, 결제 완료 7건은 `paid_at`으로 채움). 확인 스크립트는 누락 시 종료 코드 1. 적용: `scripts/apply_order_payment_attempted_at.py`, 확인: `scripts/check_order_payment_attempted_at.py`
- `028`: `users.name`·`phone` 제거(적용 전 값이 저장된 회원이 없음을 확인, 적용 스크립트가 값이 있으면 중단, 재실행 안전), 실제 DB 적용 완료. 적용: `scripts/apply_drop_user_profile_fields.py`, 확인: `scripts/check_drop_user_profile_fields.py`
- `027`: 약관 v1.1 시행에 맞춰 이메일 인증된 active 회원에게 service·privacy v1.1 동의 이력 추가(재실행 안전, 실제 DB 적용 완료 4명×2건). 적용: `scripts/apply_policy_v1_1_backfill.py`, 확인: `scripts/check_policy_v1_1_backfill.py`
- `026`: `user_addresses`(배송지 주소록, 기본 배송지 부분 고유 인덱스) 생성과 `users.postcode`·`address`·`address_detail` 제거(적용 전 주소 데이터가 없음을 확인), 실제 DB 적용 완료. 적용: `scripts/apply_user_addresses.py`, 확인: `scripts/check_user_addresses.py`
- `025`: `users`에 `name`·`phone` 추가(당시 주소 컬럼 3개도 추가했다가 026에서 제거, 재실행 안전, 기존 회원은 NULL), 실제 DB 적용 완료, 028에서 다시 제거. 적용: `scripts/apply_user_profile_fields.py`, 확인: `scripts/check_user_profile_fields.py`(028 이후에는 `profile_columns_ok=false`가 정상이라 검증 명령에서 제외)
- `024`: `orders`에 배송지(`recipient_*`·`postcode`·`address*`·`delivery_memo`)와 `delivery_status`·`shipped_at`·`delivered_at` 컬럼 추가(재실행 안전, 기존 주문은 배송지 없이 `paid` 유지), 실제 DB 적용 완료. 적용: `scripts/apply_order_shipping.py`, 확인: `scripts/check_order_shipping.py`
- `023`: `product_reviews`·`product_inquiries` 추가(재실행 안전), 실제 DB 적용 완료. 적용: `scripts/apply_reviews_and_inquiries.py`, 확인: `scripts/check_reviews_and_inquiries.py`
- `021`: `wishlist_items`, `022`: `orders`·`order_items` 추가(재실행 안전), 실제 DB 적용 완료. 적용: `scripts/apply_wishlist_and_orders.py`, 확인: `scripts/check_wishlist_and_orders.py`
- `019`: `rate_limit_events`, `020`: `cart_items` 추가(재실행 안전), 실제 DB 적용 완료. 적용: `scripts/apply_rate_limit_and_cart.py`, 확인: `scripts/check_rate_limit_and_cart.py`
- `018`: `admin_refresh_tokens` 테이블 추가(재실행 안전), 실제 DB 적용 완료. 확인: `scripts/check_admin_refresh_tokens.py`
- `017`: `user_refresh_tokens` 테이블 추가(재실행 안전), 실제 DB 적용 완료. 확인: `scripts/check_user_refresh_tokens.py`
- `016`: `user_policy_consents` 생성·기존 회원 v1.0 이력 백필, `users.email_verified_at`·`email_verification_sent_at` 추가와 기존 회원 인증 완료 처리, 실제 DB 적용 완료(재실행 안전). 확인: `scripts/check_policy_and_email_schema.py`

새 환경에서는 마이그레이션을 번호 순서대로 이해하되 이미 최종 스키마인 DB에 과거 파괴적 마이그레이션을 재실행하지 않는다. 적용 전 현재 테이블·행 수·제약조건을 읽기 전용으로 확인한다.

## 검증 명령

백엔드:

```powershell
cd backend
$env:PYTHONPATH=(Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q main.py src scripts
.\.venv\Scripts\python.exe scripts\check_auth_schema.py
.\.venv\Scripts\python.exe scripts\check_products.py
.\.venv\Scripts\python.exe scripts\check_product_restore.py
.\.venv\Scripts\python.exe scripts\check_policy_and_email_schema.py
.\.venv\Scripts\python.exe scripts\check_user_refresh_tokens.py
.\.venv\Scripts\python.exe scripts\check_wishlist_and_orders.py
.\.venv\Scripts\python.exe scripts\check_reviews_and_inquiries.py
.\.venv\Scripts\python.exe scripts\check_order_shipping.py
.\.venv\Scripts\python.exe scripts\check_drop_user_profile_fields.py
.\.venv\Scripts\python.exe scripts\check_user_addresses.py
.\.venv\Scripts\python.exe scripts\check_policy_v1_1_backfill.py
.\.venv\Scripts\python.exe scripts\check_admin_refresh_tokens.py
.\.venv\Scripts\python.exe scripts\check_admin_mfa.py
.\.venv\Scripts\python.exe scripts\check_order_payment_attempted_at.py
.\.venv\Scripts\python.exe scripts\check_smtp.py
```

프런트:

```powershell
cd frontend
npm run lint
npm run build
```

기능 변경 시 최소 검증:

- 인증: 잘못된 비밀번호, 토큰 용도 분리, 만료·`auth_version`, 잠금·탈퇴 상태
- 상품: 활성/삭제 필터, 전역 중복, 관련 상품 동일 카테고리, 이미지 롤백
- 프런트: 직접 URL 접근, 뒤로가기, 세션 만료, 모바일 880px 이하 페이지 크기
- DB: 마이그레이션 재실행 가능 여부와 기존 데이터 보존

## 배포 전 변경 필수 항목

- **CORS**: 허용 출처는 `CORS_ORIGINS`(기본 `FRONTEND_URL`)뿐이다(2026-10-02 localhost 고정값 제거). 배포에서는 `FRONTEND_URL`을 실제 도메인으로 두면 된다. 프런트와 `/api`를 같은 도메인에 두면 CORS 자체가 적용되지 않는다.
- **프록시**: 리버스 프록시 뒤에 배포하면 `TRUSTED_PROXY_IPS`에 프록시 IP·대역을 넣어야 로그인 제한·메일 제한이 실제 접속자 IP 기준으로 동작한다(비우면 모든 사용자가 프록시 IP 하나로 보임). 프록시는 `X-Forwarded-For`를 덧붙이는 방식이어야 하며 배포 환경에서 로그인 제한이 사용자별로 걸리는지 확인한다.
- `AUTH_COOKIE_SECURE=true`(https), `TRUSTED_PROXY_IPS`(리버스 프록시 IP), `ACCESS_TOKEN_EXPIRE_MINUTES`(권장 15) 확인.
- 토스페이먼츠 실제 키로 교체. 결제 성공·실패 URL은 `toss-payments.js`가 `window.location.origin`으로 만들므로 따로 바꿀 필요 없다.
- **관리자 경로는 번들에 포함된다**: `VITE_` 변수는 빌드 시 JS에 그대로 박히므로 `VITE_ADMIN_BASE_PATH`는 공개 번들을 받은 누구나 찾을 수 있다(2026-10-02 `dist` 확인). 실제 보호는 서버의 관리자 토큰 검증이며, 더 숨기려면 관리자 화면을 별도 빌드·서브도메인으로 분리하거나 IP 허용 목록을 둔다.
- `AUTH_SECRET_KEY`를 바꾸면 발급된 모든 토큰·메일 링크가 무효가 된다.
- **API 문서 노출**: `/docs`(Swagger UI)·`/redoc`·`/openapi.json`은 폴더가 아니라 FastAPI가 자동으로 만드는 URL이다. `FRONTEND_URL`이 https면 기본으로 셋 다 꺼진다(`API_DOCS_ENABLED=true`로만 다시 켬). 배포 후 세 주소가 404인지 확인한다.
- **헬스 체크**: 배포 플랫폼 상태 확인 경로는 `/api/health`다.
- **백엔드 프로세스 수**: 관리자 로그인 실패 제한기가 서버 메모리 방식이므로 배포 시 백엔드는 인스턴스 1대·uvicorn 워커 1개(`--workers` 미지정)로 둔다. 늘려야 하면 아래 '보류 목록'의 제한기 DB 전환을 먼저 한다.
- **실행 버전**: Python 3.14(`backend/.python-version`), Node 24(`frontend/.nvmrc`, `package.json` `engines`). 백엔드 패키지는 `requirements.txt`에 로컬에서 테스트한 버전(`==`)으로 고정했고 프런트는 `package-lock.json`이 고정한다. 운영 실행은 `fastapi dev`(자동 재시작 개발 서버) 대신 `uvicorn main:app --host 0.0.0.0 --port $PORT`(작업 디렉터리 `backend`)를 쓴다. 호스팅이 3.14를 지원하지 않으면 지원 버전으로 다시 테스트한 뒤 바꾼다.
- **DB 연결 방식**: 현재 Supabase 세션 풀러(포트 5432)를 쓴다. 트랜잭션 풀러(6543)는 요청(트랜잭션)마다 다른 DB 연결을 돌려 쓰므로 asyncpg가 연결에 만들어 둔 prepared statement를 찾지 못한다(2026-10-02 실제 재현: `prepared statement "__asyncpg_stmt_5__" does not exist`). `core/database.py`는 `DATABASE_URL` 포트가 6543이면 자동으로 statement 캐시를 끄고 문장 이름을 매번 새로 만든다(동시 20세션×3회 조회·시간대 `Asia/Seoul` 확인). 연결 수 한도에 걸리거나 서버리스 호스팅을 쓰면 URL의 포트만 6543으로 바꾸면 된다. 6543이면 앱 연결 풀도 `NullPool`로 바꿔 연결을 쥐지 않고(자동 확장 시 인스턴스마다 풀이 쌓이는 것 방지, Supabase 권장), 5432이면 장기 실행 서버 기준 `pool_size=5`·`max_overflow=5`(최대 10개)를 명시한다(2026-10-02 Codex 검수 반영, 두 방식 모두 실제 DB로 확인). `get_db`의 `SET TIME ZONE`은 트랜잭션 단위라 요청 중 커밋 뒤에는 유지되지 않을 수 있으나, 시각 컬럼은 모두 `timestamptz`이고 표시 변환은 Python·프런트가 하므로 영향이 없다.
- **`.env` 우선순위**: 2026-10-02 `override=False`로 바꿔 플랫폼 환경변수가 `.env`보다 우선한다. 그래도 배포 서버에는 `.env` 파일을 두지 않는 것을 원칙으로 한다.
- **환경변수 템플릿(선택)**: `backend/.env.example`은 `.gitignore`로 제외돼 저장소에 없다. 배포에는 필요 없고, 새 PC에서 클론할 때 변수 이름을 알려 주는 양식이 필요할 때만 실제 값 없이 추적한다(변수 목록은 이 문서 '환경변수' 절이 대신한다).
- **보안 헤더**: 백엔드·프런트 응답에 `X-Content-Type-Options`·`Strict-Transport-Security`·CSP 같은 헤더가 없다. 리버스 프록시(또는 CDN)에서 추가한다.

## 실제 상용화 시 DB 분리

현재는 포트폴리오용이라 로컬 개발과 배포가 Supabase 프로젝트 하나(DB·Storage)를 함께 쓴다(테스트 회원·주문·후기·문의는 시연용 데이터로 유지). 실제 서비스로 전환하면 다음 이유로 개발·운영 프로젝트를 분리한다.

- 스키마 변경이 배포보다 먼저 운영에 적용된다: 로컬에서 마이그레이션을 적용하거나 서버를 켜기만 해도(`create_all`) 운영 DB 구조가 바뀌어, 옛 코드가 돌고 있는 배포 사이트가 깨질 수 있다(예: 028의 컬럼 삭제).
- 로컬 테스트가 실제 고객 데이터를 바꾼다: 관리자 화면에서 상품·이미지를 지우면 Storage도 공용이라 운영 이미지가 사라지고, 테스트 주문·후기가 고객에게 보인다.
- 로컬 서버의 매시간 정리 작업이 운영 데이터를 대상으로 돈다: 수정 중인 정리 코드가 실제 계정·주문을 삭제할 수 있다.

권장 사항:

- Supabase 프로젝트를 개발·운영 두 개로 나누고(무료 플랜으로 가능) 로컬 `backend/.env`는 개발 프로젝트, 배포 환경변수는 운영 프로젝트를 가리킨다. Storage 버킷과 키도 프로젝트별로 둔다.
- 마이그레이션은 개발 DB에서 먼저 적용·검수 스크립트로 확인한 뒤 배포와 함께 운영에 적용한다. 컬럼 삭제처럼 호환이 깨지는 변경은 "새 코드 배포 → 컬럼 삭제" 두 단계로 나눈다.
- 운영 DB에는 테스트 계정을 만들지 않고, 운영 자료가 필요한 확인은 읽기 전용 검수 스크립트로만 한다. 정기 백업(Supabase 백업 또는 `pg_dump`)을 켠다.
- 분리 전(현재)까지는 마이그레이션을 배포와 같은 날 적용하고, 공개 전에 시연용이 아닌 테스트 흔적을 정리한다.

## 보류 목록 (현 상태 유지, 조건이 되면 진행)

2026-10-02 결정: 아래 항목은 지금 구현하지 않고 기록만 하며, 진행 조건이 실제로 생길 때 구현한다. 특히 관리자 관련 두 항목은 현재 배포 범위(관리자 1명, 백엔드 인스턴스 1대·워커 1개)에서는 작업하지 않는다.

| 항목 | 진행 조건 | 메모 |
|---|---|---|
| 개발·운영 DB 분리 | 실제 서비스로 전환할 때 | 이유·권장 사항은 '실제 상용화 시 DB 분리' 절 |
| 문의·상품 검색 인덱스(`pg_trgm` GIN) | 문의·상품이 수만 건 이상으로 늘어 관리자 검색이 느려질 때 | Supabase에 `pg_trgm` 1.6 설치 가능(미설치), DB 로케일 `en_US.UTF-8`이라 한글도 대상. 3글자 미만 검색어는 효과가 작고, 관리자 문의 검색은 문의·상품·회원 3테이블 OR 조건이라 쿼리 구조 조정이 함께 필요할 수 있다. 진행 시 다음 빈 마이그레이션 번호(현재 031) + 적용·확인 스크립트 |
| `order_items.product_id` 인덱스 | 주문이 크게 늘어 후기 작성 자격 조회가 느려질 때 | |
| 관리자 로그인 제한기 DB 전환 | 백엔드 인스턴스나 uvicorn 워커를 2개 이상으로 늘릴 때(Codex 검수 P2에서도 지적됨, 2026-10-02 사용자 결정으로 보류 유지) | 관리자 계정 수가 아니라 서버 프로세스 수가 기준이다. 관리자 계정만 늘고 인스턴스 1대·워커 1개를 유지하면 현재 메모리 제한기를 계속 쓸 수 있다. 다중 프로세스에서는 실패 횟수가 프로세스별로 나뉘고 재시작 시 초기화되므로 배포 확장 전에 단계적 제한(30초→1분→5분→1시간)을 DB로 옮긴다. 고객 제한은 이미 DB(`rate_limit_events`) 방식이다. |
| 관리자 계정 분리(감사 로그 수행자 기록) | 실제 관리자가 2명 이상이 될 때 | 관리자별 계정·MFA·로그인 세션을 분리하고 상품 변경 등 감사 로그에 수행자 식별자를 다시 기록한다. 서버가 단일 프로세스라면 이 작업과 관리자 제한기 DB 전환은 별개다. |
| CSRF 토큰 | 쿠키 SameSite를 `none`으로 바꿔야 할 때 | |
| 실제 DB 동시성 통합 테스트 환경 | 실제 서비스 사이트를 만들 때(2026-10-03 결정: 포트폴리오에서는 구현 안 함) | 로컬 PostgreSQL(Docker)이나 테스트 전용 Supabase 프로젝트에서 세션 2개로 동시 비밀번호 변경·요청 제한 경쟁을 재현한다. 현재는 운영 겸용 DB라 테스트 계정을 만들 수 없어 행 잠금 순서·버전 재확인을 단위 테스트로만 검증한다. |

해결되어 목록에서 뺀 항목: 결제 승인 대기 중 주문 행 잠금(D10)은 A5에서 결제키를 먼저 저장·커밋하고 토스를 잠금 없이 호출하도록 바뀌어 해결됐다(동시 승인은 토스 주문번호 멱등 키로 1회만 처리).

## 다음 작업 후보와 미구현 범위

- 결제는 토스페이먼츠 테스트 키로만 연동돼 있다. 환불·재고·웹훅이 없다.
- 후기 사진 첨부·도움돼요·신고·관리자 후기 삭제 기능이 없다.
- 선택 개선(필요해지면): 주문 생성 시점의 재고 확인, 주소록 기반 배송지 별 기본 요청사항. 인덱스·제한기 등은 '보류 목록' 참고.
- 관리자 2단계 인증(TOTP)은 구현됐다(2026-10-02). 관리자 계정을 여러 명이 쓰게 되면 계정 분리(감사 로그의 수행자 기록 복구)를 먼저 도입한다. 기기별 로그인 세션은 이미 독립적이다.
- 계정 잠금(5회 실패 1시간)은 아이디만 알면 남이 일부러 잠글 수 있다. IP 제한은 이를 완화할 뿐 막지 못한다.
- 리프레시 쿠키 Path는 `/api/users`다. 배포 시 API 접두사가 바뀌면 함께 바꾼다.
- 관리자 비공개 경로는 배포 보안 수단이 아니다(2단계 인증으로 보완, 필요하면 WAF 추가). 배포 시 `AUTH_COOKIE_SECURE=true`(https) 확인이 필요하다.
- SPA 배포 서버는 `/products/{id}`, `/user/*`, 관리자 비공개 경로를 `index.html`로 fallback해야 한다.
- 상품 상세는 2026-09-30에 상단·탭·배경을 개편했다. 추가 개편 때 찜 UI(목록 카드 하트 등)를 함께 검토한다. 목록 카드는 이미지 아래 전폭 '담기' 버튼(컬리 방식)이다.

## 배포 전 점검과 교차 검수 (2026-10-02~03)

결론: 배포 전 코드 작업과 Claude↔Codex 교차 검수 4회차 지적까지 반영 완료. 030은 2026-10-03 적용 완료. 앞으로도 스키마를 바꾸는 배포는 **마이그레이션 적용 → 확인 스크립트 종료 코드 0 → 애플리케이션 배포** 순서를 지킨다(새 코드가 없는 컬럼을 읽으면 주문 등 API가 실패한다).

### 현재 검증 결과 (2026-10-03, Codex 4회차 반영 후)

| 영역 | 확인 내용 | 결과 |
|---|---|---|
| 정적 분석 | `ruff --select F,E9,B,ASYNC`(B008 제외) — `src`·`main.py`·`scripts`·`tests` 전체 | 이상 없음. 보안 규칙 S까지 켜면 관리 스크립트 4곳에서 S608(코드에 고정된 테이블 이름을 f-string으로 넣음)이 나오지만 외부 입력이 없어 오탐으로 둠 |
| 기타 정적 분석 | `vulture --min-confidence 80`, `oxlint`, `pip check` | 이상 없음 |
| 의존성 취약점 | `pip-audit -r requirements.txt`, `npm audit --omit=dev` | 0건 |
| 자동 테스트 | 백엔드 134개, 프런트 Node 6개(`npm test`), `compileall`, Vite 빌드 | 통과 |
| DB 검수 | `check_*` 15종(읽기 전용) | 모두 정상(030 적용 후 `payment_attempted_at_ok=true`, 관리자 MFA 등록·복구 코드 9개) |
| 사용자 직접 확인 | 관리자 2단계 인증 등록·로그인·복구 코드 1회 사용, 비밀번호 변경 알림 메일, `testuser05` 토스 테스트 결제 2회(1회차 반영 후 포함, 모두 `paid`) | 정상 |
| Sentry | 테스트 이벤트 수신·Resolve, 4xx·네트워크 끊김 미전송, 비밀번호·쿠키·토큰·이메일·결제키 미전송, 수신 필터·Spike Protection | 정상 |
| Git 위생 | 미커밋 변경·모든 새 파일(untracked 전체)에 `.env`·비밀값 패턴·실제 관리자 경로·디버그 코드 없음, `git diff --check` | 정상 |

### 교차 검수 이력

검수 범위는 원격 `main`의 마지막 커밋 `861ccc8` 이후 미커밋 작업 트리 전체(`git diff 861ccc8`와 모든 untracked 파일)다. 검수 결과는 그대로 적용하지 않고 코드·테스트와 대조한 뒤 최소 범위로 반영한다.

**1회차 Codex 지적 → Claude 반영**

| 등급 | 지적 | 반영 |
|---|---|---|
| P1 | 토스의 처리 중·5xx 등 불확정 오류를 결제 실패로 확정하고 하루 뒤 삭제 | 확정 거절만 `failed`, 불확정은 즉시 조회 후 완료 또는 `pending` 유지(503 `PAYMENT_CONFIRMATION_PENDING`), 성공 응답도 주문번호·결제키·금액 검증, 결제키가 남은 주문은 미결제 확인 전 삭제 안 함 |
| P1 | Sentry 이벤트에 메일 링크 토큰·결제키·이메일 포함 가능 | 백엔드 `scrub_event`, 프런트 정리, 메일 발송 실패는 예외 종류만 기록 |
| P2 | 메일 링크 토큰 동시 사용, 오래된 이메일 변경 링크 재사용 | 회원 행 `FOR UPDATE`, 이메일 변경 토큰 `current_email` |
| P2 | 정리 작업이 외부 HTTP 동안 긴 트랜잭션 유지 | 정리(짧은 트랜잭션)와 결제사 조회(트랜잭션 밖)·주문별 반영 분리 |
| P2 | 요청 제한이 동시 요청에 원자적이지 않음 | 버킷 advisory lock으로 직렬화(실제 DB에서 10개 중 5개만 통과). 관리자 제한기는 보류 목록 |
| P2 | 관리자 MFA fail-open | `ADMIN_MFA_REQUIRED`(https 기본 true), 미등록·부분 설정 503 |
| P2 | 트랜잭션 풀러에서도 앱 연결 풀 유지 | 6543이면 `NullPool`, 5432는 풀 크기 명시 |
| P3 | MFA 입력칸 숫자 키패드 | `inputMode="text"`·대문자 자동 |

**2회차 Codex 지적 → Codex 직접 수정**: 토스 `ALREADY_PROCESSING_REQUEST` 등 불확정 분류, 승인 시도 시각(`payment_attempted_at`, 030) 기준 정리와 404 하루 유예, 불확정 결제 전용 '결제 결과 확인 중' 화면(`payment-result-state.js`, 같은 URL 재확인), 고객 로그인 실패 횟수 갱신 전 회원 행 잠금, 프런트 Sentry 이벤트 전체 문자열 정리(`sentry-scrub.js`), 결제 복구 시 이전 실패 사유 제거, 프런트 Node 테스트(`npm test`) 추가.

**3회차 Claude 재검증(2회차 수정 7항목 확인) + Codex 추가 지적 반영**

| 등급 | 문제 | 반영 |
|---|---|---|
| P1 (Codex) | 손상된 토스 200 응답(깨진 JSON·배열)이 `JSONDecodeError` 500 → 프런트 '결제 실패' 표시 | `toss._json_object`로 안전하게 읽고 200인데 객체가 아니면 `PAYMENT_RESPONSE_INVALID`(불확정)로 변환, 주문 서비스는 예상 못 한 예외도 결제사 조회로 처리, 오류 코드조차 없는 4xx는 확정 거절로 보지 않음, 결제 조회 응답이 깨지면 예외(다음 주기 재시도) |
| P1 (Claude 발견) | 2회차 프런트 Sentry 정리가 이벤트 전체를 재귀 정리하면서 `event_id`·`trace_id`·`release`(32자 이상 16진수)까지 `[Filtered]`로 바꿈 → 수집 거부·이슈 묶음·배포 버전 추적 실패 위험 | `SENTRY_ID_KEYS`(event_id, trace_id, span_id, parent_span_id, release, dist, debug_id, sid)는 정리하지 않음, 회귀 테스트 추가 |
| P2 (Codex) | 같은 세션의 동시 비밀번호 변경이 서로 덮어씀(lost update) | `_lock_and_confirm_password`: 시도 예약(커밋) → 회원 행 `FOR UPDATE`(`populate_existing`로 최신 값) → `auth_version`이 바뀌었으면 401(예약 삭제) → 잠근 최신 해시로 비밀번호 확인 → 성공 시도 기록 삭제(`discard_attempt`)를 계정 변경과 같은 커밋으로 반영. 비밀번호 변경·탈퇴 신청·이메일 변경 요청에 적용 |
| P2 (Codex) | 030 확인 스크립트가 미적용이어도 종료 코드 0 | 컬럼·인덱스 누락 또는 시도 시각 빈 행이 있으면 종료 코드 1, 컬럼이 없으면 `not_checked` 출력 |
| P3 (Codex) | 인계 문서와 작업 트리 불일치 | 이 절로 정리(파일 개수 고정 표기 제거, 030 미적용을 배포 차단 상태로 명시, 이전 설계 설명 교체) |
| P3 (Codex) | Ruff F·E9·B·ASYNC 6건 | 등록 스크립트 `input()`을 `asyncio.to_thread`로, `zip(strict=True)`, 테스트 람다 기본 인자 바인딩 |
| 개선 (Claude) | 030 백필이 결제 완료 주문까지 마이그레이션 시각으로 채움 | `COALESCE(paid_at, NOW())`로 결제 완료 주문은 승인 시각 사용(미적용 마이그레이션이라 수정) |

**4회차 Codex 전체 재검수 → Codex 직접 수정**

| 등급 | 문제 | 반영 |
|---|---|---|
| P1 | 토스 `DONE` 확인 뒤 주문 반영·커밋이 실패하면 일반 500으로 프런트가 이미 승인된 결제를 '실패'로 표시 | 외부 호출 뒤 주문 행을 다시 `FOR UPDATE`로 읽어 최신 상태·결제키를 검증하고, 결제 완료 반영과 응답 생성·커밋을 한 트랜잭션으로 처리. 실패하면 rollback·ERROR 로그 후 503 `PAYMENT_CONFIRMATION_PENDING`; 직접 승인·즉시 조회 복구 양쪽의 최종 커밋 실패 테스트 추가 |
| P2 | 프런트 Sentry 식별자 키 예외가 객체 전체에 적용돼 `extra.sid` 같은 임의 데이터의 JWT도 정리를 우회 | 실제 Sentry 스키마 경로의 식별자만 보존하고 같은 키 이름의 임의 중첩 데이터는 정리, 회귀 테스트 추가 |
| P2 | 상품은 0~약 10조 원을 허용하지만 결제 확인은 1~약 21억 원만 허용해 생성 가능한 주문이 승인 단계에서 422 | 카드 결제 금액 공통 범위(100~2,147,483,647원)를 백엔드 상품 입력·주문 생성·승인 스키마와 관리자 프런트 입력에 통일, 경계 테스트 추가. 현재 상품 30건은 모두 범위 안임 |

- 확인만 하고 고치지 않은 점: 실제 PostgreSQL 두 세션으로 동시 비밀번호 변경을 재현하는 통합 테스트는 운영 겸용 DB에 테스트 계정을 만들어야 해 하지 않았다(행 잠금 순서·버전 재확인은 단위 테스트로 검증).
- DB 변경·롤백: 029(관리자 MFA 컬럼), 030(`orders.payment_attempted_at`·인덱스) 모두 적용 완료. 030 롤백은 코드를 먼저 되돌린 뒤 인덱스·컬럼 제거.
- 관련 테스트: `AccountSecurityHardeningTests`, `PaymentReconciliationTests`, `RefreshRowLockTests`, `AdminMfaTests`, `TokenFlowLockTests`, `PasswordChangeLockTests`, `GuardFailuresTests`(이상 `test_security_and_schemas.py`), `test_api_routes.py`, `test_monitoring.py`, `test_product_schemas.py`, 프런트 `sentry-scrub.test.js`, `payment-result-state.test.js`.

## Claude Code와 Codex 역할 분담

Claude Code가 기본 구현과 일상적인 수정·테스트·Git 작업을 담당한다. 사용자는 다음처럼 교차 검증 가치가 큰 변경에서 Codex를 검수용으로 사용할 예정이다.

- 인증·인가와 관리자/고객 토큰 경계 변경
- 비밀번호, 잠금, 탈퇴, 계정 복구 정책 변경
- 기존 데이터에 영향을 주는 DB 마이그레이션
- 상품 삭제·복원·감사 로그·관련 상품 무결성
- Supabase Storage 이동·삭제·임시 이미지 정리
- 장바구니·주문·결제처럼 여러 도메인에 걸친 주요 기능
- 대규모 라우팅 또는 상태 관리 변경
- 배포 전 보안 검수

교차 검증 요청 전 Claude Code가 준비할 내용:

1. 변경 목적과 지켜야 할 기존 정책
2. 변경 파일 목록과 핵심 설계 선택
3. DB 변경 및 롤백 방법
4. 실행한 테스트와 결과
5. 특히 불확실하거나 반례 검토가 필요한 지점

Codex 검수 결과는 무조건 적용하지 않고 기존 요구사항·실제 코드·테스트 결과와 대조한다. 검수에서 문제가 확인되면 Claude Code가 최소 범위로 수정하고 전체 검증을 다시 실행한다.

## 작업 종료 체크리스트

1. `git status`로 사용자 변경과 생성 파일 확인
2. 사용되지 않는 파일은 import·문서·마이그레이션 이력을 모두 확인한 뒤에만 삭제
3. 백엔드 테스트와 `compileall` 실행
4. 프런트 린트와 빌드 실행
5. DB 변경 시 읽기 전용 검수 스크립트 실행
6. 환경파일·비밀값·빌드 산출물 미포함 확인
7. `CLAUDE.md`의 구현 상태·테스트 개수·다음 작업 갱신
8. 터미널 Git 명령으로 커밋·푸시
