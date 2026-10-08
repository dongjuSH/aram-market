# Oracle Cloud 운영 배포 기록

최종 갱신: 2026-10-08
최초 운영 배포 및 검증: 2026-10-05

운영 주소는 `https://aram-market.duckdns.org`이다. 이 문서는 실제 운영 서버에 적용한 구성, 배포 중 확인한 문제와 해결 방법, 이후 재배포 절차를 기록한다. 비밀번호·토큰·키·실제 환경변수 값은 기록하지 않는다.

최초 운영 배포에서 확인한 코드 기준은 `9c7033d`(`fix: include timezone data dependency`)이며, 이후 배포 설정 파일과 이 운영 기록을 저장소에 추가했다. 2026-10-07에 서버 저장소를 `9ebb755`로 갱신하고(백엔드 실행 코드 변경은 메일 템플릿 6종의 하단 안내뿐) 같은 커밋으로 빌드한 프런트 `dist`(상품 카드 접근성 수정, 푸터 포트폴리오 안내, 패치 업데이트, Sentry 소스맵 업로드)와 Nginx 캐시 스니펫을 반영했다. 2026-10-08에 주문 환불 기능 커밋 `0be4c9c`로 서버 저장소를 갱신·재시작하고(의존성 변경 없음), 마이그레이션 031(사전에 적용 완료)을 확인한 뒤 032(약관 v1.2 동의 이력)를 적용했으며, 같은 커밋으로 빌드한 프런트 `dist`를 교체했다. 배포 후 `/api/health` 200, API 문서 3종 404, 새 환불 API 5개 미인증 401, 약관 API v1.2, 번들에 환불 화면 포함, `check_order_refunds.py`·`check_policy_v1_2_backfill.py` 종료 코드 0, `inspect_stuck_refunds.py` 대상 0건을 확인했다.

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
- `deploy/nginx/aram-market-cache.conf`: `index.html` no-cache, 해시 JS·CSS 장기 캐시, 없는 `/assets/` 파일 404

서버에 적용할 때는 다음 위치를 사용한다.

