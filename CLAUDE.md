# Product Management 개발 인수인계

## 프로젝트 목적

React 고객용 상품 카탈로그와 단일 관리자 상품 관리 화면을 FastAPI 및 Supabase PostgreSQL에 연결한 학습용 프로젝트다. 고객은 로그인 없이 공개 상품을 조회하고 관리자는 고정 아이디 `admin`으로 상품을 관리한다.

## 코드 작성 규칙

- 파일 첫 줄에 해당 파일 역할을 한 줄 주석으로 작성한다.
- 함수와 클래스 설명은 내부 docstring 대신 선언 바로 위 `#` 주석으로 작성한다.
- 주석은 존댓말 문장 대신 `~검증`, `~처리`, `~모델` 형태의 명사형을 사용한다.
- 실제 비밀번호, 환경변수 값, DB 비밀번호, SMTP 앱 비밀번호, 토큰 서명키, 관리자 비공개 URL은 소스와 문서에 기록하지 않는다.
- 프로젝트 설명용 Markdown은 루트 `CLAUDE.md` 하나만 사용한다.

## 사용자와 관리자 분리

- 고객 화면은 `/products`와 `/products/detail`만 사용하며 관리자 화면 링크를 노출하지 않는다.
- 관리자 화면 경로는 Git 제외 대상인 `frontend/.env.local`의 `VITE_ADMIN_BASE_PATH`로 정한다.
- 관리자 로그인·상품 화면은 모두 위 비공개 기본 경로 아래에 있다.
- 관리자 상품 목록과 등록·수정 화면의 헤더에는 고객용 `/products`를 새 창으로 여는 `사이트로 바로가기` 버튼을 제공한다.
- 관리자 로그인 화면과 인증 UX는 배포 단계 보안 전환 전까지 현재 기능으로 고정한다.
- URL을 숨기는 것은 탐색 방지 수단일 뿐 보안 경계가 아니다. 실제 권한은 모든 `/api/admin/products` 요청에서 `admin_access` 토큰을 검증해 통제한다.
- 관리자 토큰은 `admin_access`, 향후 사용자 토큰은 `user_access` 용도로 서명한다. 두 토큰은 서로 대신 사용할 수 없다.
- 기존 회원가입·아이디 찾기·비밀번호 재설정·잠금 해제·탈퇴 소스는 `backend/src/backend/domain/users`, `frontend/src/features/user-auth`, `frontend/src/api/user-auth.js`에 보관한다.
- 사용자 인증 라우터와 화면은 현재 앱에 등록하지 않으며 `users` 테이블도 현재 서버에서 생성하지 않는다. 사용자 페이지 설계 시 별도 마이그레이션과 라우팅으로 연결한다.

## 주요 구조

```text
product-management/
├─ backend/
│  ├─ main.py
│  ├─ migrations/
│  ├─ scripts/
│  ├─ tests/
│  └─ src/backend/
│     ├─ core/
│     └─ domain/
│        ├─ admins/       # 현재 사용하는 단일 관리자 인증
│        ├─ products/     # 관리자 상품 관리와 고객 공개 조회
│        └─ users/        # 향후 사용자 인증 소스, 현재 비활성
├─ frontend/src/
│  ├─ api/
│  ├─ components/
│  ├─ config/routes.js
│  ├─ features/user-auth/ # 향후 사용자 화면, 현재 비활성
│  └─ pages/
├─ .gitignore
└─ CLAUDE.md
```

## 실행

서로 다른 터미널에서 백엔드와 프런트를 따로 실행한다.

```powershell
cd backend
fastapi dev main.py --host 127.0.0.1
```

```powershell
cd frontend
npm run dev
```

- 고객 화면: `http://localhost:5173/products`
- 관리자 화면: `http://localhost:5173` 뒤에 로컬 `VITE_ADMIN_BASE_PATH`와 `/login`을 붙인 주소
- 백엔드: `http://127.0.0.1:8000`
- API 문서: `http://127.0.0.1:8000/docs`

