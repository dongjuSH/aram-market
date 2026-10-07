# Oracle Cloud 운영 배포 기록

최종 갱신: 2026-10-07
최초 운영 배포 및 검증: 2026-10-05

운영 주소는 `https://aram-market.duckdns.org`이다. 이 문서는 실제 운영 서버에 적용한 구성, 배포 중 확인한 문제와 해결 방법, 이후 재배포 절차를 기록한다. 비밀번호·토큰·키·실제 환경변수 값은 기록하지 않는다.

최초 운영 배포에서 확인한 코드 기준은 `9c7033d`(`fix: include timezone data dependency`)이며, 이후 배포 설정 파일과 이 운영 기록을 저장소에 추가했다.

## 현재 운영 구성

| 항목 | 운영 상태 |
|---|---|
| 클라우드 | Oracle Cloud 홈 리전 Japan Central (Osaka) |
| 인스턴스 | Always Free `VM.Standard.E2.1.Micro`, 1 OCPU, 1GB RAM, x86_64 |
| OS | Ubuntu 24.04.5 LTS, 시간대 `Asia/Seoul`, NTP 활성 |
| 스왑 | `/swapfile` 2GB, 재부팅 후 자동 활성, `vm.swappiness=10` |
| 애플리케이션 | `/var/www/aram-market`, 브랜치 `main` |
| 백엔드 | Python 3.14.8(uv), `.venv`, FastAPI/Uvicorn, systemd 워커 1개 |
| 프런트엔드 | 개인 PC의 Node 24로 빌드한 `frontend/dist`만 서버에 배치 |
| 웹 서버 | Nginx 정적 파일 제공 + `/api/` 역방향 프록시 |
| 도메인·TLS | DuckDNS + Let's Encrypt(Certbot) |
| 데이터·이미지 | 기존 Supabase PostgreSQL·Storage 사용 |
| 결제 | 포트폴리오 운영이므로 Toss Payments 테스트 키 유지 |

ARM `VM.Standard.A1.Flex`는 오사카 AD-1의 호스트 용량 부족으로 생성하지 못했다. AMD 목록에서 `VM.Standard.E5.Flex`만 보이던 시점이 있었지만, Always Free 대상인 `VM.Standard.E2.1.Micro`로 최종 생성했다. 1GB 메모리를 보완하기 위해 2GB 스왑을 구성했다.

## 저장소의 배포 파일

- `deploy/systemd/aram-market.service`: 백엔드 systemd 서비스
- `deploy/nginx/aram-market.conf`: Certbot 적용 전 기준 Nginx 설정
- `deploy/nginx/aram-market-blocked-routes.conf`: 운영 API 문서 경로 404 처리

서버에 적용할 때는 다음 위치를 사용한다.

```bash
sudo cp deploy/systemd/aram-market.service /etc/systemd/system/aram-market.service
sudo cp deploy/nginx/aram-market.conf /etc/nginx/sites-available/aram-market
sudo cp deploy/nginx/aram-market-blocked-routes.conf /etc/nginx/snippets/aram-market-blocked-routes.conf
sudo ln -sfn /etc/nginx/sites-available/aram-market /etc/nginx/sites-enabled/aram-market
sudo systemctl daemon-reload
sudo systemctl enable --now aram-market nginx
sudo nginx -t
sudo systemctl reload nginx
```

Certbot이 서버에서 추가하는 인증서 경로와 HTTP→HTTPS 리디렉션은 서버별 생성값이므로 저장소 템플릿에는 포함하지 않는다.

## 서버 런타임과 배치 원칙

- Ubuntu 기본 Python 3.12 대신 저장소의 `.python-version`에 맞춰 uv로 Python 3.14를 설치한다.
- 백엔드 가상환경은 `backend/.venv`에 만들고 uv로 고정 의존성을 설치한다. `tzdata==2026.5`가 포함되어 `ZoneInfo("Asia/Seoul")`를 사용할 수 있다.
- Uvicorn은 `127.0.0.1:8000`에서만 수신한다. 외부에 8000번 포트를 열지 않는다.
- Node 24는 서버에 유지하지 않는다. 프런트엔드는 개인 PC에서 빌드하고 `dist`만 올린다. 배포 중 시험 설치했던 Node와 NodeSource 설정은 서버에서 제거했다.
- 1GB 인스턴스이므로 Uvicorn 워커는 1개를 유지한다.

백엔드 설치·검증 예시는 다음과 같다.

```bash
cd /var/www/aram-market/backend
$HOME/.local/bin/uv python install 3.14
$HOME/.local/bin/uv venv --python 3.14 .venv
$HOME/.local/bin/uv pip install --python .venv/bin/python -r requirements.txt
$HOME/.local/bin/uv pip check --python .venv/bin/python
.venv/bin/python -c "from zoneinfo import ZoneInfo; print(ZoneInfo('Asia/Seoul'))"
```