```bash
sudo cp deploy/systemd/aram-market.service /etc/systemd/system/aram-market.service
sudo cp deploy/nginx/aram-market.conf /etc/nginx/sites-available/aram-market
sudo cp deploy/nginx/aram-market-blocked-routes.conf /etc/nginx/snippets/aram-market-blocked-routes.conf
sudo cp deploy/nginx/aram-market-cache.conf /etc/nginx/snippets/aram-market-cache.conf
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

- `FRONTEND_URL`: 운영 HTTPS 주소(메일 링크·CORS·쿠키 Secure·API 문서·MFA 필수·Sentry 환경 기본값이 이 값으로 정해진다)
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

정적 파일 캐시(2026-10-07, `aram-market-cache.conf`): `/`·화면 경로·`/index.html`은 `Cache-Control: no-cache`, 파일 이름에 8자 해시가 붙은 `/assets/*.js|css`는 `max-age=315360000`, `/assets/`에 없는 파일은 `index.html` 대신 404를 돌려준다. 이전에는 `index.html`에 캐시 헤더가 없어 재배포 뒤에도 브라우저가 이전 화면을 계속 쓰고, 이미 지운 이전 번들 요청에 HTML이 돌아가 빈 화면이 될 수 있었다. 경로별 설정은 `add_header` 대신 `expires`를 써서 server 블록의 보안 헤더 상속을 유지한다(`location`에 `add_header`를 하나라도 쓰면 상속되지 않음).

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

1GB 인스턴스에서는 재시작 직후 몇 초 동안 앱이 아직 떠 있지 않아 `/api/health`가 502일 수 있다(2026-10-07 `restart` 3초 뒤 502, 곧 200). 10초쯤 뒤 다시 확인하고, 계속 502이면 위 '재부팅 직후의 502' 확인 순서를 따른다.

DB 마이그레이션이 포함된 배포는 해당 마이그레이션의 사전 확인·적용·검증 스크립트를 문서화된 순서대로 실행한 후 서비스를 확인한다.

#### 환불 확인 중 주문 운영 점검

환불을 시작한 지 하루가 지난 `refunding` 주문은 자동 재전송하지 않고 조회만 하며, 배송 전환도 계속 차단한다. Sentry의 `refund still unresolved after a day` 오류를 받으면 아래 읽기 전용 스크립트로 대상부터 확인한다. 이 스크립트는 DB나 토스 결제 상태를 변경하지 않으며 결제키도 끝 6자리만 출력한다.

```bash
cd /var/www/aram-market/backend
PYTHONPATH=src .venv/bin/python scripts/inspect_stuck_refunds.py --database-only
PYTHONPATH=src .venv/bin/python scripts/inspect_stuck_refunds.py
```

출력의 `gateway_result`는 다음처럼 해석한다.

- `full_refund_confirmed`: 토스에서 주문 금액 전액 취소가 확인됨. 다음 보정 주기의 로컬 반영 여부를 확인한다.
- `not_refunded_done`: 조회 시점에는 취소 기록이 없는 승인 완료 상태. 이전 취소 요청 결과를 토스 대시보드·기술지원으로 확인하기 전에는 새 멱등 키로 다시 취소하거나 주문을 `paid`로 변경하지 않는다.
- `payment_not_found`, `manual_review`, `lookup_error`: 자동 판단하지 않고 토스 대시보드와 API 로그를 대조한다.

DB 직접 변경은 마지막 수단이다. 변경 전 주문 행과 토스 조회 결과를 별도로 기록하고, 전액 취소가 확인된 경우에만 `refunded`, 취소가 처리되지 않았음이 토스에서 확정된 경우에만 `paid`를 검토한다. 애매한 상태는 `refunding`으로 유지한다.

### 3. 프런트엔드 갱신

개인 PC에서 운영 `.env.local`을 사용해 빌드한다.

```powershell
Set-Location .\frontend
npm ci
npm test
npm run build
```

Sentry 소스맵을 함께 올리려면 `npm run build` 직전에 Sentry Organization Token을 셸 환경변수로만 넣고, 빌드 뒤 지운다. 토큰은 `VITE_` 접두사·`.env.local`·Git에 두지 않는다. 토큰 없이 빌드하면 소스맵 없이 정상 빌드된다.

```powershell
$env:SENTRY_AUTH_TOKEN = Read-Host "Sentry token"
npm run build
(Get-ChildItem dist -Recurse -Filter *.map).Count   # 0이어야 업로드 가능
Remove-Item Env:SENTRY_AUTH_TOKEN
```

빌드 로그에 `Successfully uploaded source maps to Sentry`가 나오고 Sentry `aram-market-web` → Project Settings → Source Maps에 묶음이 보이면 된다. 릴리스 이름은 빌드 시점의 git HEAD 해시이므로 커밋한 뒤 빌드한다.

그 다음 `dist`를 서버의 `/var/www/aram-market/frontend/dist`와 교체한다. 기존 폴더는 `dist.old`로 남겨 바로 되돌릴 수 있게 한다. 서버에 `.env.local`, `node_modules`, `.map` 파일을 올리지 않는다.

```bash
# 서버: 이전 임시 폴더 정리
rm -rf ~/dist-new
```

```powershell
# 개인 PC(frontend 폴더)
scp -i ~/.ssh/oracle_aram_market -r dist ubuntu@aram-market.duckdns.org:~/dist-new
```

```bash
# 서버: 교체와 권한
cd /var/www/aram-market/frontend && rm -rf dist.old && mv dist dist.old && mv ~/dist-new dist
find dist -type d -exec chmod 755 {} + && find dist -type f -exec chmod 644 {} + && ls dist dist/assets
# 되돌리기: mv dist dist.bad && mv dist.old dist
```

Nginx는 파일을 바로 읽으므로 재시작이 필요 없다. 확인이 끝나면 `dist.old`를 지운다.

### 4. 설정 변경 시 반영

```bash
sudo cp deploy/systemd/aram-market.service /etc/systemd/system/aram-market.service
sudo cp deploy/nginx/aram-market.conf /etc/nginx/sites-available/aram-market
sudo cp deploy/nginx/aram-market-blocked-routes.conf /etc/nginx/snippets/aram-market-blocked-routes.conf
sudo cp deploy/nginx/aram-market-cache.conf /etc/nginx/snippets/aram-market-cache.conf
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
- `/`·화면 경로 → `Cache-Control: no-cache`, 해시 번들 → `max-age=315360000`, `/assets/없는파일.js` → 404, 모든 응답에 HSTS·CSP 유지
- 브라우저 콘솔 오류 없음(재배포 직후 이전 캐시가 남은 브라우저는 한 번만 강력 새로고침)

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
- (2026-10-07) 로그인 실패 제한이 실제 접속자 IP 기준: PC에서 없는 아이디로 21회 실패 후 429, 같은 와이파이의 휴대폰도 429, 휴대폰 모바일 데이터는 일반 실패 안내. 서버 `.env`의 `TRUSTED_PROXY_IPS=127.0.0.1`과 Uvicorn `--proxy-headers --forwarded-allow-ips 127.0.0.1` 확인
- (2026-10-07) Sentry 두 프로젝트 Localhost 필터, 프런트 소스맵 업로드, 상품 카드 이미지 클릭·담기 버튼과 콘솔 경고 없음, 캐시 헤더
- (2026-10-08) 주문 환불 실제 URL 테스트(토스 테스트 결제 취소, 모든 환불 1회 시도로 완료·실패 사유 없음·환불 확인 중 0건): 고객 즉시 취소(결제완료), 취소 요청 → 거절(거절 사유 필수, 고객 화면 표시, 재요청 불가, 거절 후 배송완료까지 진행), 취소 요청 → 승인(목록 사유와 '기타' 직접 입력 사유), 관리자 직접 환불(품절·재고 부족), 거절된 상품준비중 주문의 관리자 환불, 요청 대기 중 배송중 전환 차단, 두 탭 상태 엇갈림 안내, 결제 결과 화면 새로고침, 관리자 탭 필터, 거절 후 배송완료 주문의 후기 작성. 로컬에서 승인한 결제도 운영 서버가 정상 취소해 로컬·운영 토스 테스트 키가 같음을 확인

## 남은 운영·코드 개선 항목

- (해결 2026-10-07) `aria-hidden` 접근성 경고: 원인은 모달이 아니라 상품 카드 이미지가 `aria-hidden`인 포커스 가능 버튼이었던 것. 포커스를 받지 않는 `div`로 바꿔 배포했다.
- (해결 2026-10-07) Sentry Localhost 필터 활성화, 프런트 소스맵 업로드.
- 서버 `nginx.service` 유닛 파일이 디스크에서 바뀌었다는 `daemon-reload` 안내가 나온 적이 있다. 서비스 동작에는 영향이 없으며 `sudo systemctl daemon-reload`로 정리한다.
- Gmail에서 비밀번호 재설정 메일이 스팸으로 분류된 적이 있다. 포트폴리오 운영에는 지장이 없지만 실제 서비스 전환 시 발신 도메인, SPF/DKIM/DMARC와 메일 평판을 별도로 구성한다.
- Toss 테스트 키는 포트폴리오 정책에 따라 의도적으로 유지한다. 실제 결제를 받기 전에는 라이브 키·상점 계약을 별도 적용한다. 환불은 2026-10-08 구현·운영 검증을 마쳤으며, 토스 대시보드에서 직접 취소한 건은 주문 상태에 반영되지 않으므로(웹훅 없음) 취소는 관리자 화면에서만 한다.
