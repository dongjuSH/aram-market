# Product Management 개발 인수인계

## 이 문서의 목적

이 문서는 Claude Code가 현재 작업을 바로 이어가기 위한 기준 문서다. 작업을 시작할 때 전체를 먼저 읽고, 실제 코드와 충돌하면 추측하지 말고 코드·DB 읽기 결과를 기준으로 이 문서를 함께 갱신한다.

사용자는 React와 FastAPI의 동작을 직접 이해하면서 구현하는 것이 목표다. 요청하지 않은 전체 코드 생성이나 대규모 구조 변경은 피하고, 기존 코드 기준으로 원인과 개념을 먼저 설명한 뒤 필요한 범위만 수정한다. 새로운 폴더·계층·라이브러리는 실제 필요가 생겼을 때 먼저 제안한다.

## 현재 기준 상태

2026-09-29 기준 구현 범위(금일 작업 종료 시점):

- 고객용 아람 마켓 상품 목록과 상품 상세 페이지
- 고객 회원가입(비밀번호 확인, 이메일 소유 인증, 약관 버전·동의 이력), 로그인(이전 화면 복귀), 아이디 찾기, 비밀번호 재설정, 마이페이지
- 고객·관리자 인증 토큰은 HttpOnly 쿠키로만 전달(JS·sessionStorage에 토큰 없음). 고객·관리자 모두 접근 토큰+리프레시 토큰(회전·재사용 탐지) 사용
- 고객 비밀번호 변경, 마케팅 수신 동의 변경, 7일 유예 회원 탈퇴·복구
- 고정 아이디 `admin` 한 개만 사용하는 관리자 로그인
- 관리자 상품 목록·검색·등록·수정·소프트 삭제·복원
- 고객 장바구니(로그인 시 DB 저장), 찜 목록(마이 페이지), 토스페이먼츠 테스트 결제(주문 생성·서버 승인·주문 내역)
- 상품 후기(구매 고객만)·문의(로그인 고객, 비밀글, 관리자 답변)
- 주문서(배송지 입력)·배송 상태(결제완료 → 상품준비중 → 배송중 → 배송완료, 관리자 변경)·마이 페이지 배송 현황
- 고객 헤더: 상단 회원가입·로그인(로그인 시 닉네임·로그아웃), 우측 찜 목록·장바구니·마이 페이지 아이콘(컬리 방식)
- 관리자 화면: 상품 관리·주문 관리·문의 관리(현재 화면을 제외한 나머지 메뉴만 표시)
- Supabase PostgreSQL 및 Supabase Storage 연결
- 상품 변경 감사 로그와 이미지 임시 업로드 정리

실제 Supabase 상태:

- `admin_accounts`: 활성 `admin` 계정 1건
- `users`: 테스트 회원 5건(`testuser01~05`), `marketing_consent`·`email_verified_at`·`email_verification_sent_at` 컬럼 적용 완료(기존 회원은 인증 완료 처리)
- `user_policy_consents`: 약관 종류·버전·동의 여부·시각 이력(기존 회원은 v1.0 이력 백필)
- `products`: 총 30건(활성 29건, 삭제 1건)이며 소프트 삭제 상품도 보존
- 마이그레이션 017~024로 추가된 테이블: `user_refresh_tokens`, `admin_refresh_tokens`, `rate_limit_events`, `cart_items`, `wishlist_items`, `orders`(배송 컬럼 포함), `order_items`, `product_reviews`, `product_inquiries` (모두 적용 완료, 검수 스크립트로 확인)
- 상품 대표·상세 이미지는 모두 새 Storage 경로로 이전 완료
- `products.image_data`, 상품 관리자 ID, 감사 로그 관리자 ID 같은 중복 컬럼 제거 완료

자동 검증 기준:

- 백엔드 단위 테스트 74개 통과
- Python `compileall` 통과
- 프런트 `oxlint` 통과
- Vite 프로덕션 빌드 통과

## 작업 원칙

