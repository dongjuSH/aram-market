# Product Management 개발 인수인계

## 프로젝트 목적

관리자 로그인, 회원가입, 계정 찾기, 비밀번호 재설정, 로그인 잠금, 회원 탈퇴 생명주기와 상품 관리 화면을 구현하는 학습용 프로젝트다.

상품 관리 기능은 현재 화면만 구현되어 있으며 검색, 페이지 이동, 등록, 수정 API는 후속 작업 범위다.

## 코드 작성 규칙

- 파일 첫 줄에 해당 파일의 역할을 한 줄 주석으로 작성한다.
- 함수와 클래스 설명은 내부 docstring이 아닌 선언 바로 위 `#` 주석으로 작성한다.
- 주석은 `~합니다`, `~입니다` 같은 존댓말 대신 `~검증`, `~모델`, `~처리` 형태의 명사형을 사용한다.
- 모델 필드, 스키마 필드, 짧은 함수 인자처럼 한 줄로 읽을 수 있는 선언은 불필요하게 여러 줄로 나누지 않는다.
- SQL, HTML, JSX처럼 구조 구분이 필요한 코드는 기능 단위 줄바꿈을 유지한다.
- 실제 환경변수 값, DB 비밀번호, SMTP 앱 비밀번호, 인증 비밀키는 문서와 소스에 기록하지 않는다.
- 프로젝트 설명용 Markdown은 루트 `CLAUDE.md` 하나만 사용한다.

## 기술 구성

- 프런트엔드: React, Vite, JavaScript, CSS
- 백엔드: Python, FastAPI, SQLAlchemy Async, Pydantic
- DB: PostgreSQL 또는 Supabase PostgreSQL
- 메일: SMTP, HTML 및 텍스트 멀티파트
- 배치: Supabase `pg_cron`, 한국시간 자정 실행
- 인증: PBKDF2-SHA256 비밀번호 해시, HMAC 서명 토큰

## 주요 폴더

```text
product-management/
├─ backend/
│  ├─ main.py
│  ├─ scripts/
│  ├─ src/backend/core/
│  └─ src/backend/domain/
│     ├─ users/
│     └─ products/
├─ frontend/
│  └─ src/
│     ├─ api/
│     ├─ components/
│     └─ pages/
├─ .vscode/settings.json
└─ CLAUDE.md
```

## 실행

프로젝트 루트의 서로 다른 터미널에서 백엔드와 프런트를 각각 실행한다.

```powershell
cd backend
fastapi dev main.py --host 127.0.0.1
```

```powershell
cd frontend
npm run dev
```

기본 주소:

- 프런트: `http://localhost:5173`
- 백엔드: `http://127.0.0.1:8000`
- FastAPI 문서: `http://127.0.0.1:8000/docs`

`0.0.0.0`은 외부 연결을 받기 위한 바인딩 주소이며 브라우저 접속 주소가 아니다. 로컬 브라우저에서는 `http://127.0.0.1:8000`을 사용한다. `fastapi run main.py`는 배포용 기본값으로 `0.0.0.0`을 사용하므로 로컬 개발은 위 `fastapi dev` 명령을 사용한다.

`backend/main.py`는 실행 방식 차이로 import가 실패하지 않도록 `backend/src`를 Python 경로에 추가한다. VS Code 분석 경로와 인터프리터는 루트 `.vscode/settings.json`에 설정되어 있다.

## 환경변수

실제 값은 `backend/.env`에만 저장한다. `.env`와 `backend/.env.example`은 Git 제외 대상이다.

| 이름 | 용도 |
|---|---|
| `DATABASE_URL` | SQLAlchemy 비동기 PostgreSQL 연결 주소 |
| `AUTH_SECRET_KEY` | 인증 토큰 HMAC 서명키, 최소 32자 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 접근 토큰 유효시간 |
| `UNLOCK_TOKEN_EXPIRE_MINUTES` | 계정 잠금 해제 링크 유효시간 |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | 비밀번호 재설정 링크 유효시간 |
| `WITHDRAWAL_GRACE_DAYS` | 탈퇴 취소 가능 기간, 현재 7일 |
| `WITHDRAWAL_RETENTION_DAYS` | 유예 종료 후 추가 보관기간, 테스트 서비스는 0일 |
| `BACKEND_PUBLIC_URL` | 잠금 해제 메일의 백엔드 공개 주소 |
| `FRONTEND_URL` | 로그인 및 비밀번호 재설정 화면 주소 |
| `SMTP_HOST` | SMTP 호스트 |
| `SMTP_PORT` | STARTTLS 587 또는 SSL 465 |
| `SMTP_USERNAME` | SMTP 인증 계정 |
| `SMTP_PASSWORD` | SMTP 앱 비밀번호 |
| `SMTP_FROM_EMAIL` | 발신 허용 이메일 |
| `SMTP_FROM_NAME` | 발신자 표시명 |
| `SMTP_USE_TLS` | STARTTLS 사용 여부 |

