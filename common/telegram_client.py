"""
Reusable Telegram client for sending messages.

Environment variables required:
- SPORTSDATAIO_API_KEY (Telegram bot token)
- TELEGRAM_CHAT_ID

No secrets are stored in code. Values must be provided via the environment.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _get_env_variable(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if not value:
        logger.error("Missing required environment variable: %s", name)
    return value


def _get_bot_token() -> Optional[str]:
    """Return the Telegram bot token from the environment.

    The service exclusively uses ``SPORTSDATAIO_API_KEY`` for the Telegram bot
    token. Removing additional fallbacks avoids misconfigurations when only the
    canonical variable is expected to be present.
    """

    return _get_env_variable("SPORTSDATAIO_API_KEY")


def _get_chat_id() -> Optional[str]:
    """Return the Telegram chat id with graceful fallbacks."""

    return _get_env_variable("TELEGRAM_CHAT_ID") or _get_env_variable("TELEGRAM_CHATID")


def send_telegram_message(text: str, *, timeout: int = 10, retries: int = 1) -> bool:
    """
    Send a Telegram message using the Bot API.

    Args:
        text: Message text to send.
        timeout: Request timeout in seconds.
        retries: Number of retry attempts when a request fails.

    Returns:
        True when the message is delivered successfully, otherwise False.
    """
    bot_token = _get_bot_token()
    chat_id = _get_chat_id()
    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    for attempt in range(retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            if not response.ok:
                logger.error(
                    "Telegram API HTTP error (status=%s): %s",
                    response.status_code,
                    response.text,
                )
                continue

            try:
                data = response.json()
            except ValueError:
                logger.error("Telegram API returned non-JSON response: %s", response.text)
                continue

            if data.get("ok"):
                logger.info("Telegram message sent successfully")
                return True

            logger.error(
                "Telegram API error (code=%s): %s",
                data.get("error_code"),
                data.get("description"),
            )
        except requests.RequestException as exc:  # type: ignore[catching-any]
            logger.exception("Failed to send Telegram message: %s", exc)

        if attempt < retries:
            sleep_time = 2 ** attempt
            logger.info("Retrying in %s seconds (attempt %s/%s)", sleep_time, attempt + 1, retries)
            time.sleep(sleep_time)

    return False


__all__ = ["send_telegram_message"]
