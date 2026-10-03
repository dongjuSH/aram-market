# 고객용 아이디 안내·계정 잠금 해제·비밀번호 재설정·보안 알림 메일 발송

import asyncio
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import quote
from zoneinfo import ZoneInfo

from backend.core.config import settings
from backend.domain.users.models.users import User


TEMPLATE_DIRECTORY = Path(__file__).resolve().parent.parent / "templates"  # 사용자 메일 HTML 템플릿 위치


# 포트 설정에 따른 SSL 또는 STARTTLS SMTP 메시지 동기 발송
def _send_message(message: EmailMessage) -> None:
    smtp_class = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_port != 465 and settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


# 로그인 5회 실패 계정의 즉시 잠금 해제 링크 발송
async def send_account_unlock_email(user: User, token: str) -> bool:
    if not settings.smtp_host or not settings.smtp_from_email:
        return False

    unlock_url = (
        f"{settings.frontend_url.rstrip('/')}/user/unlock"
        f"?token={quote(token)}"
    )
    template = Template((TEMPLATE_DIRECTORY / "account_unlock.html").read_text(encoding="utf-8"))
    html = template.safe_substitute(
        nickname=escape(user.nickname),
        username=escape(user.username),
        unlock_url=escape(unlock_url, quote=True),
        expire_minutes=settings.unlock_token_expire_minutes,
    )

    message = EmailMessage()
    message["Subject"] = "[아람 마켓] 계정 잠금 해제 안내"
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = user.email
    message.set_content(
        f"{user.nickname}님, 로그인 오류로 계정이 잠겼습니다.\n"
        f"아래 주소를 열고 화면의 버튼을 눌러 잠금을 해제해 주세요.\n{unlock_url}\n"
        f"링크는 {settings.unlock_token_expire_minutes}분 동안 유효합니다."
    )
    message.add_alternative(html, subtype="html")

    await asyncio.to_thread(_send_message, message)
    return True


# 가입 이메일로 비밀번호 재설정 링크 발송
async def send_password_reset_email(user: User, token: str) -> bool:
    if not settings.smtp_host or not settings.smtp_from_email:
        return False

    reset_url = f"{settings.frontend_url.rstrip('/')}/user/reset-password?token={quote(token)}"
    template = Template((TEMPLATE_DIRECTORY / "password_reset.html").read_text(encoding="utf-8"))
    html = template.safe_substitute(
        nickname=escape(user.nickname),
        username=escape(user.username),
        reset_url=escape(reset_url, quote=True),
        expire_minutes=settings.password_reset_token_expire_minutes,
    )

    message = EmailMessage()
    message["Subject"] = "[아람 마켓] 비밀번호 재설정 안내"
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = user.email
    message.set_content(
        f"{user.nickname}님, 아래 주소에서 비밀번호를 재설정해 주세요.\n{reset_url}\n"
        f"링크는 {settings.password_reset_token_expire_minutes}분 동안 유효합니다."
    )
    message.add_alternative(html, subtype="html")

    await asyncio.to_thread(_send_message, message)
    return True


# 화면 노출 없이 가입 이메일로만 아이디 안내
async def send_username_reminder_email(user: User) -> bool:
    if not settings.smtp_host or not settings.smtp_from_email:
        return False

    template = Template((TEMPLATE_DIRECTORY / "username_reminder.html").read_text(encoding="utf-8"))
    html = template.safe_substitute(
        nickname=escape(user.nickname),
        username=escape(user.username),
        login_url=escape(f"{settings.frontend_url.rstrip('/')}/user/login", quote=True),
    )

    message = EmailMessage()
    message["Subject"] = "[아람 마켓] 아이디 안내"
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = user.email
    message.set_content(
        f"{user.nickname}님의 아이디는 {user.username}입니다.\n"
        f"로그인: {settings.frontend_url.rstrip('/')}/user/login"
    )
    message.add_alternative(html, subtype="html")

    await asyncio.to_thread(_send_message, message)
    return True


