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
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_API_URL: Final = "https://api.proxynova.com/v1/send_email"
API_URL = os.getenv("MAILFLOW_API_URL", DEFAULT_API_URL).strip()
REQUEST_TIMEOUT = float(os.getenv("MAILFLOW_TIMEOUT", "15"))
MAX_MESSAGE_LENGTH = 10_000
MAX_SUBJECT_LENGTH = 200

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
    console.print("[bold magenta]Developer:[/bold magenta] [white]darkvibez[/white]")
    console.print("[dim]One request • clear validation • timeout-safe delivery[/dim]\n")


def loading(text: str, dots: int = 3, delay: float = 0.12) -> None:
    """Display a small progress indicator without blocking for too long."""
    console.print(f"[yellow]{text}[/yellow]", end="")
    for _ in range(dots):
        time.sleep(delay)
        console.print("[yellow].[/yellow]", end="")
    console.print()


def prompt_required(label: str) -> str:
    """Read a non-empty value from the user."""
    while True:
        value = console.input(f"[cyan bold]{label}[/cyan bold]").strip()
        if value:
            return value
        console.print("[bold red]✗[/bold red] This field cannot be empty.")


def prompt_email() -> str:
    """Read and validate the destination email address."""
    while True:
        address = prompt_required("Destination Email : ")
        if EMAIL_PATTERN.fullmatch(address):
            return address
        console.print("[bold red]✗[/bold red] Please enter a valid email address.")


def prompt_subject() -> str:
    """Read a subject and keep it within a practical API limit."""
    while True:
        subject = prompt_required("Subject          : ")
        if len(subject) <= MAX_SUBJECT_LENGTH:
            return subject
        console.print(
            f"[bold red]✗[/bold red] Subject is too long. "
            f"Maximum: {MAX_SUBJECT_LENGTH} characters."
        )


def prompt_message() -> str:
    """Read a message and protect the request from excessively large input."""
    while True:
        message = prompt_required("Message           : ")
        if len(message) <= MAX_MESSAGE_LENGTH:
            return message
        console.print(
            f"[bold red]✗[/bold red] Message is too long. "
            f"Maximum: {MAX_MESSAGE_LENGTH} characters."
        )


def mask_email(address: str) -> str:
    """Hide most of the local part when echoing a destination on screen."""
    local, domain = address.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(2, len(local) - len(visible))}@{domain}"


def request_preview(to: str, sender_name: str, subject: str, message: str) -> None:
    """Show a compact summary before making the network request."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="cyan bold", no_wrap=True)
    table.add_column(style="white")
    table.add_row("Destination", mask_email(to))
    table.add_row("Sender", sender_name)
    table.add_row("Subject", subject)
    table.add_row("Message", f"{len(message)} characters")
    table.add_row("Endpoint", API_URL)
    console.print(Panel(table, title="REQUEST PREVIEW", border_style="blue"))


def compact_response(response: Response, limit: int = 500) -> str:
    """Return a readable, bounded server response for the status panel."""
    body = response.text.strip() or "(empty response)"
    if len(body) > limit:
        body = f"{body[:limit]}…"
    return body


def response_guidance(response: Response) -> str:
    """Turn common provider failures into an actionable next step."""
    body = response.text.lower()
    if response.status_code == 429 or "limit" in body or "rate" in body:
        return "[yellow]Next step:[/yellow] The provider limit may be reached. Wait and try again later."
    if response.status_code in {401, 403}:
        return "[yellow]Next step:[/yellow] Check API authentication and sender permissions."
    if response.status_code == 400:
        return "[yellow]Next step:[/yellow] Check the endpoint, required fields, and provider payload format."
    if response.status_code >= 500:
        return "[yellow]Next step:[/yellow] The provider returned a server error. Try again later."
    return "[yellow]Next step:[/yellow] Review the provider response and configuration."


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
    started = time.perf_counter()
    try:
        response = requests.post(
            API_URL,
            data=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        console.print(
            Panel.fit(
                "The mail service took too long to respond.\n"
                "Check the API or try again later.",
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

    elapsed = time.perf_counter() - started
    success = 200 <= response.status_code < 300
    result_label = (
        "[bold green]✓ Request accepted by the server.[/bold green]"
        if success
        else "[bold red]✗ The server rejected the request.[/bold red]"
    )
    status = (
        f"[cyan]HTTP status :[/cyan] [white]{response.status_code}[/white]\n"
        f"[cyan]Duration    :[/cyan] [white]{elapsed:.2f}s[/white]\n"
        f"[cyan]Server reply:[/cyan] [white]{compact_response(response)}[/white]\n\n"
        f"{result_label}\n"
        f"{response_guidance(response)}"
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
        subject = prompt_subject()
        message = prompt_message()

        console.print()
        request_preview(to, sender_name, subject, message)
        console.print()
        sent = send_mail(to, sender_name, subject, message)
        console.print(
            Panel.fit(
                "[bold green]MailFlow CLI finished successfully[/bold green]"
                if sent
                else "[bold yellow]MailFlow CLI finished with a failed request[/bold yellow]",
                border_style="green" if sent else "yellow",
            )
        )
        return 0 if sent else 1
    except KeyboardInterrupt:
        console.print("\n[bold red]Cancelled by user.[/bold red]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
