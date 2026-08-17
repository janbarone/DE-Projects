"""Unit tests for data/dota_common.py (throttle, retry, quota, file helpers)."""
import json

import dota_common as dc
import pytest
import requests


class FakeResponse:
    def __init__(self, status_code, headers=None, text=""):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} error")
            err.response = self
            raise err


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    monkeypatch.setattr(dc, "_sleep_until", lambda t: None)
    monkeypatch.setattr(dc.time, "sleep", lambda s: None)
    dc._last_request = 0.0
    dc._last_quota = {"minute": None, "day": None}


@pytest.fixture(autouse=True)
def _isolate_drained(monkeypatch, tmp_path):
    monkeypatch.setattr(dc, "DRAINED_FILE", tmp_path / "drained_leagues.json")
    monkeypatch.setattr(dc, "SKIPPED_FILE", tmp_path / "skipped_matches.json")


def test_timestamp_fetched_is_iso8601_utc():
    ts = dc.timestamp_fetched()
    assert ts.endswith("Z")
    assert "T" in ts


def test_load_json_array_wraps_dict():
    assert dc.load_json_array('{"a": 1}') == [{"a": 1}]
    assert dc.load_json_array('[{"a": 1}]') == [{"a": 1}]


def test_select_fields_include_exclude():
    obj = {"a": 1, "b": 2, "c": 3}
    assert dc.select_fields(obj, include=["a", "b"]) == {"a": 1, "b": 2}
    assert dc.select_fields(obj, exclude=["b"]) == {"a": 1, "c": 3}


def test_update_array_file_dedups_by_key(tmp_path):
    path = tmp_path / "leagues.json"
    dc.write_json(path, [{"leagueid": 1, "name": "A"}])
    added = dc.update_array_file(
        path, [{"leagueid": 1, "name": "A"}, {"leagueid": 2, "name": "B"}],
        "leagueid", "2026-01-01T00:00:00Z",
    )
    assert [r["leagueid"] for r in added] == [2]
    assert added[0]["timestamp_fetched"] == "2026-01-01T00:00:00Z"
    data = dc.load_json_array(path.read_text(encoding="utf-8"))
    assert len(data) == 2


def test_http_get_success_records_quota(monkeypatch):
    def fake_get(url, timeout, headers):
        return FakeResponse(200, {"X-Rate-Limit-Remaining-Minute": "55", "X-Rate-Limit-Remaining-Day": "2999"}, '{"ok": 1}')

    monkeypatch.setattr(dc.requests, "get", fake_get)
    assert dc.http_get("http://x") == '{"ok": 1}'
    assert dc.quota_remaining() == {"minute": "55", "day": "2999"}


def test_http_get_429_retries_with_retry_after(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, timeout, headers):
        calls["n"] += 1
        if calls["n"] < 3:
            return FakeResponse(429, {"Retry-After": "0"})
        return FakeResponse(200, {}, '{"ok": 1}')

    monkeypatch.setattr(dc.requests, "get", fake_get)
    assert dc.http_get("http://x") == '{"ok": 1}'
    assert calls["n"] == 3


def test_http_get_429_raises_after_cap(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, timeout, headers):
        calls["n"] += 1
        return FakeResponse(429, {"Retry-After": "0"})

    monkeypatch.setattr(dc.requests, "get", fake_get)
    with pytest.raises(dc.RateLimitedError, match="rate limited"):
        dc.http_get("http://x")
    assert calls["n"] == dc.MAX_429 + 1


def test_drained_registry():
    assert dc.load_drained() == set()
    dc.mark_drained(12735)
    dc.mark_drained(12906)
    assert dc.load_drained() == {12735, 12906}
    assert dc.is_drained(12735)
    assert not dc.is_drained(9999)
    dc.mark_drained(12735)  # idempotent
    assert dc.load_drained() == {12735, 12906}


def test_skipped_matches_registry():
    assert dc.load_skipped() == set()
    dc.mark_match_skipped(7928919925)
    assert dc.is_match_skipped(7928919925)
    assert not dc.is_match_skipped(123)
    dc.mark_match_skipped(7928919925)  # idempotent
    assert dc.load_skipped() == {7928919925}


def test_have_match_treats_skipped_as_present(monkeypatch, tmp_path):
    monkeypatch.setattr(dc, "DATA_DIR", tmp_path)
    mid = 555
    assert not dc.have_match(mid)
    dc.mark_match_skipped(mid)
    assert dc.have_match(mid)


def test_discover_league_ok(monkeypatch):
    def fake_get(url, timeout, headers):
        return FakeResponse(200, {}, '[100, 200, 300]')

    monkeypatch.setattr(dc.requests, "get", fake_get)
    mids, status, detail = dc.discover_league(5)
    assert status == "ok"
    assert mids == [100, 200, 300]


def test_discover_league_empty(monkeypatch):
    def fake_get(url, timeout, headers):
        return FakeResponse(200, {}, '[]')

    monkeypatch.setattr(dc.requests, "get", fake_get)
    mids, status, detail = dc.discover_league(5)
    assert status == "empty"
    assert mids == []


def test_discover_league_unavailable_after_retries(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, timeout, headers):
        calls["n"] += 1
        err = requests.HTTPError("404 Client Error: Not Found")
        err.response = FakeResponse(404)
        raise err

    monkeypatch.setattr(dc.requests, "get", fake_get)
    mids, status, detail = dc.discover_league(5)
    assert status == "unavailable"
    assert mids is None
    assert calls["n"] == dc.DISCOVERY_RETRIES


def test_discover_league_rate_limited(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, timeout, headers):
        calls["n"] += 1
        return FakeResponse(429, {"Retry-After": "0"})

    monkeypatch.setattr(dc.requests, "get", fake_get)
    mids, status, detail = dc.discover_league(5)
    assert status == "rate_limited"
    assert calls["n"] == dc.MAX_429 + 1


def test_http_get_5xx_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, timeout, headers):
        calls["n"] += 1
        if calls["n"] < 3:
            return FakeResponse(503)
        return FakeResponse(200, {}, '[]')

    monkeypatch.setattr(dc.requests, "get", fake_get)
    assert dc.http_get("http://x") == '[]'
    assert calls["n"] == 3


def test_http_get_network_error_retries(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, timeout, headers):
        calls["n"] += 1
        if calls["n"] < 2:
            raise requests.RequestException("boom")
        return FakeResponse(200, {}, '[]')

    monkeypatch.setattr(dc.requests, "get", fake_get)
    assert dc.http_get("http://x") == '[]'
    assert calls["n"] == 2


def test_json_log_formatter_outputs_json():
    import logging

    logger = logging.getLogger("test.json")
    handler = logging.StreamHandler()
    handler.setFormatter(dc.JsonLogFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # just ensure the formatter doesn't raise and emits valid JSON shape
    fmt = dc.JsonLogFormatter()
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    out = fmt.format(record)
    assert json.loads(out)["message"] == "hello world"
