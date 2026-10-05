# Oracle Cloud 배포 설정

현재 운영 구성은 Oracle Cloud Ubuntu 24.04, Nginx, systemd, Python 3.14와 DuckDNS를 사용한다.

## 파일 배치

```bash
sudo cp deploy/systemd/aram-market.service /etc/systemd/system/aram-market.service
sudo cp deploy/nginx/aram-market.conf /etc/nginx/sites-available/aram-market
sudo cp deploy/nginx/aram-market-blocked-routes.conf /etc/nginx/snippets/aram-market-blocked-routes.conf
sudo ln -s /etc/nginx/sites-available/aram-market /etc/nginx/sites-enabled/aram-market
sudo systemctl daemon-reload
sudo systemctl enable --now aram-market nginx
sudo nginx -t
sudo systemctl reload nginx
```

`backend/.env`와 `frontend/.env.local`은 비밀값을 포함하므로 Git에 추가하지 않는다. 운영 백엔드는 `FRONTEND_URL=https://aram-market.duckdns.org`, `TRUSTED_PROXY_IPS=127.0.0.1`과 새 `AUTH_SECRET_KEY`를 사용한다. 프런트는 개인 PC에서 운영 `VITE_*` 값으로 빌드한 `frontend/dist`만 서버에 업로드한다.

## HTTPS

HTTP 구성이 정상 동작하고 DuckDNS가 서버 공인 IP를 가리키는 것을 확인한 다음 인증서를 적용한다.

```bash
sudo certbot --nginx -d aram-market.duckdns.org
sudo certbot renew --dry-run
```

Certbot이 추가하는 인증서 경로와 HTTP에서 HTTPS로 보내는 리디렉션은 서버별 생성 설정이므로 이 템플릿에 포함하지 않는다.

## OCI 방화벽

Oracle Ubuntu 이미지에서는 UFW가 OCI 필수 규칙을 제거할 수 있으므로 사용하지 않는다. OCI 보안 목록에서 TCP 80·443을 열고, 기존 `/etc/iptables/rules.v4`의 INPUT REJECT 규칙 앞에도 TCP 80·443 허용 규칙을 추가한 뒤 `iptables-save`로 저장한다. FastAPI의 8000번 포트는 외부에 열지 않는다.

## 배포 확인

```bash
curl -fsS https://aram-market.duckdns.org/api/health
systemctl is-active aram-market nginx
sudo ss -lntp | grep -E '(:22|:80|:443|:8000)'
```

정상 상태에서는 `/api/health`가 `{"status":"ok"}`를 반환하고, `/docs`, `/redoc`, `/openapi.json`은 404이며, 8000번 포트는 `127.0.0.1`에서만 수신한다.
