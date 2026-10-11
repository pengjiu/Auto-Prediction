"""Research-only, finite-state, limit-cost maximin MILP baseline.

The Python/HiGHS optimizer is NOT a certificate authority. Every candidate is
recomputed with Python integers, but its payoff states, fee bounds and market
identity are assumptions supplied by the caller. No venue/credential/network IO.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from itertools import product
from typing import Any


@dataclass(frozen=True)
class Level:
    ask: int
    depth: int
    fee_upper: int  # bound per share for ALL possible fills at or below chosen cap


@dataclass(frozen=True)
class Asset:
    asset_id: str
    venue: str
    payoff: tuple[int, ...]  # payment per whole share, in price-scale integer ticks
    levels: tuple[Level, ...]


@dataclass(frozen=True)
class Model:
    evidence_id: str
    state_ids: tuple[str, ...]
    scale: int
    budget: int
    venue_budgets: dict[str, int]
    assets: tuple[Asset, ...]
    # This is NOT evidence that real venue terms forbid all omitted states.
    coverage: str = "ASSUMED_STATES_ONLY"


@dataclass(frozen=True)
class Buy:
    asset_id: str
    quantity: int
    limit: int
    fee_upper: int
    conservative_debit: int
    snapshot_cost_estimate: int


@dataclass(frozen=True)
class Proposal:
    model_hash: str
    buys: tuple[Buy, ...]
    worst_state: str
    lower_floor: int
    snapshot_floor: int
    capital_required: int
    numeric_solver_status: str
    authority: str = "RESEARCH_PROPOSAL_ONLY"


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{field} must be integer >= {minimum}")
    return value


def parse_model(data: dict) -> Model:
    if not isinstance(data, dict):
        raise ValueError("model must be an object")
    if data.get("coverage") != "ASSUMED_STATES_ONLY":
        raise ValueError("model is research-only; explicitly declare assumed state coverage")
    evidence_id = data.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id.strip():
        raise ValueError("nonempty evidence id required")
    states = data.get("states")
    if (not isinstance(states, list) or not (1 <= len(states) <= 128) or
            not all(isinstance(s, str) and s for s in states) or len(set(states)) != len(states)):
        raise ValueError("states must be a nonempty unique bounded list")
    scale = _integer(data.get("scale"), "scale", minimum=1)
    if scale > 1_000_000:
        raise ValueError("scale exceeds numeric solver qualification")
    budget = _integer(data.get("budget"), "budget")
    raw_budgets = data.get("venue_budgets")
    if not isinstance(raw_budgets, dict):
        raise ValueError("explicit per-venue budgets required")
    venue_budgets = {str(k): _integer(v, "venue budget") for k, v in raw_budgets.items()}
    raw_assets = data.get("assets")
    if not isinstance(raw_assets, list) or not 1 <= len(raw_assets) <= 16:
        raise ValueError("must have 1..16 assets")
    assets = []
    seen = set()
    total_upper = 0
    for record in raw_assets:
        if not isinstance(record, dict):
            raise ValueError("asset must be an object")
        ident, venue = record.get("id"), record.get("venue")
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError("asset ids must be unique and nonempty (shared depth cannot be duplicated)")
        seen.add(ident)
        if not isinstance(venue, str) or venue not in venue_budgets:
            raise ValueError("each asset venue must have explicit capital budget")
        pay = record.get("payoffs")
        if not isinstance(pay, dict) or set(pay) != set(states):
            raise ValueError("payoff vector must cover precisely the declared states")
        payoff = tuple(_integer(pay[s], "payoff") for s in states)
        if any(v > scale for v in payoff):
            raise ValueError("payment exceeds one unit collateral")
        raw_levels = record.get("asks")
        if not isinstance(raw_levels, list) or not 1 <= len(raw_levels) <= 8:
            raise ValueError("asset requires 1..8 nonempty ask levels")
        levels = []
        prev = -1
        for l in raw_levels:
            if not isinstance(l, dict):
                raise ValueError("ask level must be an object")
            ask = _integer(l.get("price"), "ask price")
            depth = _integer(l.get("depth"), "ask depth", minimum=1)
            fee = _integer(l.get("fee_upper"), "fee upper bound")
            if ask > scale or ask <= prev:
                raise ValueError("ask levels must be strictly increasing and <= 1")
            prev = ask
            levels.append(Level(ask, depth, fee))
            total_upper += depth * (scale + fee)
        assets.append(Asset(ident, venue, payoff, tuple(levels)))
    # SciPy/HiGHS works in floats. Refuse unsafe-sized models before solving,
    # even though final PnL is independently evaluated as arbitrary-size int.
    if max(total_upper, budget, *venue_budgets.values()) >= (1 << 52):
        raise ValueError("problem too large for conservative floating LP/MILP formulation")
    return Model(evidence_id, tuple(states), scale, budget, venue_budgets, tuple(assets))


def _asset_candidates(asset: Asset) -> tuple[tuple[int, int, int], ...]:
    """(limit, cumulative executable size, per-share worst fee)."""
    cap, fee = 0, 0
    result = []
    for level in asset.levels:
        cap += level.depth
        fee = max(fee, level.fee_upper)
        result.append((level.ask, cap, fee))
    return tuple(result)


def _walk_snapshot_cost(asset: Asset, quantity: int) -> int:
    remaining = quantity
    cost = 0
    for level in asset.levels:
        used = min(remaining, level.depth)
        cost += used * (level.ask + level.fee_upper)
        remaining -= used
        if remaining == 0:
            break
    if remaining:
        raise ValueError("quantity exceeds visible book depth")
    return cost


def _model_hash(model: Model) -> str:
    body = {
        "evidence_id": model.evidence_id,
        "states": model.state_ids,
        "scale": model.scale,
        "budget": model.budget,
        "venue_budgets": model.venue_budgets,
        "assets": [
            {"id": a.asset_id, "venue": a.venue, "payoff": a.payoff,
             "asks": [(l.ask, l.depth, l.fee_upper) for l in a.levels]}
            for a in model.assets
        ],
    }
    return "sha256:" + sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _evaluate(model: Model, choice: tuple[tuple[int, int] | None, ...], status: str) -> Proposal:
    if len(choice) != len(model.assets):
        raise ValueError("candidate asset count mismatch")
    buys = []
    total_debit = 0
    total_snapshot = 0
    venue_debit = {v: 0 for v in model.venue_budgets}
    payouts = [0] * len(model.state_ids)
    for asset, selected in zip(model.assets, choice):
        if selected is None:
            continue
        r, quantity = selected
        if not isinstance(r, int) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("integer limit selection and positive quantity required")
        candidates = _asset_candidates(asset)
        if r < 0 or r >= len(candidates):
            raise ValueError("invalid limit tier")
        limit, capacity, fee_upper = candidates[r]
        if quantity > capacity:
            raise ValueError("order exceeds snapshot capacity")
        debit = quantity * (limit + fee_upper)
        observed = _walk_snapshot_cost(asset, quantity)
        if observed > debit:
            raise ValueError("snapshot cost exceeds proposed conservative limit")
        buys.append(Buy(asset.asset_id, quantity, limit, fee_upper, debit, observed))
        total_debit += debit
        total_snapshot += observed
        venue_debit[asset.venue] += debit
        for i, pay in enumerate(asset.payoff):
            payouts[i] += quantity * pay
    if total_debit > model.budget or any(venue_debit[v] > model.venue_budgets[v] for v in venue_debit):
        raise ValueError("candidate violates available capital")
    worst_idx = min(range(len(payouts)), key=payouts.__getitem__)
    lower_floor = payouts[worst_idx] - total_debit
    snapshot_floor = min(payouts) - total_snapshot
    return Proposal(_model_hash(model), tuple(buys), model.state_ids[worst_idx], lower_floor,
                    snapshot_floor, total_debit, status)


def solve_maximin(model: Model, *, time_limit: float = 5.0) -> Proposal:
    """HiGHS MILP optimizes conservative full-size-at-limit cost, not VWAP.

    Decision: one limit price per token, integer quantity, venue funding and
    every supplied payout state; excludes short-selling, conversions, atomic
    execution and real fee qualification. Always validates an integer proposal.
    """
    if not 0.01 <= time_limit <= 60:
        raise ValueError("time limit outside bounded research range")
    try:
        import numpy as np
        from scipy.optimize import milp, Bounds, LinearConstraint
    except ImportError as exc:
        raise RuntimeError("SciPy is an OPTIONAL research dependency, not a production dependency") from exc

    tiers = [(i, r, price, cap, fee) for i, a in enumerate(model.assets)
             for r, (price, cap, fee) in enumerate(_asset_candidates(a))]
    n = len(tiers)
    # q[0:n], tier z[0:n], guaranteed floor t. All q and z are integer.
    size = 2 * n + 1
    idx_floor = 2 * n
    c = np.zeros(size, dtype=float)
    c[idx_floor] = -1.0
    lower = np.zeros(size, dtype=float)
    upper = np.full(size, np.inf, dtype=float)
    integral = np.zeros(size, dtype=int)
    integral[:2 * n] = 1
    for k, (_, _, _, cap, _) in enumerate(tiers):
        upper[k] = cap
        upper[n + k] = 1
    upper[idx_floor] = sum(max(a.payoff) * sum(l.depth for l in a.levels) for a in model.assets)
    rows = []
    limits = []
    # q_i,r <= max depth at limit r * z_i,r
    for k, (_, _, _, cap, _) in enumerate(tiers):
        row = np.zeros(size)
        row[k] = 1
        row[n + k] = -cap
        rows.append(row)
        limits.append(0)
    # One price cap for each asset, or no order at all.
    for i in range(len(model.assets)):
        row = np.zeros(size)
        for k, (ai, *_rest) in enumerate(tiers):
            if ai == i:
                row[n + k] = 1
        rows.append(row)
        limits.append(1)
    costs = [price + fee for _, _, price, _, fee in tiers]
    row = np.zeros(size)
    row[:n] = costs
    rows.append(row)
    limits.append(model.budget)
    for venue, max_cost in model.venue_budgets.items():
        row = np.zeros(size)
        for k, (ai, *_rest) in enumerate(tiers):
            if model.assets[ai].venue == venue:
                row[k] = costs[k]
        rows.append(row)
        limits.append(max_cost)
    # t <= sum_i payout_i(state)*quantity_i - conservative total cost.
    for state in range(len(model.state_ids)):
        row = np.zeros(size)
        row[idx_floor] = 1
        for k, (ai, *_rest) in enumerate(tiers):
            row[k] = costs[k] - model.assets[ai].payoff[state]
        rows.append(row)
        limits.append(0)
    result = milp(c=c, integrality=integral, bounds=Bounds(lower, upper),
                  constraints=LinearConstraint(np.stack(rows), -np.inf, limits),
                  options={"time_limit": time_limit, "mip_rel_gap": 0})
    if result.x is None or result.status != 0 or not result.success:
        raise RuntimeError(f"numeric optimizer did not prove optimality under its tolerances: {result.message}")
    choices: list[tuple[int, int] | None] = [None] * len(model.assets)
    for k, (i, r, *_rest) in enumerate(tiers):
        raw_q, raw_z = float(result.x[k]), float(result.x[n+k])
        q, z = round(raw_q), round(raw_z)
        if abs(raw_q - q) > 1e-5 or abs(raw_z - z) > 1e-5:
            raise RuntimeError("numeric solution not integral within tolerance")
        if q == 0:
            continue
        if z != 1 or choices[i] is not None:
            raise RuntimeError("invalid or duplicate executable tier")
        choices[i] = (r, q)
    proposal = _evaluate(model, tuple(choices), "HIGHS_NUMERIC_OPTIMAL_EXACT_RECOMPUTED")
    # Numerical t never signs the result. Recomputed integers are authoritative
    # only for the DECLARED finite payment states, not true contract semantics.
    if proposal.lower_floor < 0:
        raise RuntimeError("MILP candidate is worse than admissible no-trade control")
    return proposal


def exact_bruteforce(model: Model, *, max_candidates: int = 100_000) -> Proposal:
    """Independent exhaustive reference for tiny models. Never use at scale."""
    options = []
    total = 1
    for a in model.assets:
        all_options = [None]
        for r, (_, capacity, _) in enumerate(_asset_candidates(a)):
            all_options.extend((r, q) for q in range(1, capacity + 1))
        options.append(all_options)
        total *= len(all_options)
    if total > max_candidates:
        raise ValueError(f"exhaustive gold reference needs {total} combinations")
    # Independent reference arithmetic: do not call the proposal evaluator
    # while searching. This catches both MILP formulation mistakes and errors in
    # the optimized candidate's quantity/cost/state cash-flow evaluation.
    best_choice = tuple(None for _ in model.assets)
    best_floor = 0  # deliberately admissible no-trade benchmark
    for choice in product(*options):
        total_cost = 0
        venue_cost = {v: 0 for v in model.venue_budgets}
        state_income = [0] * len(model.state_ids)
        for asset, selection in zip(model.assets, choice):
            if selection is None:
                continue
            rank, quantity = selection
            prefix = asset.levels[:rank + 1]
            if quantity > sum(level.depth for level in prefix):
                raise AssertionError("exhaustive reference generated impossible depth")
            debit = quantity * (asset.levels[rank].ask + max(level.fee_upper for level in prefix))
            total_cost += debit
            venue_cost[asset.venue] += debit
            for state_index, payout in enumerate(asset.payoff):
                state_income[state_index] += quantity * payout
        if total_cost > model.budget or any(
            venue_cost[v] > limit for v, limit in model.venue_budgets.items()
        ):
            continue
        floor = min(state_income) - total_cost
        if floor > best_floor:
            best_floor, best_choice = floor, choice
    final = _evaluate(model, best_choice, "EXACT_ENUMERATION")
    if final.lower_floor != best_floor:
        raise AssertionError("independent oracle and candidate re-evaluation disagree")
    return final


def top_of_book_equal_size_baseline(model: Model, *, max_assets: int = 12) -> Proposal:
    """Strong deterministic benchmark: all subsets, equal sizes, best ask only."""
    if len(model.assets) > max_assets:
        raise ValueError("baseline enumeration limited to 12 assets")
    max_trials = (1 << len(model.assets)) * max(a.levels[0].depth for a in model.assets)
    if max_trials > 100_000:
        raise ValueError("equal-size research baseline exceeds bounded search budget")
    best = _evaluate(model, tuple(None for _ in model.assets), "EQUAL_SIZE_TOP_BOOK")
    for mask in range(1, 1 << len(model.assets)):
        eligible = [i for i in range(len(model.assets)) if mask & (1 << i)]
        cap = min(model.assets[i].levels[0].depth for i in eligible)
        for q in range(1, cap + 1):
            choice = tuple((0, q) if i in eligible else None for i in range(len(model.assets)))
            try:
                p = _evaluate(model, choice, "EQUAL_SIZE_TOP_BOOK")
            except ValueError:
                continue
            if p.lower_floor > best.lower_floor:
                best = p
    return best


def proposal_json(p: Proposal) -> dict:
    return {
        "schema_version": "pmh.research-limit-maximin.v1",
        "model_hash": p.model_hash,
        "authority": p.authority,
        "numeric_solver_status": p.numeric_solver_status,
        "limiting_state": p.worst_state,
        "net_floor_ticks_under_assumed_states": p.lower_floor,
        "snapshot_floor_ticks_estimate": p.snapshot_floor,
        "conditional_maximum_debit_ticks": p.capital_required,
        "buys": [vars(b) for b in p.buys],
        "execution_atomicity_proven": False,
        "real_world_settlement_completeness_proven": False,
        "live_execution_enabled": False,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: python maximin.py path/to/reviewed-research-input.json")
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        model = parse_model(json.load(handle))
    print(json.dumps(proposal_json(solve_maximin(model)), indent=2, sort_keys=True))