- 파일명은 kebab-case, React 컴포넌트 함수명은 PascalCase를 사용한다. Vite 기본 `App.jsx`, `main.jsx`는 유지한다.
- 파일 첫 줄에는 역할을 설명하는 한 줄 주석을 둔다.
- 함수·클래스 설명은 선언 바로 위의 짧은 `#` 주석으로 작성한다.
- 사용자가 만든 변경을 임의로 되돌리거나 구조를 크게 바꾸지 않는다.
- 진단 요청은 원인과 근거만 제시하고, 수정 요청이 있을 때 구현한다.
- DB 스키마 변경은 SQL 마이그레이션과 적용 스크립트를 함께 추가하며 기존 데이터를 먼저 확인한다.
- `Base.metadata.create_all()`은 기존 테이블을 변경하지 않으므로 마이그레이션을 대신할 수 없다.
- 상품·계정 삭제는 현재 정책에 맞는 소프트 삭제 또는 유예 삭제를 사용하고 직접 영구 삭제하지 않는다.
- 더 이상 쓰이지 않는 코드·CSS는 작업할 때마다 제거한다(재사용 가능성이 있으면 삭제 전에 사용자에게 확인). 마이그레이션 이력과 관리·검수 스크립트는 삭제하지 않는다.
- 문서가 바뀌면 루트 `CLAUDE.md`만 갱신한다. 별도 README를 임의로 추가하지 않는다.

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
- 인증: PBKDF2-SHA256 비밀번호 해시, 표준 JWT(HS256, PyJWT: `iss`·`aud`=토큰 용도·`sub`·`iat`·`exp`·`jti`, 알고리즘 서버 고정) 접근 토큰을 HttpOnly 쿠키(`user_access_token`, `admin_access_token`, Path=/api)로 전달. 리프레시 토큰은 무작위 불투명 값이며 고객은 `user_refresh_token`(Path=/api/users), 관리자는 `admin_refresh_token`(Path=/api/admins) 쿠키로만 전달하고 DB에는 SHA-256 해시만 저장
- 메일: SMTP, HTML·텍스트 멀티파트
- 메일 종류: 아이디 안내, 비밀번호 재설정, 계정 잠금 해제, 가입 이메일 인증. SMTP 연결·인증(`scripts/check_smtp.py`)과 잠금 해제·가입 인증 메일의 실제 발송·링크 동작은 사용자가 기능 구현 시 직접 테스트해 정상 확인함
- 시간대: DB 요청과 프런트 표시 모두 `Asia/Seoul`
- 오류 응답: 모든 오류는 RFC 9457 Problem Details(`application/problem+json`)로 통일한다(`core/problems.py`). 필드: `type`(`/problems/{code-kebab}`), `title`, `status`, `detail`(화면에 그대로 보여줄 한국어 안내), `code`(프런트 분기용 안정 코드), `instance`, 추가 정보(`retry_after`, `recovery_token`, `email`, 입력 오류의 `errors[{field,message}]`)는 최상위 확장 필드. 입력 검증 오류는 422 `VALIDATION_ERROR`이며 메시지는 한국어로 변환한다. 프런트는 `api/http.js`의 `normalizeError`가 `detail`→`message`로 읽는다. 서버에서 새 오류를 만들 때는 `api_error(status, code, message, **extra)`만 사용한다
- 요청 제한: DB(`rate_limit_events`, IP·이메일은 HMAC 해시) 슬라이딩 윈도우. Redis 등 별도 인프라는 쓰지 않는다

## 주요 구조

```text
product-management/
├─ backend/
│  ├─ main.py
│  ├─ migrations/                 # 001~024 스키마 변경 이력
│  ├─ scripts/                    # 마이그레이션·검수·관리 스크립트
│  ├─ tests/
│  └─ src/backend/
│     ├─ core/                    # 설정, DB, 토큰·비밀번호 보안
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

백엔드와 프런트를 서로 다른 터미널에서 실행한다.

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
- API 문서: `http://127.0.0.1:8000/docs`
- 관리자 화면: 로컬 `VITE_ADMIN_BASE_PATH` 뒤에 `/login`

프런트는 API를 같은 출처 `/api`로 호출하고 Vite 개발 서버가 `http://127.0.0.1:8000`으로 프록시한다(쿠키가 `localhost:5173` 출처로 저장되도록). 배포 시에도 리버스 프록시로 프런트와 `/api`를 같은 출처에 둔다.