## 단일 관리자 정책

`public.admin_accounts`에는 다음 컬럼만 유지한다.

| 필드 | 정책 |
|---|---|
| `id` | 자동 증가 내부 고유번호 |
| `username` | DB 체크 제약으로 `admin`만 허용, 고유값 |
| `password` | 모델 속성명 `password_hash`, PBKDF2 해시만 저장 |
| `created_at` | 계정 생성 시각 |
| `is_active` | 긴급 접근 차단용 상태 |
| `auth_version` | 관리 스크립트로 비밀번호 재설정 시 기존 토큰 무효화 |

관리자 회원가입·아이디 찾기·이메일·닉네임·약관·승인·탈퇴 기능과 DB 컬럼은 없다. 계정 자체를 잠그지 않으며 관리자 비밀번호는 로컬 터미널 명령으로 생성하거나 재설정한다.

```powershell
cd backend
$env:PYTHONPATH=(Resolve-Path .\src).Path
.\.venv\Scripts\python.exe scripts\create_admin.py
```

`create_admin.py`는 `getpass`로 비밀번호를 화면과 명령 기록에 노출하지 않는다. 비밀번호는 영문·숫자·특수문자를 포함한 8~64자이며 DB에는 해시만 저장된다. 비밀번호를 채팅, 소스, `.env`, Git 커밋으로 전달하지 않는다.

## 관리자 로그인 제한

- 서버에서 IP 버킷과 `IP+아이디` 버킷을 독립적으로 계산한다.
- 같은 IP의 다섯 번째 실패부터 `30초 → 1분 → 5분 → 1시간` 순서로 제한한다.
- 제한 응답은 `429 LOGIN_RATE_LIMITED`와 `Retry-After` 헤더를 포함한다.
- 정상 로그인 시 해당 IP와 조합의 실패 기록을 초기화한다.
- 최근 1시간 동안 세 개 이상의 IP에서 `admin` 로그인을 실패하면 보안 경고 로그를 남긴다.
- 원문 IP 대신 HMAC 지문만 제한 저장소와 로그에서 사용한다.
- 전달 헤더는 위조될 수 있으므로 현재는 직접 연결 IP만 사용한다. 배포 시 신뢰할 프록시 목록을 확정한 뒤 해당 프록시의 전달 IP만 읽는다.
- 현재 `LoginRateLimiter`는 로컬 단일 프로세스용 메모리 저장소이므로 서버 재시작과 다중 프로세스 간 기록을 공유하지 않는다. 배포 단계에서는 같은 인터페이스를 Redis TTL 저장소 또는 WAF 제한으로 교체한다.

## 배포 단계 보안 작업

다음 항목은 로컬 기능 구현 범위에서 제외하며 실제 배포 환경과 인프라가 확정된 뒤 반드시 적용한다.

- 메모리 기반 `LoginRateLimiter`를 Redis TTL 공유 저장소로 교체하고 여러 서버·프로세스가 같은 제한 상태를 사용하도록 구성한다.
- Cloudflare 또는 배포 플랫폼 WAF에서 관리자 로그인 경로의 속도 제한과 자동화 공격 차단 규칙을 적용한다.
- 신뢰할 리버스 프록시 목록을 확정하고 해당 프록시가 설정한 실제 접속 IP 헤더만 검증해서 사용한다. 외부 요청의 임의 `X-Forwarded-For` 헤더는 신뢰하지 않는다.
- 관리자 로그인에 MFA를 추가하고 복구 코드 발급·보관·재발급 정책을 함께 설계한다.
- `sessionStorage`의 관리자 토큰을 `HttpOnly`, `Secure`, `SameSite` 속성이 적용된 쿠키 기반 세션으로 전환하고 CSRF 방어를 함께 적용한다.
- 배포 완료 전 위 항목을 별도 보안 QA로 검증하며 비공개 관리자 URL만으로 접근 보안을 대신하지 않는다.

