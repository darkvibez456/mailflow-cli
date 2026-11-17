"""MailFlow CLI — a small educational email-form client.

Use only with an email API and recipients you are authorized to contact.
"""

from __future__ import annotations

import os
import re
import sys
import time
from typing import Final

import pyfiglet
import requests
from colorama import init
from requests import Response
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_API_URL: Final = "https://api.proxynova.com/v1/send_email"
API_URL = os.getenv("MAILFLOW_API_URL", DEFAULT_API_URL).strip()
REQUEST_TIMEOUT = float(os.getenv("MAILFLOW_TIMEOUT", "15"))
MAX_MESSAGE_LENGTH = 10_000

init(autoreset=True)
console = Console()

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


def banner() -> None:
    """Print the application banner."""
    ascii_banner = pyfiglet.figlet_format("MAILFLOW CLI", font="slant")
    console.print(
        Panel.fit(
            Text(ascii_banner, style="bold yellow"),
            subtitle="Authorized email testing tool",
            border_style="green",
        )
    )


def loading(text: str, dots: int = 3, delay: float = 0.12) -> None:
    """Display a small progress indicator without blocking for too long."""
    console.print(f"[yellow]{text}[/yellow]", end="")
    for _ in range(dots):
        time.sleep(delay)
        console.print("[yellow].[/yellow]", end="")
    console.print()


def prompt_required(label: str, *, secret: bool = False) -> str:
    """Read a non-empty value from the user."""
    while True:
        value = console.input(f"[cyan bold]{label}[/cyan bold]").strip()
        if value:
            return value
        console.print("[red]This field cannot be empty.[/red]")


def prompt_email() -> str:
    """Read and validate the destination email address."""
    while True:
        address = prompt_required("Destination Email : ")
        if EMAIL_PATTERN.fullmatch(address):
            return address
        console.print("[red]Please enter a valid email address.[/red]")


def prompt_message() -> str:
    """Read a message and protect the request from excessively large input."""
    while True:
        message = prompt_required("Message           : ")
        if len(message) <= MAX_MESSAGE_LENGTH:
            return message
        console.print(
            f"[red]Message is too long. Maximum: {MAX_MESSAGE_LENGTH} characters.[/red]"
        )


def compact_response(response: Response, limit: int = 500) -> str:
    """Return a readable, bounded server response for the status panel."""
    body = response.text.strip() or "(empty response)"
    if len(body) > limit:
        body = f"{body[:limit]}…"
    return body


def send_mail(to: str, sender_name: str, subject: str, message: str) -> bool:
    """Send one authorized email request and return whether it succeeded."""
    payload = {
        "to": to,
        "from": sender_name,
        "subject": subject,
        "message": message,
    }
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "MailFlow-CLI/2.0 (educational; authorized-use-only)",
    }

    loading("Submitting mail request")
    try:
        # A timeout is essential: a network call should never hang forever.
        response = requests.post(
            API_URL,
            data=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        console.print(
            Panel.fit(
                "The mail service took too long to respond. "
                "Please check the API or try again later.",
                title="TIMEOUT",
                border_style="red",
            )
        )
        return False
    except requests.exceptions.RequestException as exc:
        console.print(
            Panel.fit(
                f"[bold red]Network error:[/bold red] {exc}",
                title="REQUEST ERROR",
                border_style="red",
            )
        )
        return False

    success = 200 <= response.status_code < 300
    status = (
        f"[cyan]HTTP status:[/cyan] [white]{response.status_code}[/white]\n"
        f"[cyan]Server reply:[/cyan] [white]{compact_response(response)}[/white]\n\n"
        + (
            "[bold green]Request accepted by the server.[/bold green]"
            if success
            else "[bold red]The server rejected the request.[/bold red]"
        )
    )
    console.print(
        Panel.fit(
            status,
            title="STATUS PANEL",
            border_style="green" if success else "red",
        )
    )
    return success


def main() -> int:
    """Run the interactive application."""
    banner()
    console.print(
        Panel.fit(
            "Use this program only for recipients who have consented to receive\n"
            "your message and only with an API you are authorized to use.",
            title="Responsible use",
            border_style="magenta",
        )
    )

    try:
        to = prompt_email()
        sender_name = prompt_required("Sender Name      : ")
        subject = prompt_required("Subject          : ")
        message = prompt_message()

        console.print()
        send_mail(to, sender_name, subject, message)
        console.print(
            Panel.fit(
                "[bold yellow]MailFlow CLI • educational build[/bold yellow]",
                border_style="blue",
            )
        )
        return 0
    except KeyboardInterrupt:
        console.print("\n[bold red]Cancelled by user.[/bold red]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