`frontend/.env.local`에 `/`로 시작하는 12자 이상의 `VITE_ADMIN_BASE_PATH`가 없으면 프런트가 의도적으로 시작·빌드되지 않는다. 실제 경로는 문서나 커밋에 남기지 않는다.

## 환경변수

실제 백엔드 값은 Git 제외 대상인 `backend/.env`, 관리자 프런트 경로는 `frontend/.env.local`에 둔다.

백엔드 주요 변수:

- `DATABASE_URL`
- `AUTH_SECRET_KEY`: 최소 32자
- `ACCESS_TOKEN_EXPIRE_MINUTES`: 접근 토큰 유효시간(기본 15분. 로컬 `backend/.env`에는 과거 값이 남아 있을 수 있음)
- `ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES`(기본 15; 고객 `ACCESS_TOKEN_EXPIRE_MINUTES`와 별개 설정), `ADMIN_REFRESH_TOKEN_EXPIRE_HOURS`(기본 12, 관리자 로그인 유지 최대시간)
- `REFRESH_TOKEN_EXPIRE_DAYS`(기본 14, 로그인 유지 최대기간), `REFRESH_REUSE_GRACE_SECONDS`(기본 10, 동시 탭 재발급 경합 유예)
- `UNLOCK_TOKEN_EXPIRE_MINUTES`
- `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`
- `WITHDRAWAL_GRACE_DAYS`: 현재 7일
- `WITHDRAWAL_RETENTION_DAYS`: 현재 0일
- `BACKEND_PUBLIC_URL`, `FRONTEND_URL`
- `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES`(기본 1440, 미인증 계정 보관시간), `EMAIL_VERIFICATION_RESEND_SECONDS`(기본 60)
- `TOSS_SECRET_KEY`: 토스페이먼츠 시크릿 키(서버 전용, 현재 문서용 테스트 키 `test_sk_...`, 실제 결제 없음), `TOSS_API_BASE`(기본 https://api.tosspayments.com). 프런트 `frontend/.env.local`의 `VITE_TOSS_CLIENT_KEY`(공개 클라이언트 키, 테스트 `test_ck_...`). 운영 전 실제 가맹점 키로 교체하며 시크릿 키는 절대 Git에 올리지 않는다
- `TRUSTED_PROXY_IPS`: X-Forwarded-For를 신뢰할 리버스 프록시 IP·대역(쉼표 구분, 기본 빈 값=직접 접속 IP만 사용). 프록시 뒤에 배포하면 반드시 설정
- `AUTH_COOKIE_SECURE`(기본: `FRONTEND_URL`이 https이면 true), `AUTH_COOKIE_SAMESITE`(기본 lax; none은 Secure 필수)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `SMTP_USE_TLS`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`

## 라우팅

고객 화면:

- `/`: 상품 목록, 검색, 카테고리, 페이지네이션. 카테고리 메뉴를 누르면 검색어가 초기화되고 검색은 항상 전체 상품에서 수행한다. 페이지를 넘기면 목록 제목이 보이도록 스크롤하고 첫 번째 상품에 포커스를 둔다
- `/products/{id}`: 변경되지 않는 내부 상품 ID 기반 상세
- `/products`: 기존 주소 호환용으로 `/` 이동
- `/products/detail?id={id}`: 기존 주소 호환용으로 `/products/{id}` 이동
- `/user/login`: 고객 로그인과 아이디·비밀번호 찾기
- `/user/signup`: 고객 회원가입
- `/user/reset-password?token=...`: 이메일 토큰 기반 재설정
- `/user/verify-email?token=...`: 가입 이메일 인증 확인
- `/user/login?next=...`: 로그인 후 `next`(고객 화면만 허용, `getSafeRedirectPath`)로 복귀. 장바구니 화면을 만들면 `config/routes.js`의 허용 목록에 추가
- `/user`: 로그인 고객 마이페이지(`?section=wishlist`이면 찜한 상품 구역으로 스크롤)
- `/cart`: 장바구니(로그인 없이 조회·수정 가능, 주문하기는 로그인 필요)
- `/user/unlock?token=...`: 잠금 해제 메일 링크. 화면의 버튼을 눌러야 POST로 해제
- `/checkout`: 주문서(주문 상품 확인·배송지 입력·결제하기, 로그인 필요). 상세 '구매하기'와 장바구니 '주문하기'가 주문 초안을 `sessionStorage`에 저장하고 이 화면으로 이동한다(로그아웃·세션 만료 시 초안 삭제)
- `/payment/success?paymentKey&orderId&amount`: 결제창 성공 리다이렉트(로그인 필요, 서버 승인 후 결과 표시), `/payment/fail`: 결제 실패·취소 안내

관리자 화면:

- `${VITE_ADMIN_BASE_PATH}/inquiries`: 상품 문의 답변 관리
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

정책:

- 아이디는 영문·숫자·밑줄 4~20자이며 소문자로 정규화한다.
- 비밀번호는 영문·숫자·특수문자를 포함한 8~64자다.
- 비밀번호 5회 실패 시 1시간 잠그고 SMTP 설정 시 잠금 해제 메일을 보낸다.
- 존재하지 않는 아이디·오류 비밀번호·잠긴 계정은 같은 `INVALID_CREDENTIALS` 응답을 사용한다.
- 고객 토큰 용도는 `user_access`이며 `admin_access`와 교차 사용할 수 없다.
- 토큰은 로그인 응답 본문에 넣지 않고 HttpOnly 쿠키로만 발급한다. 프런트는 토큰 대신 `localStorage.userCurrentUser`(id·닉네임 표식)로 로그인 표시만 하며 실제 인증은 서버가 쿠키로 검증한다. 로그아웃은 `POST /api/users/signout`.
- CSRF는 SameSite 쿠키(기본 lax)와 JSON 요청·CORS 허용 출처 제한에 의존한다. 별도 CSRF 토큰은 없으므로 SameSite를 none으로 바꾸려면 CSRF 토큰을 먼저 도입한다.
- 회원가입은 `password_confirm` 일치 검증(프런트·서버 모두)과 `policy_versions`(화면이 동의한 약관 버전) 검증을 거친다. 약관 본문·버전은 `services/policies.py`가 관리하며 본문을 바꾸면 버전을 올린다.
- 동의·철회 이력은 `user_policy_consents`에 행을 추가해 남긴다(가입 시 service/privacy/marketing, 마이페이지 마케팅 변경 시 marketing).
- 가입 직후 이메일 인증 링크(`user_email_verify` 토큰, 24시간)를 보내며 인증 전에는 올바른 비밀번호여도 `EMAIL_NOT_VERIFIED`로 로그인할 수 없다. 재발송은 60초 간격이며 응답은 계정 존재 여부를 숨긴다.
- 인증 유효시간이 지난 미인증 계정은 가입 시점·매시간 정리 작업에서 삭제되어 아이디·이메일 선점을 막는다. 아이디 찾기·비밀번호 재설정은 인증된 이메일에만 발송한다.
- 로그인 시 접근 토큰(짧은 수명)과 리프레시 토큰을 함께 HttpOnly 쿠키로 발급한다. 접근 토큰이 만료되면 프런트 `api/user-auth.js`의 `request`가 `POST /api/users/token/refresh`로 재발급한 뒤 원래 요청을 1회 재시도한다(동시 요청은 재발급 1회로 합침).
- 리프레시 토큰은 사용할 때마다 새 값으로 회전하고 이전 값은 폐기한다(`user_refresh_tokens`, 로그인 1회 = family 1개). 이미 폐기된 토큰을 유예시간(10초) 뒤에 다시 쓰면 탈취로 보고 그 family를 전부 폐기한다. 유예시간 안의 재사용은 `REFRESH_IN_PROGRESS`로만 거부하고 쿠키는 지우지 않는다.
- 접근 토큰에는 `sid`(로그인 세션 = 리프레시 family)가 들어 있고 서버가 요청마다 해당 세션이 폐기·만료되지 않았는지 DB로 확인한다. 로그아웃·비밀번호 변경·탈퇴 즉시 기존 접근 토큰도 401이 된다(요청마다 조회 1회 비용).
- 비밀번호 변경·재설정·탈퇴 신청은 `auth_version`을 올리고 해당 회원의 모든 리프레시 토큰을 폐기한다. 로그아웃은 해당 로그인 세션(family)을 폐기한다. 만료 후 하루 지난 행은 매시간 정리 작업이 삭제한다.
- 비밀번호 변경·재설정 후 `auth_version`을 증가시켜 기존 토큰을 무효화한다.
- 탈퇴 요청은 `pending_deletion`으로 바꾸고 7일 이내 로그인 시 복구할 수 있다.
- FastAPI lifespan 작업(`main.py`의 `run_cleanup_once`)이 매시간 만료 고객 계정·미인증 계정·만료 리프레시 토큰·요청 제한 기록을 한 트랜잭션으로 정리한다. Postgres `pg_try_advisory_xact_lock`으로 서버가 여러 대여도 한 대만 실행한다.
- 요청 제한(`core/rate_limit.py`): 로그인 실패는 접속 IP당 15분에 20회(공용 IP를 고려해 넉넉하게, 올바른 로그인은 세지 않음), 메일 발송 요청(가입·재발송·아이디 찾기·비밀번호 재설정)은 IP당 시간당 15회·대상 이메일당 시간당 5회, 가입은 IP당 시간당 10회다. 초과 시 429 `RATE_LIMITED`와 `Retry-After`. 토큰 확인 계열(재발급·이메일 인증 확정·비밀번호 재설정 확정·잠금 해제·탈퇴 취소, 관리자 재발급은 별도 버킷)은 접속 IP당 15분에 4xx 실패 30회까지이며 정상 요청과 동시 탭 경합(`REFRESH_IN_PROGRESS`)은 세지 않는다. 접속 IP는 `core/client_ip.py`가 `TRUSTED_PROXY_IPS`에 든 프록시가 붙인 `X-Forwarded-For`에서만 계산한다.
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
| `DELETE` | `/api/users/me` | 7일 유예 탈퇴 신청 |
| `POST` | `/api/users/withdrawal/cancel` | 탈퇴 취소 |

장바구니: 로그인 고객은 서버 DB(`cart_items`, 가격은 저장하지 않고 조회 시 현재 상품 가격·이름·이미지 사용, 판매 종료 상품은 목록에서 제외, 삭제 전까지 유지)에 저장하고, 비로그인은 브라우저 메모리에만 있어 새로고침하면 초기화된다. 로그인 직후 비로그인 장바구니는 `POST /api/cart/merge`로 계정에 합쳐지고 로그아웃하면 화면 상태를 비운다(`features/cart/shopping-store.js`). 찜(♡)은 장바구니와 별개 기능이며 현재는 상품 상세 화면에서만 할 수 있다(상세 개편 때 카드 위치 재검토). 로그인 고객만 상세 화면의 ♡로 찜할 수 있고(`wishlist_items`, 삭제 전까지 유지) 비로그인이면 "로그인 후 이용" 안내와 로그인 버튼을 띄운다. 찜한 상품은 마이 페이지 '찜한 상품'에서 보고 장바구니 담기·찜 해제를 할 수 있다. API: `GET /api/wishlist`, `PUT`·`DELETE /api/wishlist/{product_id}`.

### 고객 헤더

- `components/products/catalog-header.jsx`: 상단 한 줄에 비로그인이면 `회원가입 | 로그인`, 로그인이면 `{닉네임}님 | 로그아웃`(마이 페이지를 거치지 않고 바로 로그아웃). 주 줄 우측에 아이콘 버튼 `찜 목록`(비로그인이면 로그인 후 마이 페이지 찜 구역으로 이동)·`장바구니`(담긴 상품 종류 수 배지)·`마이 페이지`(로그인 시에만). 로그인·회원가입 화면(`hideLogin`)에서는 비로그인 상단 링크를 숨긴다.

### 후기·문의

- 후기: 해당 상품을 `paid` 주문으로 산 로그인 고객만 작성(서버가 주문 내역으로 확인, 미구매 403 `REVIEW_NOT_PURCHASED`). 고객당 상품 1건이며 본인 후기만 수정·삭제한다. 별점 1~5, 내용 10~1000자. 작성자는 닉네임 첫 글자만 보이고 탈퇴 회원은 '탈퇴한 회원'으로 표시한다. 목록·평점 요약(개수·평균·최근 6개월 평균)은 비로그인도 조회할 수 있고 상세 상단 별점·탭 개수에 그대로 쓴다. API: `GET/POST /api/products/{id}/reviews`, `GET /api/products/{id}/reviews/eligibility`, `PUT/DELETE /api/reviews/{id}`.
- 문의: 로그인 고객 누구나 작성(5~1000자, 비밀글 선택), 본인 문의만 삭제. 비밀글은 작성자 본인에게만 내용·답변이 보이고 다른 사람에게는 '비밀글입니다.'로 표시한다. 관리자는 `/inquiries` 화면(`GET /api/admin/inquiries`, `PUT /api/admin/inquiries/{id}/answer`)에서 전체 내용을 보고 답변한다. 작성은 IP당 시간당 20회로 제한한다.
- 후기·문의 내용은 텍스트로만 렌더링한다(HTML 미허용).
- 배송·교환·반품·환불 안내 문구는 `frontend/src/config/shop-policy.js`에 있으며 포트폴리오용 테스트 사이트라는 유의사항을 포함한다.

### 주문·결제(토스페이먼츠 테스트 모드)

- 흐름: 상세 '구매하기' 또는 장바구니 '주문하기'(로그인 필요) → 주문서(`/checkout`)에서 배송지 입력 → `POST /api/orders`(배송지 포함, 미입력·형식 오류 422)가 상품 가격을 서버에서 다시 조회해 금액을 계산하고 `pending` 주문(주문번호 `ARAM-YYYYMMDD-...`)을 만든다 → 프런트가 토스 결제창(SDK `https://js.tosspayments.com/v2/standard`, `features/checkout/toss-payments.js`)을 연다 → 성공 시 `/payment/success`가 `POST /api/orders/confirm`으로 서버 승인 요청 → 서버가 주문의 본인 여부·금액 일치를 확인하고 토스 승인 API(`/v1/payments/confirm`, 주문번호를 `Idempotency-Key`로 사용)를 호출해 `paid`로 바꾸며, 장바구니에서 주문했으면 해당 상품만 장바구니에서 제거한다.
- 금액·상품명은 클라이언트 값을 믿지 않는다. 금액 불일치는 주문을 `failed`로 바꾸고 거부한다. 같은 결제 승인 요청을 다시 보내도(새로고침) 이미 `paid`이고 `payment_key`가 같으면 같은 결과를 돌려준다.
- 주문 테이블은 가격·상품명·이미지 스냅샷을 저장하고, 회원·상품이 삭제돼도 거래 기록이 남도록 `ON DELETE SET NULL`이다. 결제하지 않은 `pending`·`failed` 주문은 하루 뒤 정리 작업이 삭제한다. 주문 생성은 IP당 시간당 30회로 제한한다.
- 마이 페이지 '주문한 제품'은 `GET /api/orders`의 결제 완료 주문을 표시한다.
- 배송: 결제 승인 시 `delivery_status=paid`(결제완료)이며 관리자가 주문 관리 화면(`GET /api/admin/orders`, `PUT /api/admin/orders/{order_number}/delivery-status`)에서 상품준비중 → 배송중 → 배송완료로 **한 단계씩만** 변경한다(건너뛰기·되돌리기 409 `INVALID_DELIVERY_TRANSITION`). 배송중·배송완료 시각을 기록하고 마이 페이지 주문 내역에 4단계 진행 표시와 배송지를 보여준다. 실제 택배사·송장 연동은 없다(포트폴리오용 더미 배송). 배송지 입력 기능 이전 주문은 배송지가 없다.
- 아직 없는 것: 환불·결제 취소 API, 재고 관리, 토스 웹훅(결제창 이탈 후 승인 누락 보정), 영수증. 실제 결제 전 이 항목과 전자상거래법상 거래기록 보관 정책을 설계한다.

## 단일 관리자 인증

`public.admin_accounts`에는 `id`, 고정 `username=admin`, `password`, `created_at`, `is_active`, `auth_version`만 유지한다.

- 관리자 토큰 용도는 `admin_access`다. 로그인 시 접근 토큰(15분)과 리프레시 토큰(12시간, 회전·재사용 탐지, `admin_refresh_tokens`)을 HttpOnly 쿠키로 발급하고 프런트 `api/auth.js`의 `request`가 만료 시 `POST /api/admins/token/refresh`로 재발급 후 1회 재시도한다. 관리자 비밀번호 재설정(`auth_version` 증가)이나 계정 비활성화 시 기존 리프레시 토큰은 무효가 된다.
- 관리자 비밀번호는 채팅·소스·환경파일에 넣지 않고 `scripts/create_admin.py`의 `getpass`로 생성·재설정한다.
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
| `POST` | `/api/admins/signin` | 관리자 로그인 |
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
- 상세 HTML은 서버 허용 목록으로 다시 정리한다.
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
.\.venv\Scripts\python.exe scripts\check_admin_refresh_tokens.py
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

- **CORS**: `backend/main.py`의 `allow_origins`에 `http://localhost:5173`, `http://127.0.0.1:5173`이 고정돼 있다. 로컬 개발 중에는 유지하고, 배포 직전에 환경변수(예: `CORS_ORIGINS`)로 옮겨 실제 도메인만 허용한다.
- **프록시**: 리버스 프록시 뒤에 배포하면 `TRUSTED_PROXY_IPS`에 프록시 IP·대역을 넣어야 로그인 제한·메일 제한이 실제 접속자 IP 기준으로 동작한다(비우면 모든 사용자가 프록시 IP 하나로 보임). 프록시는 `X-Forwarded-For`를 덧붙이는 방식이어야 하며 배포 환경에서 로그인 제한이 사용자별로 걸리는지 확인한다.
- `AUTH_COOKIE_SECURE=true`(https), `TRUSTED_PROXY_IPS`(리버스 프록시 IP), `ACCESS_TOKEN_EXPIRE_MINUTES`(권장 15) 확인.
- 로컬 `backend/.env`에 과거 값(`ACCESS_TOKEN_EXPIRE_MINUTES=60`)이 남아 있을 수 있다.
- 토스페이먼츠 실제 키로 교체, 결제 성공·실패 URL이 실제 도메인인지 확인.
- `AUTH_SECRET_KEY`를 바꾸면 발급된 모든 토큰·메일 링크가 무효가 된다.

## 다음 작업 후보와 미구현 범위

- 결제는 토스페이먼츠 테스트 키로만 연동돼 있다. 환불·재고·웹훅이 없다.
- 후기 사진 첨부·도움돼요·신고·관리자 후기 삭제 기능이 없다.
- 관리자 MFA가 없다. 관리자 계정을 여러 명이 공유하게 되면 계정 분리(감사 로그의 수행자 기록 복구)와 MFA를 먼저 도입한다. 기기별 로그인 세션은 이미 독립적이다.
- 계정 잠금(5회 실패 1시간)은 아이디만 알면 남이 일부러 잠글 수 있다. IP 제한은 이를 완화할 뿐 막지 못한다.
- 리프레시 쿠키 Path는 `/api/users`다. 배포 시 API 접두사가 바뀌면 함께 바꾼다.
- 관리자 비공개 경로는 배포 보안 수단이 아니므로 WAF·MFA가 필요하다. 배포 시 `AUTH_COOKIE_SECURE=true`(https) 확인이 필요하다.
- SPA 배포 서버는 `/products/{id}`, `/user/*`, 관리자 비공개 경로를 `index.html`로 fallback해야 한다.
- 상품 상세 화면은 대대적으로 개편할 예정이다. 이때 찜 UI(♡ 위치)도 함께 정리한다. 목록 카드는 이미지 아래 전폭 '담기' 버튼(컬리 방식)이다.

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
