"""Email service for AMINRA.

Sender abstraction enables easy testing:
- AiosmtplibSender: real SMTP via aiosmtplib (production)
- LoggingSender: dry-run, just logs (set EMAIL_ENABLED=false in dev)
- CapturingSender: in-memory list (used by unit tests)

Templates live at backend/templates/emails/{name}.{lang}.{html,txt}.
Each template is rendered via Jinja2 with the supplied context dict.
The first non-empty line of the rendered .txt file is treated as the subject.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

log = logging.getLogger("aminra.mailer")

DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"


# ── Config ──────────────────────────────────────────────────────────────────

@dataclass
class MailerConfig:
    enabled: bool = False
    host: str = "smtp.example.com"
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    from_email: str = "noreply@aminra.vn"
    from_name: str = "AMINRA"
    default_lang: str = "vi"
    app_base_url: str = "http://localhost:3100"
    template_dir: Path = field(default_factory=lambda: DEFAULT_TEMPLATE_DIR)

    @classmethod
    def from_env(cls) -> "MailerConfig":
        return cls(
            enabled=os.getenv("EMAIL_ENABLED", "false").lower() == "true",
            host=os.getenv("SMTP_HOST", "smtp.example.com"),
            port=int(os.getenv("SMTP_PORT", "587")),
            username=os.getenv("SMTP_USER", ""),
            password=os.getenv("SMTP_PASSWORD", ""),
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            from_email=os.getenv("SMTP_FROM_EMAIL", "noreply@aminra.vn"),
            from_name=os.getenv("SMTP_FROM_NAME", "AMINRA"),
            default_lang=os.getenv("DEFAULT_EMAIL_LANG", "vi"),
            app_base_url=os.getenv("APP_BASE_URL", "http://localhost:3100"),
        )


# ── Sender abstraction ──────────────────────────────────────────────────────

class Sender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class AiosmtplibSender:
    """Production sender — opens a fresh connection per message (simple, reliable)."""

    def __init__(self, config: MailerConfig):
        self.config = config

    async def send(self, message: EmailMessage) -> None:
        await aiosmtplib.send(
            message,
            hostname=self.config.host,
            port=self.config.port,
            username=self.config.username or None,
            password=self.config.password or None,
            start_tls=self.config.use_tls,
        )


class LoggingSender:
    """Dry-run sender for dev/CI — logs the email instead of sending."""

    async def send(self, message: EmailMessage) -> None:
        log.info(
            "[mailer:dry-run] to=%s subject=%r body_preview=%r",
            message["To"],
            message["Subject"],
            (message.get_body(preferencelist=("plain",)).get_content()[:120]
             if message.get_body(preferencelist=("plain",)) else ""),
        )


class CapturingSender:
    """Test sender — keeps every sent message in `outbox`."""

    def __init__(self):
        self.outbox: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)


# ── Mailer ──────────────────────────────────────────────────────────────────

class TemplateError(Exception):
    """Raised when a requested email template is missing or malformed."""


class Mailer:
    def __init__(self, config: MailerConfig, sender: Sender | None = None):
        self.config = config
        self.sender = sender or self._default_sender()
        self.env = Environment(
            loader=FileSystemLoader(str(config.template_dir)),
            autoescape=select_autoescape(["html"]),
            keep_trailing_newline=True,
        )

    def _default_sender(self) -> Sender:
        return AiosmtplibSender(self.config) if self.config.enabled else LoggingSender()

    # ── Public API ──────────────────────────────────────────────────────────

    async def send_template(
        self,
        to: str,
        template: str,
        context: dict | None = None,
        lang: str | None = None,
    ) -> bool:
        """Render a template + send. Returns True on success, False on transport error.

        Template lookup falls back to default_lang if requested lang missing.
        """
        ctx = self._build_context(context or {})
        lang = lang or self.config.default_lang
        subject, html_body, text_body = self.render(template, ctx, lang)
        message = self.build_message(to, subject, html_body, text_body)
        return await self._send_with_logging(message)

    def render(self, template: str, context: dict, lang: str) -> tuple[str, str, str]:
        """Render html + txt templates. Subject = first non-empty line of txt body."""
        text_template = self._load(template, lang, "txt")
        html_template = self._load(template, lang, "html")
        text_body = text_template.render(**context)
        html_body = html_template.render(**context)
        subject, body = self._split_subject(text_body)
        return subject, html_body, body

    def build_message(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
        return msg

    # ── Internal ────────────────────────────────────────────────────────────

    def _build_context(self, extra: dict) -> dict:
        return {
            "app_base_url": self.config.app_base_url,
            "from_name": self.config.from_name,
            **extra,
        }

    def _load(self, template: str, lang: str, ext: str):
        try:
            return self.env.get_template(f"{template}.{lang}.{ext}")
        except TemplateNotFound:
            if lang != self.config.default_lang:
                try:
                    return self.env.get_template(f"{template}.{self.config.default_lang}.{ext}")
                except TemplateNotFound:
                    pass
            raise TemplateError(f"Template not found: {template}.{lang}.{ext}")

    @staticmethod
    def _split_subject(text_body: str) -> tuple[str, str]:
        lines = text_body.splitlines()
        subject = ""
        body_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("Subject:"):
                continue
            if stripped.startswith("Subject:"):
                subject = stripped[len("Subject:"):].strip()
                body_start = i + 1
                break
        if not subject:
            raise TemplateError(
                "Email .txt template must start with a 'Subject: ...' line"
            )
        # Skip blank line after the subject header if present
        while body_start < len(lines) and not lines[body_start].strip():
            body_start += 1
        body = "\n".join(lines[body_start:]).strip() + "\n"
        return subject, body

    async def _send_with_logging(self, message: EmailMessage) -> bool:
        try:
            await self.sender.send(message)
            log.info("[mailer] sent to=%s subject=%r", message["To"], message["Subject"])
            return True
        except Exception as e:
            log.exception("[mailer] send failed to=%s err=%s", message["To"], e)
            return False


# ── Module-level singleton (lazy) ───────────────────────────────────────────

_default_mailer: Mailer | None = None


def get_mailer() -> Mailer:
    """FastAPI dependency. Reads env on first call; pass override in tests."""
    global _default_mailer
    if _default_mailer is None:
        _default_mailer = Mailer(MailerConfig.from_env())
    return _default_mailer


def reset_mailer() -> None:
    """For tests — clear the singleton between cases."""
    global _default_mailer
    _default_mailer = None
