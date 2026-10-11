"""Exact conditional price consistency and sampled execution research.

NO certificate authority. States are assumptions, not LLM-proven venue rules.
Network-free; all amounts in Fraction or integer units. Uses S1 unchanged.
"""
from __future__ import annotations
from dataclasses import asdict
from fractions import Fraction as F
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "s1"))
from maximin import parse_model, solve_maximin, top_of_book_equal_size_baseline, _evaluate

SCALE = 1_000_000
RULE_FIELDS = ("id", "conditionId", "question", "description", "resolutionSource",
               "endDate", "outcomes", "clobTokenIds", "feesEnabled", "feeSchedule",
               "negRisk", "negRiskMarketID", "closed", "acceptingOrders", "enableOrderBook")


def rational(value) -> F:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("exact decimal text or integer required")
    if isinstance(value, str) and not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise ValueError("finite decimal required")
    return F(value)


def units(value) -> int:
    x = rational(value) * SCALE
    if x.denominator != 1 or x < 0:
        raise ValueError("value outside fixed-point precision")
    return x.numerator


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def rule_identity(event, market_ids=None):
    members = event.get("markets")
    if not isinstance(members, list):
        raise ValueError("event has no member definitions")
    ids = [str(m.get("id")) for m in members]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate member id")
    wanted = set(ids) if market_ids is None else set(market_ids)
    if not wanted.issubset(ids):
        raise ValueError("missing event member")
    selected = sorted((m for m in members if str(m["id"]) in wanted), key=lambda m: str(m["id"]))
    return canonical_hash({"event_id": str(event["id"]),
        "group_flags": {k: event.get(k) for k in ("negRisk", "enableNegRisk", "negRiskAugmented")},
        "members": [{k: m.get(k) for k in RULE_FIELDS} for m in selected]})


def parse_book(body, token, condition):
    if not isinstance(body, dict) or body.get("asset_id") != token or body.get("market") != condition:
        raise ValueError("book token/condition mismatch")
    if not isinstance(body.get("hash"), str) or not body["hash"]:
        raise ValueError("book hash absent")
    ts = body.get("timestamp")
    if not isinstance(ts, str) or not ts.isdigit():
        raise ValueError("book timestamp unavailable")
    minimum, tick = rational(body['min_order_size']), rational(body['tick_size'])
    if minimum<=0 or not 0<tick<=1: raise ValueError('minimum size or tick unavailable')
    result = {'min_order_size':minimum,'tick_size':tick}
    for side in ("asks", "bids"):
        if not isinstance(body.get(side), list):
            raise ValueError("book ladder missing")
        seen, ladder = set(), []
        for level in body[side]:
            price, size = rational(level["price"]), rational(level["size"])
            if not 0 <= price <= 1 or size <= 0 or price in seen or (price/tick).denominator != 1:
                raise ValueError("invalid/duplicate price level")
            seen.add(price)
            ladder.append((price, size))
        result[side] = tuple(sorted(ladder, reverse=side == "bids"))
    if not result["asks"]:
        raise ValueError("empty ask book; never substitute a last price")
    result["timestamp_ns"] = int(ts) * 1_000_000
    result["hash"] = body["hash"]
    return result


def alignment(records, books, *, max_window_ns=5_000_000_000, max_age_ns=120_000_000_000):
    if not records or len(records) != len(books):
        raise ValueError("missing quote observations")
    for r, book in zip(records, books):
        if r["status"] != 200 or r["error"] is not None or r["method"] != "GET":
            raise ValueError("unsuccessful quote observation")
        if r["received_ns"] < r["started_ns"] or not 0 <= r["duration_ns"] <= max_window_ns:
            raise ValueError("quote request duration/clock invalid")
        age = r["received_ns"] - book["timestamp_ns"]
        if not -5_000_000_000 <= age <= max_age_ns:
            raise ValueError("server book timestamp outside freshness window")
    span = max(r["received_ns"] for r in records) - min(r["started_ns"] for r in records)
    if span > max_window_ns:
        raise ValueError("family acquisition skew exceeds fixed window")
    return span


