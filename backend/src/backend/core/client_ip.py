# 신뢰한 리버스 프록시가 전달한 X-Forwarded-For에서만 실제 접속 IP를 계산

from ipaddress import ip_address, ip_network

from fastapi import Request

from backend.core.config import settings


# 문자열 IP가 신뢰 프록시 목록(IP 또는 대역)에 속하는지 확인
def _is_trusted(value: str) -> bool:
    try:
        address = ip_address(value.strip())
    except ValueError:
        return False
    for entry in settings.trusted_proxy_ips:
        try:
            if address in ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


# 직접 접속 IP가 신뢰 프록시일 때만 X-Forwarded-For를 오른쪽부터 읽어 처음 나오는 비신뢰 IP를 사용
def get_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if not _is_trusted(peer):
        return peer  # 임의로 붙인 X-Forwarded-For는 무시
    forwarded = [item.strip() for item in request.headers.get("x-forwarded-for", "").split(",") if item.strip()]
    for candidate in reversed(forwarded):
        if not _is_trusted(candidate):
            return candidate
    return peer