## API 경로

관리자 인증:

| 방식 | 경로 | 기능 |
|---|---|---|
| `POST` | `/api/admins/signin` | 단일 관리자 로그인 |
| `GET` | `/api/admins/me` | 관리자 토큰과 계정 상태 확인 |

관리자 상품:

| 방식 | 경로 | 기능 |
|---|---|---|
| `GET`, `POST` | `/api/admin/products` | 상품 목록 또는 등록 |
| `GET`, `PUT`, `DELETE` | `/api/admin/products/{id}` | 상품 상세·수정·소프트 삭제 |
| `POST` | `/api/admin/products/{id}/restore` | 삭제 상품 복원 |
| `GET` | `/api/admin/products/categories` | 활성 카테고리 |
| `GET` | `/api/admin/products/related-candidates` | 관련 상품 후보 |
| `POST` | `/api/admin/products/editor-images` | 상세내용 이미지 업로드 |
| `DELETE` | `/api/admin/products/editor-image-drafts/{upload_session_id}` | 저장 취소한 상세 이미지 임시 세션 정리 |

고객 공개 상품:

| 방식 | 경로 | 기능 |
|---|---|---|
| `GET` | `/api/products` | 공개 상품 검색·카테고리·페이지 조회 |
| `GET` | `/api/products/categories` | 공개 카테고리 조회 |
| `GET` | `/api/products/{id}` | 공개 상품 상세와 관련 상품 조회 |

## 상품 정책

- 상품은 관리자 개인 소유가 아닌 전역 카탈로그다.
- 단일 관리자 구조이므로 상품과 감사 로그에 관리자 ID를 중복 저장하지 않는다. 감사 로그에는 상품, 동작, 변경값, 발생 시각만 기록한다.
- 고객 화면에는 `status=active`, `visible=true`, 활성 카테고리 상품만 노출한다.
- 활성 상품의 상품코드와 노출순서는 전체 카탈로그에서 고유하다.
- 삭제 시 `status=deleted`, `deleted_at`을 기록하는 소프트 삭제를 사용하며, 현재 자동 영구 삭제 작업은 없어 DB와 Storage 원본을 계속 보존한다.
- 관리자 목록은 판매 상품과 삭제 상품을 분리해 조회한다. 복원 상품은 `visible=false`로 시작하며 사용 중인 노출순서는 마지막 순서로 자동 변경한다.
- 복원 시 상품코드·활성 카테고리를 다시 검증하고, 삭제 감사 로그에 남은 관련 상품 중 현재도 활성·동일 카테고리이며 최대 선택 수를 넘지 않는 연결만 되살린다.
- 등록·수정·삭제·복원 시각은 한국 시간대를 명시해 생성하고 API는 `+09:00` 오프셋으로 응답한다. PostgreSQL `TIMESTAMPTZ`의 내부 순간은 UTC로 정규화되며 요청 DB 세션과 프런트 표시는 `Asia/Seoul`로 고정한다.
- 대표 이미지와 상세내용 이미지는 Supabase Storage에 저장하며 상세 HTML은 서버 허용 목록으로 정리한다.
- 대표 이미지 교체는 새 객체 업로드 → DB 반영 → 기존 객체 삭제 순서로 처리한다. DB 반영 실패 시 새 객체를 삭제해 기존 이미지를 유지한다.
- 상품 카테고리가 바뀌면 대표 이미지와 본문 이미지 경로도 새 카테고리 폴더로 이동하며, DB 저장 실패 시 원래 경로로 되돌린다.

## 환경변수