## 사용자 DB 모델

테이블명은 `public.users`다.

| 필드 | 정책 |
|---|---|
| `id` | 자동 증가 기본키 |
| `username` | 4~20자, 영문·숫자·밑줄, 소문자 정규화, 고유값 |
| `password` | 모델 속성명 `password_hash`, PBKDF2 해시만 저장 |
| `nickname` | 2~10자, 한글·영문·숫자·밑줄, 고유값 |
| `email` | 최대 254자, 소문자 정규화, 고유값 |
| `created_at` | 가입 시각 |
| `is_active` | 관리자 비활성화 여부 |
| `login_fail_count` | 연속 로그인 실패 횟수 |
| `locked_until` | 로그인 잠금 만료 시각 |
| `status` | `active`, `pending_deletion`, `withdrawn` |
| `withdrawn_at` | 탈퇴 접수 시각 |
| `auth_version` | 비밀번호 변경·탈퇴 시 기존 토큰 무효화용 버전 |
| `service_policy` | 서비스 이용약관 필수 동의 |
| `privacy_policy` | 개인정보 수집 필수 동의 |

`Base.metadata.create_all()`은 새 테이블만 생성하고 기존 테이블 구조는 변경하지 않는다. 기존 DB에는 `backend/scripts/apply_account_lifecycle.py` 등 필요한 마이그레이션을 별도로 적용한다.

## API 경로

공통 API prefix `/api`는 `backend/main.py`에서 적용하고 사용자 도메인 라우터는 `/users`만 담당한다. 현재는 단일 내부·학습 서비스이므로 별도 버전 경로를 사용하지 않으며, 외부 클라이언트와 하위 호환을 유지해야 하는 시점에 major 버전 도입을 검토한다.

| 방식 | 경로 | 기능 |
|---|---|---|
| `POST` | `/api/users/signup` | 회원가입 |
| `POST` | `/api/users/signin` | 로그인 |
| `POST` | `/api/users/find-username` | 아이디 안내 메일 요청 |
| `POST` | `/api/users/password-reset/request` | 비밀번호 재설정 메일 요청 |
| `POST` | `/api/users/password-reset/confirm` | 새 비밀번호 저장 |
| `GET` | `/api/users/unlock` | 이메일 토큰 기반 계정 잠금 해제 |
| `GET` | `/api/users/me` | 접근 토큰 검증 및 현재 사용자 조회 |
| `PUT` | `/api/users/me/password` | 로그인 사용자의 현재 비밀번호 확인 후 변경 |
| `DELETE` | `/api/users/me` | 로그인 계정 탈퇴 접수 |
| `POST` | `/api/users/withdrawal/cancel` | 탈퇴 유예 계정 복구 |

## 인증 정책

- 비밀번호는 PBKDF2-SHA256 600,000회 반복과 무작위 salt로 해시한다.
- 기존 학습용 평문 비밀번호는 첫 성공 로그인에서 해시로 교체한다.
- 비밀번호 5회 실패 시 계정을 1시간 잠근다.
- 존재하지 않는 아이디, 틀린 비밀번호, 잠긴 계정은 모두 같은 `INVALID_CREDENTIALS` 응답을 반환한다.
- 로그인 실패 횟수와 계정 존재·잠금 여부는 응답으로 노출하지 않는다.
- 5회 실패 시 가입 이메일로 즉시 잠금 해제 링크를 발송한다.
- 정상 로그인 시 실패 횟수와 잠금시간을 초기화한다.
- 접근 토큰은 `sessionStorage`에 저장하며 브라우저 종료 시 사라진다.
- 비밀번호 재설정과 탈퇴는 `auth_version`을 증가시켜 기존 토큰을 무효화한다.

