# 관리자 로그인 요청을 서버 메모리에서 IP와 IP·아이디 조합별로 제한

import hashlib
import hmac
import math
import threading
import time
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Callable

from backend.core.config import settings


OBSERVATION_SECONDS = 60 * 60  # 마지막 실패 후 1시간 동안 단계적 제한 횟수 유지
MAX_TRACKED_KEYS = 10_000  # 무제한 키 생성으로 인한 로컬 메모리 증가 방지


# 하나의 제한 버킷에 누적되는 실패 상태
@dataclass
class AttemptState:
    failure_count: int
    last_failure_at: float
    blocked_until: float


# 실패 기록 후 프런트 응답과 보안 로그에 필요한 결과
@dataclass(frozen=True)
class FailureResult:
    retry_after: int
    pair_failure_count: int
    ip_failure_count: int
    distinct_admin_ips: int
    client_fingerprint: str


# 배포 전 로컬 환경에서 사용하는 서버 프로세스 단위 로그인 제한기
class LoginRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._ip_attempts: dict[str, AttemptState] = {}
        self._pair_attempts: dict[str, AttemptState] = {}
        self._admin_ip_activity: dict[str, float] = {}
        self._lock = threading.Lock()

    # 현재 IP 또는 IP·아이디 조합에 남은 제한시간 조회
    def retry_after(self, client_ip: str, username: str) -> int:
        now = self._clock()
        ip_key, pair_key, _ = self._keys(client_ip, username)
        with self._lock:
            self._prune_stale(now)
            return max(
                self._state_retry_after(self._ip_attempts.get(ip_key), now),
                self._state_retry_after(self._pair_attempts.get(pair_key), now),
            )

    # 실패를 두 독립 버킷에 기록하고 새로 적용된 제한시간 반환
    def record_failure(self, client_ip: str, username: str) -> FailureResult:
        now = self._clock()
        normalized_username = username.strip().lower()
        ip_key, pair_key, fingerprint = self._keys(client_ip, normalized_username)
        with self._lock:
            self._prune_stale(now)
            ip_state = self._increment(self._ip_attempts, ip_key, now)
            pair_state = self._increment(self._pair_attempts, pair_key, now)
            if normalized_username == "admin":
                self._admin_ip_activity[ip_key] = now
            self._enforce_capacity(self._ip_attempts)
            self._enforce_capacity(self._pair_attempts)
            retry_after = max(
                self._state_retry_after(ip_state, now),
                self._state_retry_after(pair_state, now),
            )
            return FailureResult(
                retry_after=retry_after,
                pair_failure_count=pair_state.failure_count,
                ip_failure_count=ip_state.failure_count,
                distinct_admin_ips=len(self._admin_ip_activity),
                client_fingerprint=fingerprint,
            )

    # 정상 로그인한 IP와 IP·아이디 조합의 실패 기록 초기화
    def reset(self, client_ip: str, username: str) -> None:
        ip_key, pair_key, _ = self._keys(client_ip, username)
        with self._lock:
            self._ip_attempts.pop(ip_key, None)
            self._pair_attempts.pop(pair_key, None)
            self._admin_ip_activity.pop(ip_key, None)

    # 다섯 번째 실패부터 30초·1분·5분·1시간 제한시간 결정
    @staticmethod
    def _penalty_seconds(failure_count: int) -> int:
        if failure_count < 5:
            return 0
        if failure_count == 5:
            return 30
        if failure_count == 6:
            return 60
        if failure_count == 7:
            return 5 * 60
        return 60 * 60

    # 기존 관찰시간이 끝났으면 새 상태로 실패 횟수 누적
    def _increment(self, states: dict[str, AttemptState], key: str, now: float) -> AttemptState:
        state = states.get(key)
        if not state or now - state.last_failure_at >= OBSERVATION_SECONDS:
            state = AttemptState(failure_count=0, last_failure_at=now, blocked_until=0)
        state.failure_count += 1
        state.last_failure_at = now
        state.blocked_until = now + self._penalty_seconds(state.failure_count)
        states[key] = state
        return state

    # 저장 상태에서 올림 처리한 남은 제한 초 계산
    @staticmethod
    def _state_retry_after(state: AttemptState | None, now: float) -> int:
        if not state or state.blocked_until <= now:
            return 0
        return max(1, math.ceil(state.blocked_until - now))

    # 원문 IP를 저장하지 않도록 정규화 후 HMAC 지문과 버킷 키 생성
    @staticmethod
    def _keys(client_ip: str, username: str) -> tuple[str, str, str]:
        try:
            normalized_ip = str(ip_address(client_ip))
        except ValueError:
            normalized_ip = client_ip.strip().lower() or "unknown"
        fingerprint = hmac.new(
            settings.auth_secret_key.encode(),
            normalized_ip.encode(),
            hashlib.sha256,
        ).hexdigest()
        normalized_username = username.strip().lower()
        pair_key = hmac.new(
            settings.auth_secret_key.encode(),
            f"{normalized_ip}|{normalized_username}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return fingerprint, pair_key, fingerprint[:12]

    # 관찰시간이 끝난 실패 기록과 관리자 IP 활동 제거
    def _prune_stale(self, now: float) -> None:
        for states in (self._ip_attempts, self._pair_attempts):
            stale_keys = [key for key, state in states.items() if now - state.last_failure_at >= OBSERVATION_SECONDS]
            for key in stale_keys:
                states.pop(key, None)
        stale_admin_ips = [
            key for key, last_seen in self._admin_ip_activity.items() if now - last_seen >= OBSERVATION_SECONDS
        ]
        for key in stale_admin_ips:
            self._admin_ip_activity.pop(key, None)

    # 제한된 메모리 크기를 넘으면 가장 오래된 실패 기록부터 제거
    @staticmethod
    def _enforce_capacity(states: dict[str, AttemptState]) -> None:
        overflow = len(states) - MAX_TRACKED_KEYS
        if overflow <= 0:
            return
        oldest_keys = sorted(states, key=lambda key: states[key].last_failure_at)[:overflow]
        for key in oldest_keys:
            states.pop(key, None)


admin_login_limiter = LoginRateLimiter()  # 단일 FastAPI 프로세스에서 공유하는 로컬 제한 저장소