# 가입 이메일 소유 확인 링크 발송
async def send_email_verification_email(user: User, token: str) -> bool:
    if not settings.smtp_host or not settings.smtp_from_email:
        return False

    verify_url = f"{settings.frontend_url.rstrip('/')}/user/verify-email?token={quote(token)}"
    expire_hours = max(1, settings.email_verification_token_expire_minutes // 60)
    template = Template((TEMPLATE_DIRECTORY / "email_verification.html").read_text(encoding="utf-8"))
    html = template.safe_substitute(
        nickname=escape(user.nickname),
        verify_url=escape(verify_url, quote=True),
        expire_hours=expire_hours,
    )

    message = EmailMessage()
    message["Subject"] = "[아람 마켓] 이메일 인증 안내"
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = user.email
    message.set_content(
        f"{user.nickname}님, 아래 주소를 열어 이메일 인증을 완료해 주세요.\n{verify_url}\n"
        f"링크는 {expire_hours}시간 동안 유효하며, 기간 내 인증하지 않으면 가입 정보가 삭제됩니다."
    )
    message.add_alternative(html, subtype="html")

    await asyncio.to_thread(_send_message, message)
    return True


# 마이 페이지 이메일 변경 시 새 이메일 주소로 소유 확인 링크 발송
async def send_email_change_email(user: User, new_email: str, token: str) -> bool:
    if not settings.smtp_host or not settings.smtp_from_email:
        return False

    confirm_url = f"{settings.frontend_url.rstrip('/')}/user/verify-email?type=email-change&token={quote(token)}"
    expire_hours = max(1, settings.email_verification_token_expire_minutes // 60)
    template = Template((TEMPLATE_DIRECTORY / "email_change.html").read_text(encoding="utf-8"))
    html = template.safe_substitute(
        nickname=escape(user.nickname),
        verify_url=escape(confirm_url, quote=True),
        new_email=escape(new_email),
        expire_hours=expire_hours,
    )

    message = EmailMessage()
    message["Subject"] = "[아람 마켓] 이메일 변경 확인 안내"
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = new_email
    message.set_content(
        f"{user.nickname}님, 아람 마켓 계정의 이메일을 {new_email}(으)로 변경하려면 아래 주소를 열어 확인해 주세요.\n{confirm_url}\n"
        f"링크는 {expire_hours}시간 동안 유효합니다. 본인이 요청하지 않았다면 이 메일을 무시해 주세요."
    )
    message.add_alternative(html, subtype="html")

    await asyncio.to_thread(_send_message, message)
    return True


# 비밀번호·이메일 변경, 탈퇴 신청 같은 계정 보안 변경을 알림(이메일 변경은 바뀌기 전 주소로 발송)
async def send_security_notice_email(user: User, to_email: str, title: str, message_text: str) -> bool:
    if not settings.smtp_host or not settings.smtp_from_email:
        return False

    occurred_at = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    login_url = f"{settings.frontend_url.rstrip('/')}/user/login"
    template = Template((TEMPLATE_DIRECTORY / "security_notice.html").read_text(encoding="utf-8"))
    html = template.safe_substitute(
        title=escape(title),
        nickname=escape(user.nickname),
        username=escape(user.username),
        message=escape(message_text),
        occurred_at=occurred_at,
        login_url=escape(login_url, quote=True),
    )

    message = EmailMessage()
    message["Subject"] = f"[아람 마켓] {title}"
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = to_email
    message.set_content(
        f"{user.nickname}님({user.username}) 계정에서 변경이 있었습니다.\n{message_text}\n"
        f"변경 시각: {occurred_at} (한국 시간)\n"
        f"본인이 한 변경이 아니라면 즉시 비밀번호를 재설정해 주세요: {login_url}"
    )
    message.add_alternative(html, subtype="html")

    await asyncio.to_thread(_send_message, message)
    return True