## 환경변수와 비밀값

`backend/.env`, `frontend/.env.local`과 모든 비밀값은 Git에 추가하지 않는다. 운영 서버의 `backend/.env`는 안전한 경로로 전송하고 권한을 `600`으로 제한한다.

필수 운영 방향은 다음과 같다.

- `BACKEND_PUBLIC_URL`과 `FRONTEND_URL`: 운영 HTTPS 주소
- `TRUSTED_PROXY_IPS`: 같은 서버의 Nginx만 신뢰하도록 `127.0.0.1`
- `AUTH_SECRET_KEY`: 로컬과 다른 새 64자 난수 값
- HTTPS에서 Secure 인증 쿠키 사용
- 관리자 MFA 필수
- API 문서 비활성화
- Sentry 환경 `production`

새 `AUTH_SECRET_KEY`를 적용하면 기존에 암호화된 관리자 MFA 시크릿과 복구 코드는 사용할 수 없다. 운영 서버에서 MFA를 다시 등록해야 한다.

```bash
cd /var/www/aram-market/backend
PYTHONPATH=src .venv/bin/python scripts/setup_admin_mfa.py
```

운영 관리자 MFA는 재등록을 완료했으며 복구 코드 10개가 발급된 상태로 확인했다.

## 네트워크와 방화벽

Oracle Ubuntu 이미지에서는 UFW를 사용하지 않는다. UFW 활성화 과정에서 OCI가 제공하는 필수 iptables 규칙이 유실되면 부팅·스토리지 연결에 영향을 줄 수 있다.

- OCI VCN: `aram-market-vcn`
- 퍼블릭 서브넷: `aram-market-public-subnet`
- OCI 기본 보안 목록 수신 규칙: TCP 22·80·443
- 서버 iptables: INPUT REJECT 규칙 앞에 TCP 22·80·443 허용
- `/etc/iptables/rules.v4`에 규칙 저장 및 재부팅 후 유지 확인
- FastAPI 8000: `127.0.0.1`에서만 수신
- DuckDNS A 레코드: 운영 인스턴스 공인 IP를 가리키도록 설정

## Nginx, HTTPS와 보안 헤더

Nginx는 `frontend/dist`를 제공하고 `/api/`만 백엔드로 프록시한다. SPA 경로는 `index.html`로 폴백하되, API 문서 경로가 SPA 화면으로 200 응답하지 않도록 별도 스니펫에서 404로 차단한다.

```bash
sudo certbot --nginx -d aram-market.duckdns.org
sudo certbot renew --dry-run
```

인증서 발급과 갱신 모의 실행을 모두 통과했다. HTTP는 HTTPS로 301 리디렉션하며 다음 헤더를 적용한다.

- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- Content Security Policy(CSP) 강제 적용

CSP는 먼저 Report-Only로 점검한 뒤 강제 적용했다. 토스 결제, Supabase 이미지, Sentry, 카카오 우편번호 검색에 필요한 출처만 허용한다. 주소 검색은 `postcode.map.daum.net`에서 실제로 `postcode.map.kakao.com`으로 전환되어 두 frame 출처를 모두 허용해야 정상 동작한다. 현재 설정은 저장소의 `deploy/nginx/aram-market.conf`에 기록되어 있다.

## 최초 배포 중 확인한 문제

| 현상 | 원인 | 처리·결과 |
|---|---|---|
| A1 인스턴스 생성 실패 | 오사카 AD-1 ARM 호스트 용량 부족 | Always Free AMD `E2.1.Micro`로 전환 |
| SSH `Permission denied (publickey)` | 개인키 암호 입력 문제 | 인스턴스 생성에 쓴 기존 개인키 암호를 확인해 접속 성공 |
| 1GB 메모리 | 빌드·동시 실행 여유 부족 | 2GB 스왑 추가, 서버 프런트 빌드 금지, 백엔드 워커 1개 |
| `/docs` 등이 200 | Nginx SPA fallback이 `index.html` 반환 | 문서 경로를 명시적으로 404 처리 |
| 주소 검색 창 차단 | CSP에 실제 Kakao postcode frame 출처 누락 | Daum·Kakao postcode frame 출처 모두 허용 |
| 재부팅 직후 외부 헬스 체크 502 | Nginx가 백엔드 초기화보다 먼저 요청을 받음 | 잠시 뒤 자동 복구되어 내부·외부 헬스 모두 200 확인 |
| 비밀번호 재설정 메일 지연 | Gmail 스팸 분류 | 메일 2건 수신 및 운영 도메인 링크 정상 확인 |

재부팅 직후의 502가 지속되면 단순 대기하지 말고 아래 순서로 확인한다.

```bash
systemctl status aram-market --no-pager
sudo journalctl -u aram-market -n 100 --no-pager
curl -i http://127.0.0.1:8000/api/health
curl -i https://aram-market.duckdns.org/api/health
```

