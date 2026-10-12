"""Exact finite histories of recurring events in bounded integer-time intervals.

Only interval arithmetic: this module does not interpret contractual prose.
The output is conditional research, never venue settlement or execution proof.
"""
from __future__ import annotations
from itertools import product, combinations
from fractions import Fraction as F
import re


def checked(intervals):
    if not isinstance(intervals,(list,tuple)) or not 1 <= len(intervals) <= 6:
        raise ValueError('1..6 intervals required')
    for x in intervals:
        if not isinstance(x,(list,tuple)) or len(x)!=2 or any(type(t) is not int for t in x) or x[0]>x[1]:
            raise ValueError('nonempty exact integer intervals required')
    return intervals


def atoms(intervals):
    """Every membership pattern in inclusive discrete time; arbitrary size integers."""
    checked(intervals)
    points=sorted({t for lo,hi in intervals for t in (lo,hi+1)})
    return [(t, sum(1<<i for i,(lo,hi) in enumerate(intervals) if lo<=t<=hi)) for t in points]


def histories(intervals):
    """OR-closure is exact for zero or more qualifying occurrences, not just one.

    Any history produces a union of atom signatures. Conversely place one event
    at the representative time of every selected signature. At most 2**n results.
    """
    states={0:()}
    for t,mask in atoms(intervals):
        for current,witness in list(states.items()):
            states.setdefault(current|mask,witness+(t,) if mask else witness)
    return dict(sorted(states.items()))


def robust_histories(members):
    """Union of unresolved start-inclusive/exclusive and final-minute readings.

    Independence of boundary choices is conservative. No scalar first-event
    model and no assumption that an early creation gap had no qualifying event.
    """
    if not isinstance(members,list) or not 1<=len(members)<=6:raise ValueError('member bound')
    choices=[]
    for m in members:
        values=[m[k] for k in ('startNS','endNS','endMinuteNS')]
        if any(type(v)is not str or not re.fullmatch(r'-?\d{1,50}',v) for v in values):raise ValueError('exact bounded integer timestamp text required')
        lo,hi,minute=map(int,values)
        if minute<hi or lo>=hi:raise ValueError('bad source interval')
        choices.append([(lo+a,end) for a in (0,1) for end in (hi,minute)])
    states={}
    for iv in product(*choices):
        for mask,w in histories(iv).items():states.setdefault(mask,{'timesNS':[str(t) for t in w],'intervalsNS':[[str(a),str(b)] for a,b in iv]})
    return dict(sorted(states.items()))


def relation_report(members,states):
    n=len(members)
    implications=[(a,b) for a in range(n) for b in range(n) if a!=b and all(not(s>>a&1) or s>>b&1 for s in states)]
    pairwise=[s for s in range(1<<n) if all(not(s>>a&1) or s>>b&1 for a,b in implications)]
    higher=[]
    for a in range(n):
        for bs in combinations([b for b in range(n) if b!=a],2):
            if all(not(s>>a&1) or any(s>>b&1 for b in bs) for s in states) and all((a,b) not in implications for b in bs):
                higher.append({'antecedent':a,'cover':list(bs)})
    naive_errors=[]
    for a,b in combinations(range(n),2):
        if int(members[a]['endNS'])>int(members[b]['endNS']):a,b=b,a
        bad=next((s for s in states if s>>a&1 and not(s>>b&1)),None)
        if bad is not None:naive_errors.append({'earlier':a,'later':b,'counterworld_mask':bad,'witness':states[bad]})
    return {'pairwise_implications':implications,'pairwise_masks':pairwise,'higher_order_covers':higher,'naive_deadline_counterexamples':naive_errors}


def payout_rows(masks,n):
    if not masks or len(set(masks))!=len(masks) or any(type(s)is not int or not 0<=s<1<<n for s in masks):raise ValueError('bad masks')
    return [tuple(F(int(bool(s>>i&1)==yes)) for s in masks) for i in range(n) for yes in (True,False)]
