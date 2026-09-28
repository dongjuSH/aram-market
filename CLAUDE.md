# Product Management 개발 인수인계

## 이 문서의 목적

이 문서는 Claude Code가 현재 작업을 바로 이어가기 위한 기준 문서다. 작업을 시작할 때 전체를 먼저 읽고, 실제 코드와 충돌하면 추측하지 말고 코드·DB 읽기 결과를 기준으로 이 문서를 함께 갱신한다.

사용자는 React와 FastAPI의 동작을 직접 이해하면서 구현하는 것이 목표다. 요청하지 않은 전체 코드 생성이나 대규모 구조 변경은 피하고, 기존 코드 기준으로 원인과 개념을 먼저 설명한 뒤 필요한 범위만 수정한다. 새로운 폴더·계층·라이브러리는 실제 필요가 생겼을 때 먼저 제안한다.

## 현재 기준 상태

2026-09-29 기준 구현 범위:

- 고객용 아람 마켓 상품 목록과 상품 상세 페이지
- 고객 회원가입, 로그인, 아이디 찾기, 비밀번호 재설정, 마이페이지
- 고객 비밀번호 변경, 마케팅 수신 동의 변경, 7일 유예 회원 탈퇴·복구
- 고정 아이디 `admin` 한 개만 사용하는 관리자 로그인
- 관리자 상품 목록·검색·등록·수정·소프트 삭제·복원
- Supabase PostgreSQL 및 Supabase Storage 연결
- 상품 변경 감사 로그와 이미지 임시 업로드 정리

실제 Supabase 상태:

- `admin_accounts`: 활성 `admin` 계정 1건
- `users`: 4건, `marketing_consent` 컬럼 적용 완료
- `products`: 총 30건(활성 29건, 삭제 1건)이며 소프트 삭제 상품도 보존
- 상품 대표·상세 이미지는 모두 새 Storage 경로로 이전 완료
- `products.image_data`, 상품 관리자 ID, 감사 로그 관리자 ID 같은 중복 컬럼 제거 완료

자동 검증 기준:

- 백엔드 단위 테스트 31개 통과
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
- 인증: PBKDF2-SHA256 비밀번호 해시, HMAC 서명 토큰
- 메일: SMTP, HTML·텍스트 멀티파트
- 시간대: DB 요청과 프런트 표시 모두 `Asia/Seoul`

## 주요 구조

```text
product-management/
├─ backend/
│  ├─ main.py
│  ├─ migrations/                 # 001~015 스키마 변경 이력
│  ├─ scripts/                    # 마이그레이션·검수·관리 스크립트
│  ├─ tests/
│  └─ src/backend/
│     ├─ core/                    # 설정, DB, 토큰·비밀번호 보안
│     └─ domain/
│        ├─ admins/               # 단일 관리자 인증
│        ├─ products/             # 관리자 CRUD와 고객 공개 조회
│        └─ users/                # 고객 인증·계정 생명주기
├─ frontend/
│  ├─ public/                     # favicon, 브랜드 SVG, 카탈로그 히어로 이미지
│  └─ src/
│     ├─ api/                     # 관리자·고객·상품 API 호출
│     ├─ components/              # 공통, 상품, 고객 레이아웃
│     ├─ config/routes.js         # 공개·고객·비공개 관리자 경로
│     ├─ features/user-auth/      # 고객 인증과 마이페이지
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

`frontend/.env.local`에 `/`로 시작하는 12자 이상의 `VITE_ADMIN_BASE_PATH`가 없으면 프런트가 의도적으로 시작·빌드되지 않는다. 실제 경로는 문서나 커밋에 남기지 않는다.

## 환경변수

실제 백엔드 값은 Git 제외 대상인 `backend/.env`, 관리자 프런트 경로는 `frontend/.env.local`에 둔다.

백엔드 주요 변수:

- `DATABASE_URL`
- `AUTH_SECRET_KEY`: 최소 32자
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `UNLOCK_TOKEN_EXPIRE_MINUTES`
- `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`
- `WITHDRAWAL_GRACE_DAYS`: 현재 7일
- `WITHDRAWAL_RETENTION_DAYS`: 현재 0일
- `BACKEND_PUBLIC_URL`, `FRONTEND_URL`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `SMTP_USE_TLS`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`

## 라우팅

고객 화면:

