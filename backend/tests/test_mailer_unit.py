"""Unit tests for backend/services/mailer.py.

No network. Templates are real (loaded from disk) so we also catch template regressions.
"""
from __future__ import annotations

import logging
from email.message import EmailMessage
from pathlib import Path

import pytest

from services.mailer import (
    CapturingSender,
    LoggingSender,
    Mailer,
    MailerConfig,
    TemplateError,
    get_mailer,
    reset_mailer,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def cfg() -> MailerConfig:
    return MailerConfig(
        enabled=False,
        from_email="noreply@aminra.vn",
        from_name="AMINRA",
        default_lang="vi",
        app_base_url="https://app.aminra.vn",
    )


@pytest.fixture
def capturing() -> CapturingSender:
    return CapturingSender()


@pytest.fixture
def mailer(cfg: MailerConfig, capturing: CapturingSender) -> Mailer:
    return Mailer(cfg, sender=capturing)


# ── Template rendering ──────────────────────────────────────────────────────

class TestRender:
    def test_renders_password_reset_vi_with_subject_html_text(self, mailer: Mailer):
        subject, html, text = mailer.render(
            "password_reset",
            {"reset_url": "https://app.aminra.vn/reset?t=abc", "user_name": "Anh Tuan", "ttl_minutes": 30},
            lang="vi",
        )
        assert subject == "[AMINRA] Yêu cầu đặt lại mật khẩu"
        assert "https://app.aminra.vn/reset?t=abc" in text
        assert "Anh Tuan" in text
        assert "30 phút" in text
        # html escaping should NOT mangle the URL inside an href
        assert 'href="https://app.aminra.vn/reset?t=abc"' in html

    def test_renders_password_reset_en(self, mailer: Mailer):
        subject, html, text = mailer.render(
            "password_reset",
            {"reset_url": "https://app.aminra.vn/reset?t=xyz"},
            lang="en",
        )
        assert subject == "[AMINRA] Password reset request"
        assert "Reset password" in html
        # default fallback when user_name missing
        assert "there" in text

    def test_unknown_lang_falls_back_to_default(self, mailer: Mailer):
        # 'ms' template doesn't exist → falls back to vi (default_lang)
        subject, _, _ = mailer.render(
            "password_reset",
            {"reset_url": "x"},
            lang="ms",
        )
        assert subject == "[AMINRA] Yêu cầu đặt lại mật khẩu"

    def test_missing_template_raises(self, mailer: Mailer):
        with pytest.raises(TemplateError, match="not found"):
            mailer.render("does_not_exist", {}, lang="vi")

    def test_template_without_subject_line_raises(self, tmp_path: Path, cfg: MailerConfig):
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "broken.vi.txt").write_text("Just a body, no subject line.\n")
        (bad_dir / "broken.vi.html").write_text("<p>body</p>")
        cfg.template_dir = bad_dir
        m = Mailer(cfg, sender=CapturingSender())
        with pytest.raises(TemplateError, match="Subject:"):
            m.render("broken", {}, lang="vi")

    def test_html_autoescape_prevents_injection(self, mailer: Mailer):
        # If a user-supplied value contains HTML, it must be escaped in HTML body
        # but appear verbatim in text body.
        _, html, text = mailer.render(
            "password_reset",
            {
                "reset_url": "https://x",
                "user_name": "<script>alert(1)</script>",
            },
            lang="vi",
        )
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html
        # Plain-text body is NOT autoescaped, by design
        assert "<script>alert(1)</script>" in text


# ── Message construction ────────────────────────────────────────────────────

class TestBuildMessage:
    def test_builds_multipart_with_from_to_subject(self, mailer: Mailer):
        msg = mailer.build_message("user@example.com", "Hello", "<b>Hi</b>", "Hi")
        assert msg["From"] == "AMINRA <noreply@aminra.vn>"
        assert msg["To"] == "user@example.com"
        assert msg["Subject"] == "Hello"
        # Both parts present
        plain = msg.get_body(preferencelist=("plain",))
        html = msg.get_body(preferencelist=("html",))
        assert plain.get_content().strip() == "Hi"
        assert "<b>Hi</b>" in html.get_content()


# ── Send via CapturingSender ────────────────────────────────────────────────

class TestSendTemplate:
    async def test_send_template_lands_in_outbox(self, mailer: Mailer, capturing: CapturingSender):
        ok = await mailer.send_template(
            to="biz@example.vn",
            template="password_reset",
            context={"reset_url": "https://app.aminra.vn/reset?t=xyz"},
            lang="vi",
        )
        assert ok is True
        assert len(capturing.outbox) == 1
        msg = capturing.outbox[0]
        assert msg["To"] == "biz@example.vn"
        assert msg["Subject"].startswith("[AMINRA]")

    async def test_send_returns_false_on_sender_error(self, cfg: MailerConfig):
        class BrokenSender:
            async def send(self, message: EmailMessage) -> None:
                raise RuntimeError("smtp down")

        m = Mailer(cfg, sender=BrokenSender())
        ok = await m.send_template(
            to="biz@example.vn",
            template="password_reset",
            context={"reset_url": "x"},
        )
        assert ok is False

    async def test_app_base_url_injected_into_context(self, cfg: MailerConfig, capturing: CapturingSender):
        # Template uses {{ from_name }} from auto-injected context
        m = Mailer(cfg, sender=capturing)
        await m.send_template(
            to="user@x.com",
            template="password_reset",
            context={"reset_url": "u"},
        )
        body = capturing.outbox[0].get_body(preferencelist=("plain",)).get_content()
        assert "AMINRA" in body  # from_name injected


# ── Sender behavior ─────────────────────────────────────────────────────────

class TestSenderImplementations:
    async def test_logging_sender_does_not_raise(self, caplog: pytest.LogCaptureFixture):
        # LoggingSender is the default when EMAIL_ENABLED=false
        m = Mailer(MailerConfig(enabled=False))
        with caplog.at_level(logging.INFO, logger="aminra.mailer"):
            ok = await m.send_template(
                to="x@y.z",
                template="password_reset",
                context={"reset_url": "https://x/"},
            )
        assert ok is True
        assert any("dry-run" in r.message for r in caplog.records)

    def test_default_sender_picked_by_enabled_flag(self):
        from services.mailer import AiosmtplibSender
        enabled_mailer = Mailer(MailerConfig(enabled=True))
        disabled_mailer = Mailer(MailerConfig(enabled=False))
        assert isinstance(enabled_mailer.sender, AiosmtplibSender)
        assert isinstance(disabled_mailer.sender, LoggingSender)


# ── Module-level singleton ──────────────────────────────────────────────────

class TestSingleton:
    def test_get_mailer_returns_same_instance(self):
        reset_mailer()
        a = get_mailer()
        b = get_mailer()
        assert a is b

    def test_reset_mailer_clears_singleton(self):
        a = get_mailer()
        reset_mailer()
        b = get_mailer()
        assert a is not b
