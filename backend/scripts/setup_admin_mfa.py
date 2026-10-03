# 터미널에서 admin 계정의 TOTP 2단계 인증을 등록·해제·확인(비밀값과 복구 코드는 화면에 한 번만 표시)

import argparse
import asyncio
from datetime import datetime, timezone

import qrcode
from sqlalchemy import select

from backend.core.database import async_session, engine
from backend.domain.admins.models.admins import AdminAccount
from backend.domain.admins.services.mfa import (
    encrypt_secret,
    generate_recovery_codes,
    generate_secret,
    hash_recovery_code,
    matching_step,
    provisioning_uri,
)


ADMIN_USERNAME = "admin"
MAX_CONFIRM_ATTEMPTS = 3


# 터미널 입력은 동기 함수라 별도 스레드에서 받아 비동기 흐름(DB 세션)을 막지 않음
async def ask(prompt: str) -> str:
    return (await asyncio.to_thread(input, prompt)).strip()


# 휴대폰 카메라로 스캔할 수 있도록 등록 주소를 터미널에 QR 코드로 출력(어두운 배경 터미널은 색을 반전)
def print_qr(uri: str, dark_terminal: bool) -> None:
    qr = qrcode.QRCode(border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    qr.print_ascii(invert=dark_terminal)


# 등록: 비밀값 생성 → QR·설정 키 표시 → 앱의 현재 코드로 확인 → 복구 코드 발급 후 저장(기존 로그인 세션 모두 종료)
async def enroll(admin: AdminAccount, dark_terminal: bool = False) -> None:
    if admin.mfa_enabled_at and await ask("이미 등록되어 있습니다. 새 비밀값으로 교체할까요? (yes 입력): ") != "yes":
        print("취소했습니다.")
        return

    secret = generate_secret()
    print("\nGoogle Authenticator에서 [+] → [QR 코드 스캔]으로 아래 코드를 스캔하세요.")
    print("스캔이 안 되면 --dark-terminal 옵션을 바꿔 다시 실행하거나 아래 설정 키를 입력하세요.\n")
    print_qr(provisioning_uri(secret, ADMIN_USERNAME), dark_terminal)
    grouped = " ".join(secret[index : index + 4] for index in range(0, len(secret), 4))
    print(f"\nQR을 쓸 수 없으면 [설정 키 입력] → 계정 이름 'admin', 키: {grouped} (시간 기준)\n")

    for _ in range(MAX_CONFIRM_ATTEMPTS):
        step = matching_step(secret, await ask("앱에 표시된 6자리 코드: "))
        if step is not None:
            break
        print("코드가 일치하지 않습니다. 앱의 현재 코드를 다시 입력해 주세요.")
    else:
        print("확인에 실패해 등록하지 않았습니다. 휴대폰 시간이 자동 설정인지 확인한 뒤 다시 실행해 주세요.")
        return

    recovery_codes = generate_recovery_codes()
    admin.mfa_secret_encrypted = encrypt_secret(secret)
    admin.mfa_enabled_at = datetime.now(timezone.utc)
    admin.mfa_last_used_step = step  # 등록 확인에 쓴 코드로는 로그인할 수 없음
    admin.mfa_recovery_code_hashes = [hash_recovery_code(code) for code in recovery_codes]
    admin.auth_version += 1  # 2단계 인증 없이 로그인된 기존 세션 종료

    print("\n복구 코드(휴대폰을 잃어버렸을 때 6자리 코드 대신 한 번씩 사용). 지금만 표시되니 안전한 곳에 보관하세요:")
    for code in recovery_codes:
        print(f"  {code}")
    print("\n2단계 인증을 등록했습니다. 기존 관리자 로그인은 모두 종료되었습니다.")


# 해제: 휴대폰과 복구 코드를 모두 잃어버렸을 때 서버 관리자가 직접 해제
async def disable(admin: AdminAccount) -> None:
    if await ask("2단계 인증을 해제하려면 disable 을 입력하세요: ") != "disable":
        print("취소했습니다.")
        return
    admin.mfa_secret_encrypted = None
    admin.mfa_enabled_at = None
    admin.mfa_last_used_step = None
    admin.mfa_recovery_code_hashes = []
    admin.auth_version += 1
    print("2단계 인증을 해제했습니다. 다시 등록해 주세요.")


async def run(action: str, dark_terminal: bool) -> None:
    async with async_session() as session:
        admin = (await session.execute(select(AdminAccount).where(AdminAccount.username == ADMIN_USERNAME))).scalar_one_or_none()
        if admin is None:
            raise RuntimeError("admin 계정이 없습니다. scripts/create_admin.py를 먼저 실행해 주세요.")
        if action == "status":
            enabled = admin.mfa_enabled_at is not None
            print(f"mfa_enabled={str(enabled).lower()} recovery_codes_remaining={len(admin.mfa_recovery_code_hashes or [])}")
        elif action == "disable":
            await disable(admin)
        else:
            await enroll(admin, dark_terminal)
        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="admin TOTP 2단계 인증 등록·해제·상태 확인")
    parser.add_argument("action", nargs="?", choices=("enroll", "disable", "status"), default="enroll")
    parser.add_argument("--dark-terminal", action="store_true", help="검은 배경 터미널에서 QR 색 반전")
    arguments = parser.parse_args()
    asyncio.run(run(arguments.action, arguments.dark_terminal))