- `/`: 상품 목록, 검색, 카테고리, 페이지네이션
- `/products/{id}`: 변경되지 않는 내부 상품 ID 기반 상세
- `/products`: 기존 주소 호환용으로 `/` 이동
- `/products/detail?id={id}`: 기존 주소 호환용으로 `/products/{id}` 이동
- `/user/login`: 고객 로그인과 아이디·비밀번호 찾기
- `/user/signup`: 고객 회원가입
- `/user/reset-password?token=...`: 이메일 토큰 기반 재설정
- `/user`: 로그인 고객 마이페이지

관리자 화면:

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
- 비밀번호 변경·재설정 후 `auth_version`을 증가시켜 기존 토큰을 무효화한다.
- 탈퇴 요청은 `pending_deletion`으로 바꾸고 7일 이내 로그인 시 복구할 수 있다.
- FastAPI lifespan 작업이 매시간 만료 고객 계정을 정리한다. 다중 프로세스·다중 서버 배포 전에는 별도 스케줄러나 단일 작업자로 옮겨야 한다.
- 마케팅 수신 동의는 회원가입과 마이페이지에서 변경할 수 있다.

고객 API:

| 방식 | 경로 | 기능 |
|---|---|---|
| `POST` | `/api/users/signup` | 회원가입 |
| `POST` | `/api/users/signin` | 로그인 |
| `POST` | `/api/users/find-username` | 아이디 안내 메일 요청 |
| `POST` | `/api/users/password-reset/request` | 재설정 메일 요청 |
| `POST` | `/api/users/password-reset/confirm` | 새 비밀번호 저장 |
| `GET` | `/api/users/unlock` | 잠금 해제 메일 링크 |
| `GET` | `/api/users/me` | 현재 고객 조회 |
| `PUT` | `/api/users/me/password` | 비밀번호 변경 |
| `PUT` | `/api/users/me/marketing-consent` | 마케팅 동의 변경 |
| `DELETE` | `/api/users/me` | 7일 유예 탈퇴 신청 |
| `POST` | `/api/users/withdrawal/cancel` | 탈퇴 취소 |

현재 마이페이지의 주문 내역과 헤더 장바구니는 UI만 구현되어 있다. 실제 장바구니·주문 테이블과 API는 아직 없다.

## 단일 관리자 인증

`public.admin_accounts`에는 `id`, 고정 `username=admin`, `password`, `created_at`, `is_active`, `auth_version`만 유지한다.

- 관리자 토큰 용도는 `admin_access`다.
- 관리자 비밀번호는 채팅·소스·환경파일에 넣지 않고 `scripts/create_admin.py`의 `getpass`로 생성·재설정한다.
- 서버 메모리에서 IP 버킷과 `IP+아이디` 버킷을 분리해 로그인 실패를 제한한다.
- 다섯 번째 실패부터 `30초 → 1분 → 5분 → 1시간` 제한과 `Retry-After`를 적용한다.
- 원문 IP 대신 HMAC 지문을 기록하며 임의 `X-Forwarded-For`를 신뢰하지 않는다.
- 현재 제한기는 단일 프로세스 메모리 기반이다. 배포 시 Redis TTL 또는 WAF로 교체한다.

```powershell
cd backend
$env:PYTHONPATH=(Resolve-Path .\src).Path
.\.venv\Scripts\python.exe scripts\create_admin.py
```

관리자 API:

| 방식 | 경로 | 기능 |
|---|---|---|
| `POST` | `/api/admins/signin` | 관리자 로그인 |
| `GET` | `/api/admins/me` | 관리자 토큰·활성 상태 확인 |

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

## 다음 작업 후보와 미구현 범위

- 장바구니·주문·결제는 아직 UI 자리만 있고 DB/API가 없다.
- 주문 내역은 마이페이지에서 목업 UI만 표시한다.
- 고객 로그인은 현재 `sessionStorage` 토큰 방식이다.
- 관리자도 `sessionStorage` 토큰 방식이며 MFA가 없다.
- 사용자 로그인 API에는 관리자 수준의 IP 속도 제한이 없다.
- lifespan의 고객 탈퇴 정리는 서버 프로세스마다 실행될 수 있다.
- 관리자 비공개 경로는 배포 보안 수단이 아니므로 WAF·MFA·HttpOnly 쿠키 전환이 필요하다.
- SPA 배포 서버는 `/products/{id}`, `/user/*`, 관리자 비공개 경로를 `index.html`로 fallback해야 한다.
- 실제 주문 구현 전 상품 상세의 구매 UX와 재고·가격 스냅샷 정책을 먼저 설계해야 한다.

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
