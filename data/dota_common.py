"""Shared helpers for the OpenDota pipeline scripts."""
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://api.opendota.com/api"
# The data/ directory this module lives in. Derived from __file__ so the repo
# is portable (no hardcoded absolute path).
DATA_DIR = Path(__file__).resolve().parent

_HEADERS = {"User-Agent": "opencode-dota-pipeline/1.0"}
MIN_INTERVAL = 1.1  # ~55 req/min, safely under the 60/min unauthenticated limit
RETRY_BASE_DELAY = 5.0  # seconds, doubles on each retry (5, 10, 20, ...)
MAX_RETRIES = 4  # transient (5xx/network) retries inside http_get
_last_request = 0.0
_last_quota = {"minute": None, "day": None}  # remaining quota from last response


def quota_remaining() -> dict:
    """Remaining API quota observed on the last request."""
    return dict(_last_quota)


def print_quota() -> None:
    """Print remaining API quota (per minute / per day) from the last request."""
    q = quota_remaining()
    if q["minute"] is not None or q["day"] is not None:
        print(f"API quota remaining: {q['minute']}/minute, {q['day']}/day")


def wait_exit(message: str | None = None) -> None:
    """Hold the console open so a quota stop is noticed before the window closes.

    No-op (does not block) when stdin is closed, e.g. scheduled runs piping to
    /dev/null, so the script never hangs without a console."""
    if message:
        print(message)
    try:
        input("\nPress Enter to exit...")
    except (EOFError, KeyboardInterrupt):
        pass


def timestamp_fetched() -> str:
    """Current UTC time as ISO 8601 with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _sleep_until(next_time: float) -> None:
    """Sleep until the given monotonic timestamp."""
    remaining = next_time - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)


def http_get(url: str, timeout: int = 120) -> str:
    """GET a URL respecting OpenDota's rate limits. Returns response body text.

    Safeguards (anonymous tier: 60/min, 3000/day):
    - throttles to ~55 req/min via MIN_INTERVAL
    - honors the Retry-After header on 429
    - exponential backoff on repeated 429s and transient 5xx/network errors
    - waits if the per-minute quota hits zero
    - records remaining minute/day quota from response headers
    """
    global _last_request
    attempt = 0
    while True:
        # --- throttle to stay under the per-minute limit ---
        _sleep_until(_last_request + MIN_INTERVAL)
        _last_request = time.monotonic()

        try:
            resp = requests.get(url, timeout=timeout, headers=_HEADERS)
            _last_quota["minute"] = resp.headers.get("X-Rate-Limit-Remaining-Minute")
            _last_quota["day"] = resp.headers.get("X-Rate-Limit-Remaining-Day")

            if resp.status_code == 429:
                attempt += 1
                retry_after = resp.headers.get("Retry-After")
                wait = retry_after if retry_after is not None else RETRY_BASE_DELAY * (2 ** (attempt - 1))
                try:
                    wait = float(wait)
                except (TypeError, ValueError):
                    wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  rate-limited (429), waiting {wait:.0f}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.text
        except requests.HTTPError as e:
            if getattr(e.response, "status_code", None) in (500, 502, 503, 504) and attempt < MAX_RETRIES:
                attempt += 1
                wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  server error ({e.response.status_code}), retrying in {wait:.0f}s...")
                time.sleep(wait)
                continue
            raise
        except requests.RequestException as e:
            if attempt < MAX_RETRIES:
                attempt += 1
                wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  network error ({e}), retrying in {wait:.0f}s...")
                time.sleep(wait)
                continue
            raise


def load_json_array(text: str) -> list:
    """Parse JSON, guaranteeing a list is returned (single-object responses too)."""
    data = json.loads(text)
    if isinstance(data, list):
        return list(data)
    return [data]


def write_json(path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def update_array_file(path, new_records, key_field, ts) -> list:
    """Append only records whose key_field is new. Adds timestamp_fetched to new records.
    Returns the list of records that were added."""
    path = Path(path)
    existing = []
    keys = set()
    if path.exists():
        existing = load_json_array(path.read_text(encoding="utf-8"))
        for rec in existing:
            k = rec.get(key_field)
            if k is not None:
                keys.add(str(k))
    added = []
    for rec in new_records:
        if not isinstance(rec, dict):
            continue
        k = rec.get(key_field)
        if k is None:
            continue
        if str(k) not in keys:
            keys.add(str(k))
            rec["timestamp_fetched"] = ts
            existing.append(rec)
            added.append(rec)
    if added:
        write_json(path, existing)
    return added


def select_fields(obj: dict, include=None, exclude=None) -> dict:
    out = {}
    for name, value in obj.items():
        if include is not None and name not in include:
            continue
        if exclude is not None and name in exclude:
            continue
        out[name] = value
    return out


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line: machine-readable, structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(name: str = "dota", level: int = logging.INFO) -> logging.Logger:
    """Configure a structured (JSON) logger. Safe to call more than once."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger


def get_logger(name: str = "dota") -> logging.Logger:
    """Return a logger, configuring it lazily if not yet configured."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return configure_logging(name)
    return logger
