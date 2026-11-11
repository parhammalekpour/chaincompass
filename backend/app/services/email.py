import asyncio
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeEmailMessage
from pathlib import Path
from typing import Protocol

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)
TEMPLATE_DIRECTORY = Path(__file__).resolve().parents[1] / "templates"
templates = Environment(
    loader=FileSystemLoader(TEMPLATE_DIRECTORY),
    autoescape=select_autoescape(("html",)),
)


@dataclass(frozen=True)
class OutgoingEmail:
    recipient: str
    subject: str
    text: str
    html: str


class EmailSender(Protocol):
    async def send(self, message: OutgoingEmail) -> None: ...


class ConsoleFileEmailSender:
    def __init__(self, mail_directory: Path | None = None) -> None:
        self.mail_directory = mail_directory or (
            Path(__file__).resolve().parents[2] / ".dev-mail"
        )

    async def send(self, message: OutgoingEmail) -> None:
        await asyncio.to_thread(self._write_and_print, message)

    def _write_and_print(self, message: OutgoingEmail) -> None:
        self.mail_directory.mkdir(parents=True, exist_ok=True)
        content = (
            f"To: {message.recipient}\nSubject: {message.subject}\n"
            f"Content-Type: multipart/alternative\n\n"
            f"--- text/plain ---\n{message.text}\n"
            f"--- text/html ---\n{message.html}\n"
        )
        path = self.mail_directory / "latest.eml"
        path.write_text(content, encoding="utf-8")
        print(f"Development email saved: {path.name}\n{content}")


class SmtpEmailSender:
    async def send(self, message: OutgoingEmail) -> None:
        await asyncio.to_thread(self._send_sync, message)

    @staticmethod
    def _send_sync(message: OutgoingEmail) -> None:
        email = MimeEmailMessage()
        email["Subject"] = message.subject
        email["From"] = settings.smtp_from
        email["To"] = message.recipient
        email.set_content(message.text)
        email.add_alternative(message.html, subtype="html")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(email)


def build_auth_email(
    locale: str,
    kind: str,
    link: str | None = None,
) -> OutgoingEmail:
    normalized_locale = "fa" if locale == "fa" else "en"
    values = {"kind": kind, "link": link or ""}
    subject_template = templates.get_template(
        f"{normalized_locale}/auth_email_subject.j2"
    )
    text_template = templates.get_template(f"{normalized_locale}/auth_email.txt.j2")
    html_template = templates.get_template(f"{normalized_locale}/auth_email.html.j2")
    return OutgoingEmail(
        recipient="",
        subject=subject_template.render(**values).strip(),
        text=text_template.render(**values).strip(),
        html=html_template.render(**values).strip(),
    )


def email_for(
    recipient: str,
    locale: str,
    kind: str,
    link: str | None = None,
) -> OutgoingEmail:
    template = build_auth_email(locale, kind, link)
    return OutgoingEmail(
        recipient=recipient,
        subject=template.subject,
        text=template.text,
        html=template.html,
    )


def get_email_sender() -> EmailSender:
    if settings.app_env.strip().lower() in {"development", "dev", "test", "local"}:
        return ConsoleFileEmailSender()
    return SmtpEmailSender()


async def send_email_safely(sender: EmailSender, message: OutgoingEmail) -> None:
    try:
        await sender.send(message)
    except Exception as exc:
        logger.warning("Background email delivery failed (%s)", type(exc).__name__)