def verify_witness(payoffs, asks, weights):
    """Exact dual witness for BUY-ONLY min-state profit <= 0, not all strategies."""
    if not weights or any(not isinstance(w, F) or w < 0 for w in weights) or sum(weights) != 1:
        return False
    if not payoffs or len(payoffs) != len(asks) or any(not isinstance(a, F) or a < 0 for a in asks):
        return False
    return all(len(row) == len(weights) and all(isinstance(v, F) for v in row)
        and sum(w * h for w, h in zip(weights, row)) <= ask
        for row, ask in zip(payoffs, asks))


def partition_witness(yes_asks, no_asks, *, binary=False):
    """Construct rational prices consistent with binary complement / one-hot states."""
    if not yes_asks or len(yes_asks) != len(no_asks) or any(not isinstance(a,F) or a<0 for a in (*yes_asks,*no_asks)):
        raise ValueError("missing paired asks")
    lo = [max(F(0), 1 - a) for a in no_asks]
    hi = [min(F(1), a) for a in yes_asks]
    if any(l > u for l, u in zip(lo, hi)):
        return None
    if binary:
        if len(lo) != 1:
            raise ValueError("binary witness requires one condition")
        return (lo[0], 1 - lo[0])
    if sum(lo) > 1 or sum(hi) < 1:
        return None
    w, remaining = lo[:], 1 - sum(lo)
    for i in range(len(w)):
        delta = min(hi[i] - lo[i], remaining)
        w[i] += delta
        remaining -= delta
    if remaining != 0:
        raise AssertionError("witness construction failed")
    return tuple(w)


def fee_posture(markets):
    # Deliberately do not translate Gamma rates into a match-level certificate.
    rates, zero = [], True
    for m in markets:
        schedule = m.get("feeSchedule")
        rate = schedule.get("rate") if isinstance(schedule, dict) else None
        if rate is not None:
            rate = rational(rate)
            if rate < 0 or rate > 1:
                raise ValueError("invalid fee rate")
        if m.get("feesEnabled") is False and rate not in (None, F(0)):
            raise ValueError("contradictory fee metadata")
        if m.get("feesEnabled") is not False:
            zero = False
        rates.append(None if rate is None else str(rate))
    return {"status": "EXPLICIT_ZERO_METADATA_ONLY" if zero else "MATCH_FEE_BOUND_UNQUALIFIED",
            "rates": rates, "production_certified": False}