- 실제 백엔드 값은 Git 제외 대상인 `backend/.env`에 저장한다.
- 관리자 프런트 경로는 Git 제외 대상인 `frontend/.env.local`의 `VITE_ADMIN_BASE_PATH`에 저장한다.
- `AUTH_SECRET_KEY`는 32자 이상의 무작위 문자열을 사용한다.
- `DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, SMTP 비밀값은 프런트에 노출하지 않는다.
- 탈퇴·메일 관련 백엔드 설정은 향후 사용자 인증 소스 재연결을 위해 남아 있으며 현재 관리자 API에서는 사용하지 않는다.

## 마이그레이션과 현재 DB 상태

- `007_admin_accounts_and_approval.sql`은 과거 사용자형 계정을 관리자 테이블로 전환한 이력이다.
- `008_single_admin_account.sql`은 기존 계정을 모두 삭제하고 관리자 테이블을 단일 `admin` 전용 컬럼으로 축소하며 관리자 탈퇴 Cron과 함수를 제거한다.
- `009_admin_ip_rate_limit.sql`은 계정 잠금 컬럼을 제거하고 서버 측 접속 IP 제한기로 전환한다.
- `010`, `011`은 단일 관리자 구조에서 중복이 된 상품·감사 로그의 관리자 ID 컬럼을 제거한다.
- `012_korea_timezone.sql`은 직접 DB 연결의 기본 시간대를 한국으로 설정하기 위한 마이그레이션이다. 현재 Supabase Pooler 연결은 서버 기본값을 UTC로 초기화하므로 애플리케이션 요청마다 한국 시간대를 다시 설정한다.
- `013_product_restore.sql`은 감사 로그에 `restored` 작업 유형을 추가한다.
- `014_remove_legacy_image_data.sql`은 Storage 경로가 있는지 확인한 후 `products.image_data`를 제거하고 `image_path`를 필수값으로 변경한다.
- 2026-09-28 실제 DB에 `008`~`011`, `013`, `014` 적용과 구조 검증을 완료했다. `012`는 Pooler를 통한 영구 기본값 변경 대신 요청별 설정으로 동작한다. 활성 `admin` 계정 한 건과 상품 20건이 존재한다.
- 대표 이미지와 상세 이미지는 `products/{category_code}/{YYYY-MM-DD}/{main|detail}-{uuid}.확장자` 구조로 Storage에 저장한다. 날짜는 상품 최초 등록일이며 `products.image_data` 컬럼은 제거했다.
- 현재 단일 관리자의 운영 계획은 상품당 대표 이미지 1장과 상세내용 이미지 1장, 총 2장이다. 에디터 기능은 향후 활용을 위해 여러 상세 이미지를 허용하며 1장 제한을 강제하지 않는다. 현재 규모에서는 상품 ID 하위 폴더 없이 기존 경로를 유지하고, 실제로 상품당 이미지 수가 늘거나 이미지 버전·일괄 정리 기능이 필요해지면 `products/{category_code}/{YYYY-MM-DD}/{product_id}/...` 구조와 이미지 전용 테이블 도입을 함께 재검토한다.
- 에디터 이미지는 저장 전 `products/_drafts/{upload_session_id}/detail-{uuid}.확장자`에 격리하고, 저장 시 정식 경로로 이동한다. 취소·화면 이탈 또는 저장 완료 시 같은 세션의 미사용 임시 파일을 정리한다.
- 브라우저 비정상 종료 등으로 정리 요청이 도착하지 않은 임시 파일은 `backend/scripts/cleanup_product_image_drafts.py --retention-hours 24`로 정리한다. 배포 시 하루 1회 실행 작업으로 연결한다.

## 검증 명령과 완료 상태

```powershell
cd backend
$env:PYTHONPATH=(Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q main.py src scripts
.\.venv\Scripts\python.exe scripts\check_auth_schema.py
```

```powershell
cd frontend
npm run lint
npm run build
```

2026-09-28 기준 백엔드 단위 테스트 28개, Python 문법 검사, 프런트 린트와 프로덕션 빌드가 통과했다. 실제 상품 DB에는 잘못된 삭제 상태, 비활성·다른 카테고리 관련 상품, 상품당 2건 초과 관계가 없으며 복원 감사 제약이 적용되어 있다.
