# SMTP 기반 아이디 안내·계정 잠금 해제·비밀번호 재설정 메일 발송

import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import quote

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
        f"{settings.backend_public_url.rstrip('/')}/api/users/unlock"
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
    message["Subject"] = "[Product Management] 계정 잠금 해제 안내"
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = user.email
    message.set_content(
        f"{user.nickname}님, 로그인 오류로 계정이 잠겼습니다.\n"
        f"아래 주소를 열어 즉시 잠금을 해제해 주세요.\n{unlock_url}\n"
        f"링크는 {settings.unlock_token_expire_minutes}분 동안 유효합니다."
    )
    message.add_alternative(html, subtype="html")

    await asyncio.to_thread(_send_message, message)
    return True


# 가입 이메일로 비밀번호 재설정 링크 발송
async def send_password_reset_email(user: User, token: str) -> bool:
    if not settings.smtp_host or not settings.smtp_from_email:
        return False

    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={quote(token)}"
    template = Template((TEMPLATE_DIRECTORY / "password_reset.html").read_text(encoding="utf-8"))
    html = template.safe_substitute(
        nickname=escape(user.nickname),
        username=escape(user.username),
        reset_url=escape(reset_url, quote=True),
        expire_minutes=settings.password_reset_token_expire_minutes,
    )

    message = EmailMessage()
    message["Subject"] = "[Product Management] 비밀번호 재설정 안내"
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
        login_url=escape(f"{settings.frontend_url.rstrip('/')}/login", quote=True),
    )

    message = EmailMessage()
    message["Subject"] = "[Product Management] 아이디 안내"
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = user.email
    message.set_content(
        f"{user.nickname}님의 아이디는 {user.username}입니다.\n"
        f"로그인: {settings.frontend_url.rstrip('/')}/login"
    )
    message.add_alternative(html, subtype="html")

    await asyncio.to_thread(_send_message, message)
    return True
