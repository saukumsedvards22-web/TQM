"""Send monthly reports via SMTP or SendGrid."""

from __future__ import annotations

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

log = logging.getLogger(__name__)


class ReportEmailer:
    """Send the monthly report PDF + markdown summary by email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_address: str,
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.use_tls = use_tls

    def send(
        self,
        to: list[str],
        subject: str,
        html_body: str,
        pdf_path: Path | None = None,
    ) -> None:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = self.from_address
        msg["To"] = ", ".join(to)

        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alternative)

        if pdf_path and pdf_path.exists():
            with pdf_path.open("rb") as fh:
                part = MIMEApplication(fh.read(), Name=pdf_path.name)
            part["Content-Disposition"] = f'attachment; filename="{pdf_path.name}"'
            msg.attach(part)

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.from_address, to, msg.as_string())

        log.info("Report emailed to %s", to)