## 계정 찾기 및 메일 정책

- 아이디 찾기는 가입 이메일만 입력받는다.
- 비밀번호 찾기는 아이디와 가입 이메일을 입력받는다.
- 계정 존재 여부 노출 방지를 위해 일치 여부와 관계없이 같은 일반 안내를 반환한다.
- SMTP 발송 실패도 사용자에게는 일반 안내를 반환하고 서버 로그에만 기록한다.
- 사용자 입력을 이메일 템플릿에 삽입하기 전 HTML 이스케이프한다.
- 비밀번호 재설정 링크는 프런트 `/reset-password`로 연결한다.
- 계정 잠금 해제 링크는 백엔드 `/api/users/unlock`으로 연결한다.

## 탈퇴 정책

- 탈퇴 요청 즉시 삭제하지 않고 `pending_deletion` 상태로 전환한다.
- 탈퇴 접수 후 7일 이내 정상 비밀번호로 로그인하면 탈퇴 취소 여부를 확인한다.
- 탈퇴 취소용 토큰은 10분 동안 유효하다.
- 유예 종료 후 `withdrawn` 상태로 전환하고 추가 보관기간이 지나면 행을 삭제한다.
- 현재 테스트 서비스는 거래·결제 정보를 수집하지 않아 추가 보관기간을 0일로 설정한다.
- Supabase Cron은 `0 15 * * *` UTC, 한국시간 자정에 실행한다.
- `backend/scripts/apply_withdrawal_cron.py`는 `WITHDRAWAL_GRACE_DAYS`와 `WITHDRAWAL_RETENTION_DAYS`를 읽어 SQL 기간을 생성한다. 기간 변경 후 이 스크립트를 다시 실행해야 등록된 DB 함수를 갱신할 수 있다.

## 프런트 화면

- `/login`: 로그인, 회원가입 이동, 아이디 찾기 모달, 비밀번호 찾기 모달
- `/signup`: 회원정보 및 약관 입력, 필드별 검증 오류
- `/reset-password`: 이메일 토큰 기반 새 비밀번호 설정
- `/products`: 로그인 후 상품 관리 화면과 계정 메뉴
- `/change-password`: 로그인 사용자의 현재 비밀번호 확인 및 즉시 변경

로그인과 모달은 데스크톱에서 화면 중앙 정렬이다. 회원가입은 가로 중앙 정렬과 세로 스크롤 구조다. 모바일에서는 가로 넘침 없이 세로 스크롤을 사용한다.

공통 모달은 콘텐츠 영역의 상하좌우 안쪽 여백을 동일하게 사용하고 닫기 버튼만 우측 상단에 고정한다. 문장은 마침표 기준으로 줄을 나누며, Tab 포커스를 모달 내부에 고정하고 닫을 때 이전 요소로 복원한다.

상품 화면과 비밀번호 변경 화면은 저장된 토큰의 존재 여부만 보지 않고 `GET /api/users/me`로 서명·만료·인증 버전·계정 상태를 확인한 뒤 표시한다. `?preview=1`은 Vite 개발 모드에서 UI 확인에만 사용한다.

## 현재 미구현 또는 확인 필요 항목

- 상품 검색·페이지 이동·등록·수정 API 및 DB 모델
- 접근 토큰 갱신 또는 쿠키 기반 세션 정책
- 로그인 및 계정 찾기 API의 IP 기반 요청 제한
- `testsign003` 계정의 유예기간 종료 후 Cron 자정 삭제 확인

## 검증 명령

프런트:

```powershell
cd frontend
npm run lint
npm run build
```

백엔드:

```powershell
$env:PYTHONPATH="backend/.venv/Lib/site-packages;backend/src"
python -m unittest discover -s backend/tests -v
python -m compileall -q backend/main.py backend/src backend/scripts
```

마지막 자동 검증 기준으로 백엔드 테스트 17개, Python 문법 검사, 프런트 린트와 프로덕션 빌드가 통과한 상태다. 실제 DB의 컬럼·중복·제약·Cron 등록 상태와 SMTP 연결·인증을 확인했다. 실제 이메일 수신, 계정 잠금 해제, 비밀번호 변경도 수동 테스트를 통과했다. `testsign003` 계정의 Cron 자정 삭제 실행만 별도로 확인해야 한다.
