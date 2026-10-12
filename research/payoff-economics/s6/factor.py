"""Finite composition arithmetic; semantic assumptions live in the source review."""
from itertools import product,combinations
from fractions import Fraction as F

def truth_states():
    return [(s=='D',h=='D',s=='D' and h=='D',s=='D' and h=='R')
            for s,h in product(('D','R','OTHER'),repeat=2)]

def pairwise_relaxation(states):
    if not states or any(len(s)!=4 or any(type(x)is not bool for x in s) for s in states):
        raise ValueError('four boolean outcomes required')
    # Stronger than implication-only: retain every allowed two-variable projection.
    pairs={ij:{(s[ij[0]],s[ij[1]]) for s in states} for ij in combinations(range(4),2)}
    return [s for s in product((False,True),repeat=4) if all((s[i],s[j]) in allowed for (i,j),allowed in pairs.items())]

def rows(states):
    if not states or any(len(s)!=4 for s in states):raise ValueError('four-state-vector required')
    if any(not isinstance(x,(bool,F)) or not 0<=x<=1 for s in states for x in s):raise ValueError('exact payoff required')
    return [tuple(F(s[i]) if yes else 1-F(s[i]) for s in states) for i in range(4) for yes in (True,False)]
