# 비밀값 출력·메일 발송 없는 SMTP 연결 및 인증 점검

import smtplib

from backend.core.config import settings


# 메일 발송 없는 SMTP TLS 연결 및 계정 인증
def run() -> None:
    smtp_class = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.ehlo()
        if settings.smtp_port != 465 and settings.smtp_use_tls:
            smtp.starttls()
            smtp.ehlo()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
    print("smtp_connection=ok, smtp_authentication=ok, email_sent=no")


if __name__ == "__main__":
    run()