## 재배포 절차

### 1. 변경 전 확인

```bash
cd /var/www/aram-market
git status --short
git fetch origin
git log --oneline HEAD..origin/main
```

서버 작업 트리에 예상하지 못한 변경이 있으면 덮어쓰지 말고 먼저 원인을 확인한다.

### 2. 백엔드 갱신

```bash
cd /var/www/aram-market
git pull --ff-only origin main
cd backend
$HOME/.local/bin/uv pip install --python .venv/bin/python -r requirements.txt
$HOME/.local/bin/uv pip check --python .venv/bin/python
sudo systemctl restart aram-market
sudo systemctl status aram-market --no-pager
```

DB 마이그레이션이 포함된 배포는 해당 마이그레이션의 사전 확인·적용·검증 스크립트를 문서화된 순서대로 실행한 후 서비스를 확인한다.

### 3. 프런트엔드 갱신

개인 PC에서 운영 `.env.local`을 사용해 빌드한다.

```powershell
Set-Location .\frontend
npm ci
npm test
npm run build
```

그 다음 `frontend/dist`의 내용만 서버의 `/var/www/aram-market/frontend/dist`에 업로드한다. 업로드 후 Nginx가 읽을 수 있도록 디렉터리는 755, 파일은 644인지 확인한다. 서버에 `.env.local`, `node_modules` 또는 로컬 소스맵 비밀값을 업로드하지 않는다.

### 4. 설정 변경 시 반영

```bash
sudo cp deploy/systemd/aram-market.service /etc/systemd/system/aram-market.service
sudo cp deploy/nginx/aram-market.conf /etc/nginx/sites-available/aram-market
sudo cp deploy/nginx/aram-market-blocked-routes.conf /etc/nginx/snippets/aram-market-blocked-routes.conf
sudo systemctl daemon-reload
sudo nginx -t
sudo systemctl restart aram-market
sudo systemctl reload nginx
```

Nginx 템플릿을 다시 복사하면 Certbot이 추가한 인증서 지시문이 사라질 수 있다. 실제 서버 설정과 비교하고, 필요하면 `sudo certbot --nginx -d aram-market.duckdns.org`를 다시 실행한 뒤 `nginx -t`로 검증한다.

### 5. 배포 후 확인

```bash
curl -fsS https://aram-market.duckdns.org/api/health
for path in /docs /docs/ /redoc /redoc/ /openapi.json; do
  curl -s -o /dev/null -w "$path -> %{http_code}\n" "https://aram-market.duckdns.org$path"
done
systemctl is-enabled aram-market nginx
systemctl is-active aram-market nginx
sudo ss -lntp | grep -E '(:22|:80|:443|:8000)'
sudo certbot renew --dry-run
```

정상 기준은 다음과 같다.

- `/api/health` → 200, `{"status":"ok"}`
- `/docs`, `/redoc`, `/openapi.json`과 슬래시 변형 → 404
- `aram-market`, `nginx` → enabled·active
- 22·80·443 → 공개 수신, 8000 → `127.0.0.1`에서만 수신
- HTTP → HTTPS 301 리디렉션
- 인증 쿠키 → `Secure`, `HttpOnly`, 의도한 `SameSite`

## 완료한 운영 검증

- 관리자 로그인과 새 MFA 인증
- 고객 로그인, 새로고침 세션 유지, 로그아웃, 쿠키 속성
- 비밀번호 재설정 메일 수신과 운영 HTTPS 링크
- Toss 테스트 결제 및 고객·관리자 주문 화면 반영
- 상품 목록·상세·이미지, 관리자 화면, 배송지 주소 검색
- API 헬스 체크, API 문서 경로 404
- TLS 자동 갱신 모의 실행
- 재부팅 후 스왑·iptables·systemd 서비스 자동 복구
- SMTP 연결·인증

## 남은 운영·코드 개선 항목

- 상품 상세 모달을 닫을 때 포커스가 남은 요소에 `aria-hidden`이 적용되는 브라우저 접근성 경고가 있다. 기능 장애는 아니지만 포커스를 먼저 안전한 요소로 이동하거나 `inert`를 사용하도록 프런트 코드를 개선해야 한다.
- Sentry 프로젝트의 Localhost Inbound Filter 활성화 여부는 콘솔에서 최종 확인한다. 소스맵 업로드는 선택 사항이다.
- Gmail에서 비밀번호 재설정 메일이 스팸으로 분류된 적이 있다. 포트폴리오 운영에는 지장이 없지만 실제 서비스 전환 시 발신 도메인, SPF/DKIM/DMARC와 메일 평판을 별도로 구성한다.
- Toss 테스트 키는 포트폴리오 정책에 따라 의도적으로 유지한다. 실제 결제를 받기 전에는 라이브 키·상점 계약·환불 운영 절차를 별도 적용한다.
