"""Bounded anonymous public GET capture. No trading SDK, credentials or writes.

Each HTTP response is retained byte-for-byte; catalogs are not quote sources.
Run on a network-enabled host, then analyze the downloaded evidence offline.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
HOSTS = {"gamma-api.polymarket.com", "clob.polymarket.com", "docs.polymarket.com"}
MAX_BYTES = 12_000_000


def allowed_url(url: str) -> bool:
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in HOSTS or p.port not in (None, 443):
        return False
    if p.username or p.password or p.fragment:
        return False
    if p.hostname == "clob.polymarket.com":
        return p.path in ("/book", "/fee-rate") or bool(re.fullmatch(r"/markets/0x[0-9a-fA-F]{64}", p.path))
    if p.hostname == "gamma-api.polymarket.com":
        return p.path == "/events" or bool(re.fullmatch(r"/events/\d+", p.path))
    return p.path.endswith(".md") or p.path.startswith("/api-spec/")


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError("redirect leaves approved anonymous read endpoints")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def json_array(value):
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        raise ValueError("expected array")
    return value


def market_tokens(m):
    if m.get("closed") is not False or m.get("acceptingOrders") is not True:
        raise ValueError("market not explicitly open/accepting")
    if m.get("enableOrderBook") is not True:
        raise ValueError("order book not enabled")
    condition = m.get("conditionId", "")
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}", condition):
        raise ValueError("unsupported condition identity")
    labels, tokens = json_array(m.get("outcomes")), json_array(m.get("clobTokenIds"))
    if [str(x).lower() for x in labels] != ["yes", "no"] or len(tokens) != 2:
        raise ValueError("unsupported outcome/position schema")
    if len(set(tokens)) != 2 or any(not isinstance(t, str) or not re.fullmatch(r"\d{1,100}", t) for t in tokens):
        raise ValueError("invalid native tokens")
    if not isinstance(m.get("description"), str) or not m["description"].strip():
        raise ValueError("missing rule text")
    return tokens


class Capture:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=False)
        (root / "raw").mkdir()
        self.root, self.lock, self.records = root, threading.Lock(), []

    def get(self, url: str, label: str):
        if not allowed_url(url):
            raise ValueError("URL not an approved public read endpoint")
        start, mono = time.time_ns(), time.monotonic_ns()
        status, headers, body, error = 0, {}, b"", None
        try:
            req = Request(url, headers={"User-Agent": "AutoPrediction-ReadOnlyResearch/0.1", "Accept": "application/json, text/markdown;q=0.9", "Cache-Control": "no-cache"}, method="GET")
            with build_opener(SafeRedirect()).open(req, timeout=12) as r:
                status, headers = r.status, dict(r.headers)
                body = r.read(MAX_BYTES + 1)
        except HTTPError as exc:
            status, headers, body = exc.code, dict(exc.headers), exc.read(MAX_BYTES + 1)
            error = f"HTTP_{exc.code}"
        except (OSError, URLError, ValueError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        received, duration = time.time_ns(), time.monotonic_ns() - mono
        if len(body) > MAX_BYTES:
            error = "BODY_LIMIT_EXCEEDED"
        digest = sha256(body).hexdigest()
        rec = {"label": label, "url": url, "method": "GET", "status": status,
               "started_ns": start, "received_ns": received, "duration_ns": duration,
               "body_sha256": digest, "bytes": len(body), "error": error,
               "headers": {k.lower(): v for k, v in headers.items() if k.lower() in ("date", "content-type", "cache-control", "age")}}
        with self.lock:
            (self.root / "raw" / f"{digest}.bin").write_bytes(body)
            self.records.append(rec)
            with (self.root / "requests.jsonl").open("a") as f:
                f.write(json.dumps(rec, sort_keys=True) + "\n")
        parsed = None
        if error is None and status == 200:
            try:
                parsed = json.loads(body, parse_float=str)
            except (ValueError, UnicodeDecodeError):
                pass
        return rec, parsed

    def save(self, name, data):
        (self.root / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cycles", type=int, default=12)
    parser.add_argument("--interval", type=float, default=5)
    args = parser.parse_args()
    if not (2 <= args.cycles <= 20 and 1 <= args.interval <= 30):
        parser.error("capture must be bounded: 2..20 cycles, 1..30 second interval")
    cap = Capture(args.output)
    config = {"schema": "s2.public-capture.v1", "started_ns": time.time_ns(),
              "cycles": args.cycles, "interval_seconds": args.interval, "max_tokens": 96,
              "catalog_scope": "first 300 liquidity-ranked + 100 recent open events; no claim of universe completeness",
              "max_group_members": 6, "max_groups": 8, "max_binary_controls": 16,
              "authority": "READ_ONLY_RESEARCH", "value_moving_actions": False}
    cap.save("config.json", config)
    docs = ["trading/fees", "concepts/negative-risk", "concepts/resolution", "market-data/prices-order-books", "market-data/market-details"]
    for path in docs:
        cap.get(f"https://docs.polymarket.com/{path}.md", "docs:" + path)
    events, catalogs = {}, []
    for order, offset in (("liquidity", 0), ("liquidity", 100), ("liquidity", 200), ("id", 0)):
        url = GAMMA + "/events?" + urlencode({"limit": 100, "offset": offset, "active": "true", "closed": "false", "order": order, "ascending": "false"})
        rec, page = cap.get(url, f"catalog:{order}:{offset}")
        catalogs.append(rec["body_sha256"])
        if isinstance(page, list):
            for e in page:
                if isinstance(e, dict) and str(e.get("id", "")).isdigit():
                    events.setdefault(str(e["id"]), e)
    selected, rejected, token_set, group_count = [], [], set(), 0
    for e in events.values():
        members = e.get("markets", [])
        if not isinstance(members, list) or not 2 <= len(members) <= 6:
            rejected.append({"event_id": e["id"], "reason": "group_size_out_of_scope"}); continue
        if e.get("negRisk") is not True and e.get("enableNegRisk") is not True:
            rejected.append({"event_id": e["id"], "reason": "not_negative_risk_group"}); continue
        if e.get("negRiskAugmented") is True:
            rejected.append({"event_id": e["id"], "reason": "augmented_group_excluded"}); continue
        try:
            tokens = [t for m in members for t in market_tokens(m)]
        except (TypeError, ValueError) as exc:
            rejected.append({"event_id": e["id"], "reason": str(exc)}); continue
        if len(set(tokens)) != len(tokens):
            rejected.append({"event_id": e["id"], "reason": "duplicate_native_token"}); continue
        if group_count >= 8 or len(token_set | set(tokens)) > 64:
            rejected.append({"event_id": e["id"], "reason": "fixed_capture_budget"}); continue
        selected.append({"kind": "NEG_RISK_ASSUMED_EXHAUSTIVE", "event": e,
                         "markets": members, "semantic_admission": "COMPLETENESS_AND_SETTLEMENT_UNVERIFIED"})
        token_set.update(tokens); group_count += 1
    binaries = 0
    for e in events.values():
        for m in e.get("markets", []):
            try: tokens = market_tokens(m)
            except (TypeError, ValueError): continue
            if set(tokens) & token_set or binaries >= 16 or len(token_set | set(tokens)) > 96:
                continue
            selected.append({"kind": "BINARY_COMPLEMENT", "event": e, "markets": [m],
                             "semantic_admission": "SAME_CONDITION_COMPLEMENT_ASSUMPTION"})
            token_set.update(tokens); binaries += 1
    cap.save("selection.json", {"catalogs": catalogs, "catalog_events": len(events),
        "families": selected, "excluded": rejected, "tokens": sorted(token_set)})
    print(json.dumps({"events": len(events), "families": len(selected), "groups": group_count,
                      "binary_controls": binaries, "tokens": len(token_set)}), flush=True)
    event_ids = sorted({str(f["event"]["id"]) for f in selected})
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda eid: cap.get(GAMMA + "/events/" + eid, "rules-before:" + eid), event_ids))
        for cycle in range(args.cycles):
            start = time.monotonic()
            list(pool.map(lambda token: cap.get(CLOB + "/book?" + urlencode({"token_id": token}), f"book:{cycle}:{token}"), sorted(token_set)))
            print(f"cycle {cycle}: {len(token_set)} public book reads recorded", flush=True)
            if cycle + 1 < args.cycles:
                time.sleep(max(0, args.interval - (time.monotonic() - start)))
        list(pool.map(lambda eid: cap.get(GAMMA + "/events/" + eid, "rules-after:" + eid), event_ids))
    cap.save("summary.json", {"finished_ns": time.time_ns(), "requests": len(cap.records),
        "successful_responses": sum(r["status"] == 200 and r["error"] is None for r in cap.records),
        "errors": sum(r["error"] is not None for r in cap.records), "family_count": len(selected),
        "authority": "PUBLIC_OBSERVATION_ONLY", "profitability_verified": False})


if __name__ == "__main__":
    main()
