"""SMSFlow CLI — a one-message educational SMS API client.

Use only with an authorized SMS provider and recipients who have opted in.
Credentials are read from environment variables and are never hard-coded.
"""

from __future__ import annotations

import base64
import os
import re
import sys
import time
from typing import Final

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()
DEFAULT_API_ROOT: Final = "https://api.twilio.com/2010-04-01/Accounts"
PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
MAX_MESSAGE_LENGTH = 1_600


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def banner() -> None:
    console.print(
        Panel.fit(
            Text("SMSFLOW CLI", style="bold cyan"),
            subtitle="Authorized SMS API testing tool",
            border_style="blue",
        )
    )
    console.print("[bold magenta]Developer:[/bold magenta] [white]darkvibez[/white]")
    console.print("[dim]One message • E.164 validation • provider-controlled delivery[/dim]\n")


def prompt_required(label: str) -> str:
    while True:
        value = console.input(f"[cyan bold]{label}[/cyan bold]").strip()
        if value:
            return value
        console.print("[bold red]✗[/bold red] This field cannot be empty.")


def prompt_phone(label: str) -> str:
    while True:
        number = prompt_required(label)
        if PHONE_PATTERN.fullmatch(number):
            return number
        console.print(
            "[bold red]✗[/bold red] Use international E.164 format, "
            "for example [white]+14155552671[/white]."
        )


def prompt_message() -> str:
    while True:
        message = prompt_required("Message          : ")
        if len(message) <= MAX_MESSAGE_LENGTH:
            return message
        console.print(
            f"[bold red]✗[/bold red] Message is too long. "
            f"Maximum: {MAX_MESSAGE_LENGTH} characters."
        )


def mask_phone(number: str) -> str:
    return f"{number[:3]}{'*' * max(4, len(number) - 7)}{number[-4:]}"


def compact(text: str, limit: int = 400) -> str:
    text = text.strip() or "(empty response)"
    return f"{text[:limit]}…" if len(text) > limit else text


def send_sms(to_number: str, message: str) -> bool:
    account_sid = required_env("SMSFLOW_ACCOUNT_SID")
    auth_token = required_env("SMSFLOW_AUTH_TOKEN")
    from_number = required_env("SMSFLOW_FROM_NUMBER")
    timeout = float(os.getenv("SMSFLOW_TIMEOUT", "15"))
    api_url = os.getenv("SMSFLOW_API_URL", "").strip()
    url = api_url or f"{DEFAULT_API_ROOT}/{account_sid}/Messages.json"

    if not PHONE_PATTERN.fullmatch(from_number):
        raise RuntimeError("SMSFLOW_FROM_NUMBER must use E.164 format.")

    token = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
        "User-Agent": "SMSFlow-CLI/1.0 (educational; authorized-use-only)",
    }
    payload = {"To": to_number, "From": from_number, "Body": message}

    console.print("[yellow]Submitting SMS request...[/yellow]")
    started = time.perf_counter()
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=timeout)
    except requests.exceptions.Timeout:
        console.print(
            Panel.fit(
                "The SMS provider took too long to respond.\n"
                "Check the provider or try again later.",
                title="TIMEOUT",
                border_style="red",
            )
        )
        return False
    except requests.exceptions.RequestException as exc:
        console.print(Panel.fit(str(exc), title="REQUEST ERROR", border_style="red"))
        return False

    elapsed = time.perf_counter() - started
    success = 200 <= response.status_code < 300
    if success:
        result = "[bold green]✓ SMS request accepted by the provider.[/bold green]"
        next_step = "[yellow]Next step:[/yellow] Check provider delivery status for final delivery."
    elif response.status_code in {401, 403}:
        result = "[bold red]✗ Provider authentication was rejected.[/bold red]"
        next_step = "[yellow]Next step:[/yellow] Check the account credentials and sender number."
    elif response.status_code == 429:
        result = "[bold red]✗ Provider rate limit or quota reached.[/bold red]"
        next_step = "[yellow]Next step:[/yellow] Wait before trying again and check provider limits."
    else:
        result = "[bold red]✗ The SMS provider rejected the request.[/bold red]"
        next_step = "[yellow]Next step:[/yellow] Check the provider response and message settings."

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="cyan bold", no_wrap=True)
    table.add_column(style="white")
    table.add_row("HTTP status", str(response.status_code))
    table.add_row("Duration", f"{elapsed:.2f}s")
    table.add_row("Provider reply", compact(response.text))
    table.add_row("Result", result)
    table.add_row("Guidance", next_step)
    console.print(Panel(table, title="SMS STATUS PANEL", border_style="green" if success else "red"))
    return success


def main() -> int:
    banner()
    console.print(
        Panel.fit(
            "Send only to recipients who have explicitly opted in.\n"
            "Never use this tool for spam, harassment, or unsolicited messages.",
            title="Responsible use",
            border_style="magenta",
        )
    )
    try:
        to_number = prompt_phone("Destination Number: ")
        message = prompt_message()
        from_number = os.getenv("SMSFLOW_FROM_NUMBER", "not configured")

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="cyan bold", no_wrap=True)
        table.add_column(style="white")
        table.add_row("Destination", mask_phone(to_number))
        table.add_row("Sender", from_number)
        table.add_row("Message", f"{len(message)} characters")
        console.print(Panel(table, title="SMS REQUEST PREVIEW", border_style="blue"))

        sent = send_sms(to_number, message)
        console.print(
            Panel.fit(
                "[bold green]SMSFlow CLI finished successfully[/bold green]"
                if sent
                else "[bold yellow]SMSFlow CLI finished with a failed request[/bold yellow]",
                border_style="green" if sent else "yellow",
            )
        )
        return 0 if sent else 1
    except RuntimeError as exc:
        console.print(Panel.fit(str(exc), title="CONFIGURATION ERROR", border_style="red"))
        return 2
    except KeyboardInterrupt:
        console.print("\n[bold red]Cancelled by user.[/bold red]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
