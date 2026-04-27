"""Integration tests for mailer.

Spins up a real (in-process) SMTP server using aiosmtpd, points
AiosmtplibSender at it, and verifies the email actually flows over the
socket. Catches issues unit tests can't: TLS negotiation, connection
errors, malformed RFC822 envelope, etc.
"""
from __future__ import annotations

import asyncio
import socket
from email import message_from_bytes, policy
from email.message import EmailMessage

import pytest
from aiosmtpd.controller import Controller

from services.mailer import (
    AiosmtplibSender,
    Mailer,
    MailerConfig,
)


# ── Fake SMTP server ────────────────────────────────────────────────────────

class _CapturingHandler:
    """aiosmtpd handler that captures every received message."""

    def __init__(self):
        self.received: list[EmailMessage] = []

    async def handle_DATA(self, server, session, envelope):
        # policy.default → unicode-aware Subject + working get_body() / get_content()
        msg = message_from_bytes(envelope.content, policy=policy.default)
        msg["X-Envelope-To"] = ", ".join(envelope.rcpt_tos)
        msg["X-Envelope-From"] = envelope.mail_from
        self.received.append(msg)
        return "250 OK"


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def smtp_server():
    """Start aiosmtpd on a random port for the duration of one test."""
    handler = _CapturingHandler()
    port = _free_port()
    controller = Controller(handler, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        yield handler, port
    finally:
        controller.stop()


@pytest.fixture
def integration_cfg(smtp_server):
    _, port = smtp_server
    return MailerConfig(
        enabled=True,
        host="127.0.0.1",
        port=port,
        username="",
        password="",
        use_tls=False,  # plain SMTP — aiosmtpd default has no TLS
        from_email="noreply@aminra.vn",
        from_name="AMINRA",
        default_lang="vi",
        app_base_url="https://app.aminra.vn",
    )


# ── Tests ───────────────────────────────────────────────────────────────────

class TestRealSmtpDelivery:
    async def test_password_reset_email_lands_on_smtp_server(
        self, integration_cfg: MailerConfig, smtp_server
    ):
        handler, _ = smtp_server
        mailer = Mailer(integration_cfg, sender=AiosmtplibSender(integration_cfg))

        ok = await mailer.send_template(
            to="biz@example.vn",
            template="password_reset",
            context={
                "reset_url": "https://app.aminra.vn/reset?t=integration-token",
                "user_name": "Anh Tuan",
                "ttl_minutes": 60,
            },
            lang="vi",
        )

        assert ok is True
        assert len(handler.received) == 1
        msg = handler.received[0]
        assert msg["X-Envelope-From"] == "noreply@aminra.vn"
        assert "biz@example.vn" in msg["X-Envelope-To"]
        assert msg["Subject"] == "[AMINRA] Yêu cầu đặt lại mật khẩu"

        plain = msg.get_body(preferencelist=("plain",)).get_content()
        assert "https://app.aminra.vn/reset?t=integration-token" in plain
        assert "Anh Tuan" in plain

        html = msg.get_body(preferencelist=("html",)).get_content()
        assert 'href="https://app.aminra.vn/reset?t=integration-token"' in html

    async def test_send_returns_false_when_smtp_unreachable(self):
        """Pointing at a closed port — aiosmtplib should fail; mailer returns False."""
        port = _free_port()  # pick a free port, don't bind it
        cfg = MailerConfig(
            enabled=True,
            host="127.0.0.1",
            port=port,
            use_tls=False,
        )
        mailer = Mailer(cfg, sender=AiosmtplibSender(cfg))
        ok = await mailer.send_template(
            to="x@example.vn",
            template="password_reset",
            context={"reset_url": "https://x"},
        )
        assert ok is False

    async def test_concurrent_sends_all_arrive(
        self, integration_cfg: MailerConfig, smtp_server
    ):
        """Send 5 messages in parallel, all 5 should land at the SMTP server."""
        handler, _ = smtp_server
        mailer = Mailer(integration_cfg, sender=AiosmtplibSender(integration_cfg))

        async def send_one(i: int):
            return await mailer.send_template(
                to=f"user{i}@example.vn",
                template="password_reset",
                context={"reset_url": f"https://app.aminra.vn/reset?t={i}"},
            )

        results = await asyncio.gather(*(send_one(i) for i in range(5)))
        assert all(results)
        assert len(handler.received) == 5

        recipients = sorted(msg["X-Envelope-To"] for msg in handler.received)
        assert recipients == [f"user{i}@example.vn" for i in range(5)]

    async def test_email_verification_template_also_works(
        self, integration_cfg: MailerConfig, smtp_server
    ):
        """Smoke-check the second template ships end-to-end too."""
        handler, _ = smtp_server
        mailer = Mailer(integration_cfg, sender=AiosmtplibSender(integration_cfg))

        ok = await mailer.send_template(
            to="newuser@example.vn",
            template="email_verification",
            context={
                "verify_url": "https://app.aminra.vn/verify?t=abc",
                "user_name": "New User",
                "ttl_minutes": 1440,
            },
            lang="en",
        )
        assert ok is True
        msg = handler.received[0]
        assert msg["Subject"] == "[AMINRA] Verify your email address"
        assert "https://app.aminra.vn/verify?t=abc" in msg.get_body(
            preferencelist=("plain",)
        ).get_content()