def model_from_books(evidence_id, states, tokens, payoffs, books, budget_units=1000*SCALE):
    assets = []
    for token, payoff, book in zip(tokens, payoffs, books):
        asks, remaining = [], 10_000
        for price, quantity in book["asks"]:
            depth = min(quantity.numerator // quantity.denominator, remaining)
            if depth <= 0: continue
            asks.append({"price": int(price*SCALE) if (price*SCALE).denominator == 1 else None,
                         "depth": depth, "fee_upper": 0})
            if asks[-1]["price"] is None:
                raise ValueError("price precision cannot enter S1")
            remaining -= depth
            if len(asks) == 8 or remaining == 0: break
        if not asks:
            raise ValueError("no whole-share depth for S1 integer domain")
        assets.append({"id": token, "venue": "polymarket", "payoffs": {s: int(p*SCALE) for s,p in zip(states,payoff)}, "asks": asks})
    return parse_model({"coverage": "ASSUMED_STATES_ONLY", "evidence_id": evidence_id,
        "scale": SCALE, "budget": budget_units, "venue_budgets": {"polymarket": budget_units},
        "states": states, "assets": assets})


def walk_limit(ladder, quantity, limit):
    """Whole-share FOK against sampled visible prices, zero fees diagnostic only."""
    if type(quantity) is not int or quantity<=0 or not isinstance(limit,F) or not 0<=limit<=1:
        raise ValueError('invalid quantity or limit')
    if any(not isinstance(p,F) or not isinstance(q,F) or not 0<=p<=1 or q<=0 for p,q in ladder):
        raise ValueError('invalid replay ladder')
    if list(ladder)!=sorted(ladder) or len({p for p,_ in ladder})!=len(ladder):
        raise ValueError('unordered or duplicate replay levels')
    remaining, cost = F(quantity), F(0)
    for price, size in ladder:
        if price > limit: break
        filled = min(size, remaining)
        cost += filled * price
        remaining -= filled
        if not remaining: return cost
    return None


def partial_fill_floor(payoffs, quantities, debits):
    """Adversarial independent FOK-leg failures, not a fitted fill probability."""
    if len(payoffs) != len(quantities) or len(debits) != len(quantities) or len(quantities) > 12:
        raise ValueError("partial-fill problem dimensions invalid")
    if any(type(q) is not int or q<=0 for q in quantities) or any(not isinstance(c,F) or c<0 for c in debits):
        raise ValueError('invalid stress amount')
    if not payoffs or not payoffs[0] or any(len(p) != len(payoffs[0]) for p in payoffs):
        raise ValueError("empty/inconsistent payoff states")
    worst, worst_mask = F(0), tuple(False for _ in quantities)
    for mask in product((False, True), repeat=len(quantities)):
        floor = min(sum(q*p[k]-c for enabled,q,p,c in zip(mask,quantities,payoffs,debits) if enabled)
                    for k in range(len(payoffs[0])))
        if floor < worst: worst, worst_mask = floor, mask
    return {"worst_floor": str(worst), "filled_mask": list(worst_mask),
            "assumption": "independent leg acceptance; no forced unwind; zero fees"}


class SampledLedger:
    """Single account, no funding reuse until actual redemption evidence exists.

    No settlement is invented. Cash debit and locked inventory are not profit.
    Reused identical book bytes cannot replenish the same sampled liquidity.
    """
    def __init__(self, cash=F(1000)):
        if not isinstance(cash,F) or cash<0: raise ValueError('invalid cash')
        self.cash, self.inventory, self.seen_families, self.used_books = cash, {}, set(), set()

    def apply(self, family, proposal, books_by_token):
        if family in self.seen_families: return {"status": "FAMILY_ALREADY_ATTEMPTED"}
        if F(proposal.capital_required, SCALE) > self.cash: return {"status": "INSUFFICIENT_CASH"}
        if not proposal.buys: return {"status": "NO_TRADE"}
        if any((b.asset_id, books_by_token[b.asset_id]["hash"]) in self.used_books for b in proposal.buys):
            return {"status": "REUSED_DEPTH"}
        if len({b.asset_id for b in proposal.buys})!=len(proposal.buys) or proposal.capital_required!=sum(b.conservative_debit for b in proposal.buys):
            raise ValueError('invalid proposal debit or duplicate asset')
        filled, staged, cost = [], [], F(0)
        for b in proposal.buys:
            book = books_by_token[b.asset_id]
            debit = walk_limit(book["asks"], b.quantity, F(b.limit, SCALE))
            if debit is None: continue
            if debit>F(b.conservative_debit,SCALE): raise ValueError('fill exceeds order reserve')
            cost += debit; filled.append(b.asset_id); staged.append((b.asset_id,b.quantity,book['hash']))
        if cost > self.cash: raise AssertionError("sampled debit exceeds reserved cash")
        self.seen_families.add(family)
        for token,quantity,book_hash in staged:
            self.inventory[token]=self.inventory.get(token,0)+quantity
            self.used_books.add((token,book_hash))
        self.cash -= cost
        return {"status": "ALL_FILLED" if len(filled)==len(proposal.buys) else "PARTIAL" if filled else "NO_FILL",
                "filled": filled, "gross_cash_debit": str(cost), "remaining_cash": str(self.cash),
                "realized_profit": None, "model": "SAMPLED_ZERO_FEE_FOK_LEGS_NOT_ACTUAL_FILLS"}


def equal_size_frontier(model):
    """Exactly the S1 equal-size/top-book objective, O(2^assets), no share loop.

    For a fixed subset all costs and state payouts are linear in common size.
    If unit floor is positive, the largest funded integer size is optimal.
    This is an algebraic speedup of the baseline, NOT a new alpha strategy.
    """
    if len(model.assets) > 12:
        raise ValueError("equal-size baseline limited to 12 assets")
    best = _evaluate(model, tuple(None for _ in model.assets), "EQUAL_SIZE_ANALYTIC")
    for mask in range(1, 1 << len(model.assets)):
        ids = [i for i in range(len(model.assets)) if mask & (1 << i)]
        unit_cost = sum(model.assets[i].levels[0].ask + model.assets[i].levels[0].fee_upper for i in ids)
        unit_floor = min(sum(model.assets[i].payoff[k] for i in ids) for k in range(len(model.state_ids))) - unit_cost
        if unit_floor <= 0: continue
        quantity = min(model.assets[i].levels[0].depth for i in ids)
        if unit_cost: quantity = min(quantity, model.budget // unit_cost)
        for venue, budget in model.venue_budgets.items():
            cost = sum(model.assets[i].levels[0].ask + model.assets[i].levels[0].fee_upper for i in ids if model.assets[i].venue == venue)
            if cost: quantity = min(quantity, budget // cost)
        if quantity <= 0: continue
        candidate = _evaluate(model, tuple((0, quantity) if i in ids else None for i in range(len(model.assets))), "EQUAL_SIZE_ANALYTIC")
        if candidate.lower_floor > best.lower_floor: best = candidate
    return best


def equal_size_depth_frontier(model):
    """Strong all-subsets equal-share baseline over ALL S1 price tiers.

    Within an interval of cumulative-depth breakpoints, cost per share and
    the minimum payout per share are constant. Check its largest funded
    integer size. This separates depth access from unequal-quantity benefit.
    """
    if len(model.assets) > 12: raise ValueError("depth baseline limited to 12 assets")
    tiers = []
    for asset in model.assets:
        cap, fee, row = 0, 0, []
        for l in asset.levels:
            cap += l.depth; fee = max(fee, l.fee_upper)
            row.append((l.ask+fee, cap))
        tiers.append(row)
    best = _evaluate(model, tuple(None for _ in model.assets), "EQUAL_SIZE_ALL_DEPTH")
    for mask in range(1, 1 << len(model.assets)):
        ids = [i for i in range(len(model.assets)) if mask & (1 << i)]
        max_quantity = min(tiers[i][-1][1] for i in ids)
        ends = sorted({cap for i in ids for _,cap in tiers[i] if cap <= max_quantity} | {max_quantity})
        lo = 1
        for hi in ends:
            rank = {i:next(r for r,(_,cap) in enumerate(tiers[i]) if cap>=lo) for i in ids}
            unit_cost = sum(tiers[i][rank[i]][0] for i in ids)
            unit_floor = min(sum(model.assets[i].payoff[k] for i in ids) for k in range(len(model.state_ids))) - unit_cost
            if unit_floor > 0:
                q = min(hi, model.budget//unit_cost) if unit_cost else hi
                for venue,budget in model.venue_budgets.items():
                    c = sum(tiers[i][rank[i]][0] for i in ids if model.assets[i].venue==venue)
                    if c: q = min(q,budget//c)
                if q>=lo:
                    candidate = _evaluate(model, tuple((rank[i],q) if i in rank else None for i in range(len(model.assets))), "EQUAL_SIZE_ALL_DEPTH")
                    if candidate.lower_floor>best.lower_floor: best=candidate
            lo=hi+1
    return best


def nominal_fees_for_buys(proposal, tokens, markets, books, payoffs):
    """Unrounded curve-fee scenario on sampled depth, not a debit guarantee."""
    cost, fees = F(0), F(0)
    payout = [F(0)] * len(payoffs[0])
    for buy in proposal.buys:
        idx=tokens.index(buy.asset_id); market=markets[idx//2]
        schedule=market.get('feeSchedule')
        if market.get('feesEnabled') is False: rate=F(0)
        elif isinstance(schedule,dict) and schedule.get('exponent')==1 and schedule.get('takerOnly') is True:
            rate=rational(schedule['rate'])
        else: return None
        remaining=F(buy.quantity)
        for price,size in books[idx]['asks']:
            if price>F(buy.limit,SCALE): break
            q=min(remaining,size); cost+=q*price; fees+=q*rate*price*(1-price); remaining-=q
            if not remaining: break
        if remaining: raise ValueError('proposal exceeds nominal replay depth')
        for k,p in enumerate(payoffs[idx]): payout[k]+=buy.quantity*p
    return {'gross_cost':str(cost), 'unrounded_curve_fee':str(fees),
            'nominal_net_floor':str(min(payout)-cost-fees),
            'qualification':'NOMINAL_FORMULA_SCENARIO_NOT_ACTUAL_DEBIT_CERTIFICATE'}
