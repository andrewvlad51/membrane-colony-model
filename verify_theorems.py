#!/usr/bin/env python3
"""Bounded checks of the theorem statements in "Membranes for Machine Workers".

These are not proofs. Each theorem is proved in the paper. This program tests each
statement on every small instance, or on many random ones, so that a wrong statement
is caught. Every test is also run against a deliberately wrong variant of the statement
and must then report failures. Seeds are fixed, so the output is reproducible.

Usage:  python3 verify_theorems.py        (about one minute)
"""

import itertools
import random


def closure(n, adj, start, avoid):
    """Vertices reachable from `start` on paths whose vertices all lie outside `avoid` (bitmasks)."""
    seen = start & ~avoid
    frontier = seen
    while frontier:
        nxt = 0
        v = 0
        f = frontier
        while f:
            if f & 1:
                nxt |= adj[v]
            f >>= 1
            v += 1
        nxt &= ~avoid & ~seen
        seen |= nxt
        frontier = nxt
    return seen


def graphs(n):
    pairs = [(a, b) for a in range(n) for b in range(n)]
    for bits in range(1 << len(pairs)):
        adj = [0] * n
        for i, (a, b) in enumerate(pairs):
            if bits >> i & 1:
                adj[a] |= 1 << b
        yield adj


def random_graph(rng, n, p):
    return [sum(1 << b for b in range(n) if rng.random() < p) for _ in range(n)]


# ---- Theorem 2: spawn admission --------------------------------------------------------

def admission_case(n, adj, X, Y, c, I, O, wrong=False):
    """Returns (violated in the extended graph, predicted by the local test)."""
    F = closure(n, adj, X, Y)
    old = bool(F >> c & 1)
    B = 0
    for v in range(n):
        if not Y >> v & 1 and closure(n, adj, 1 << v, Y) >> c & 1:
            B |= 1 << v
    local = bool(I & F) and bool(O & B & ~Y)
    if wrong:                                              # wrong variant: forgets the mediators
        local = bool(I & closure(n, adj, X, 0)) and bool(O & B)
    w = n
    adj2 = [adj[v] | ((1 << w) if I >> v & 1 else 0) for v in range(n)] + [O]
    new = bool(closure(n + 1, adj2, X, Y) >> c & 1)
    return new, old or local


def theorem2():
    n, cases, bad, bad_wrong = 3, 0, 0, 0
    for adj in graphs(n):
        for X in range(1, 1 << n):
            for Y in range(1 << n):
                for c in range(n):
                    for I in range(1 << n):
                        for O in range(1 << n):
                            cases += 1
                            a, b = admission_case(n, adj, X, Y, c, I, O)
                            bad += a != b
                            if cases % 97 == 0:
                                a, b = admission_case(n, adj, X, Y, c, I, O, wrong=True)
                                bad_wrong += a != b
    rng = random.Random(11)
    rnd = rbad = 0
    for _ in range(200000):
        n = rng.randint(4, 8)
        adj = random_graph(rng, n, rng.choice([0.1, 0.2, 0.35]))
        X, Y, I, O = (rng.getrandbits(n) & rng.getrandbits(n) for _ in range(4))
        a, b = admission_case(n, adj, X or 1, Y, rng.randrange(n), I, O)
        rnd += 1
        rbad += a != b
    return cases, bad, rnd, rbad, bad_wrong


# ---- Corollary: a worker wired like an existing one ------------------------------------

def corollary_template():
    rng = random.Random(12)
    cases = bad = bad_wrong = 0
    while cases < 100000:
        n = rng.randint(3, 7)
        adj = random_graph(rng, n, 0.3)
        X, Y, c, m = rng.getrandbits(n) or 1, rng.getrandbits(n) & rng.getrandbits(n), rng.randrange(n), rng.randrange(n)
        if Y >> m & 1 or closure(n, adj, X, Y) >> c & 1:
            continue
        preds = sum(1 << a for a in range(n) if adj[a] >> m & 1)
        I, O = preds & rng.getrandbits(n), adj[m] & rng.getrandbits(n)
        cases += 1
        new, _ = admission_case(n, adj, X, Y, c, I, O)
        bad += new                                          # must never be violated
        new, _ = admission_case(n, adj, X, Y, c, rng.getrandbits(n), rng.getrandbits(n))
        bad_wrong += new                                    # an arbitrary worker sometimes is
    return cases, bad, bad_wrong


# ---- Theorem 1, value form: noninterference through mediators ---------------------------

def noninterference():
    rng = random.Random(13)
    cases = bad = bad_wrong = 0
    for _ in range(50000):
        n, k = rng.randint(3, 6), 3
        adj = random_graph(rng, n, 0.35)
        X, Y = rng.getrandbits(n) or 1, rng.getrandbits(n) & rng.getrandbits(n)
        high = closure(n, adj, X, Y)
        edges = [(u, v) for u in range(n) for v in range(n) if adj[u] >> v & 1]
        if not edges:
            continue
        s1 = [rng.randrange(k) for _ in range(n)]
        s2 = [s1[v] if not high >> v & 1 else rng.randrange(k) for v in range(n)]
        t1, t2 = list(s1), list(s2)                         # second pair: mediator writes not fixed
        for _ in range(12):
            u, v = rng.choice(edges)
            table = [[rng.randrange(k) for _ in range(k)] for _ in range(k)]
            const = rng.randrange(k)
            g = (lambda p, q: const) if Y >> v & 1 else (lambda p, q: table[p][q])
            s1[v], s2[v] = g(s1[u], s1[v]), g(s2[u], s2[v])
            t1[v], t2[v] = table[t1[u]][t1[v]], table[t2[u]][t2[v]]
        cases += 1
        low = [v for v in range(n) if not high >> v & 1]
        bad += any(s1[v] != s2[v] for v in low)
        bad_wrong += any(t1[v] != t2[v] for v in low)
    return cases, bad, bad_wrong


# ---- Theorem 3: control objects ----------------------------------------------------------

def control_objects():
    """Every trace of length up to 7 over two parameters. Effects need the object present."""
    events = [(kind, p) for kind in ("write", "revoke", "effect", "forge") for p in (0, 1)]
    cases = bad = bad_wrong = 0
    for length in range(1, 8):
        for trace in itertools.product(events, repeat=length):
            for guarded in (True, False):
                present, ok, valid = set(), True, True
                last_write = {}
                for i, (kind, p) in enumerate(trace):
                    if kind == "write":
                        present.add(p); last_write[p] = i
                    elif kind == "revoke":
                        present.discard(p); last_write.pop(p, None)
                    elif kind == "forge":
                        if guarded:
                            valid = False; break            # untrusted compartments have no rule on the node
                        present.add(p)
                    else:
                        if p not in present:
                            valid = False; break            # the effect is not enabled
                        ok &= p in last_write
                if not valid:
                    continue
                if guarded:
                    cases += 1; bad += not ok
                else:
                    bad_wrong += not ok
    return cases, bad, bad_wrong


# ---- Theorem 4: delimiter integrity --------------------------------------------------------

def delimiter_integrity():
    rng = random.Random(14)
    R, alphabet = "#", "ab#\\"
    escape = lambda u: u.replace("\\", "\\\\").replace(R, "\\h")
    cases = bad = bad_wrong = 0
    for _ in range(100000):
        fields = [(rng.random() < 0.4, "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 6)))) for _ in range(rng.randint(1, 5))]
        for enc, wrong in ((escape, False), (lambda u: u, True)):
            out = []
            for trusted, text in fields:
                out += [(ch, trusted) for ch in (text if trusted else enc(text))]
            forged = any(ch == R and not trusted for ch, trusted in out)
            if wrong:
                bad_wrong += forged
            else:
                cases += 1; bad += forged
    return cases, bad, bad_wrong


# ---- Theorem 6: composition ------------------------------------------------------------------

def composition():
    rng = random.Random(15)
    cases = bad = bad_wrong = 0
    for _ in range(100000):
        n = rng.randint(4, 9)
        side = [rng.choice("12I") for _ in range(n)]          # caller only, callee only, interface
        V1 = sum(1 << v for v in range(n) if side[v] in "1I")
        V2 = sum(1 << v for v in range(n) if side[v] in "2I")
        I = V1 & V2
        adj, leak = [0] * n, [0] * n
        for a in range(n):
            for b in range(n):
                if rng.random() < 0.3:
                    if (V1 >> a & 1 and V1 >> b & 1) or (V2 >> a & 1 and V2 >> b & 1):
                        adj[a] |= 1 << b
                    leak[a] |= 1 << b                           # wrong variant: edges ignore the sides
        cases += 1
        for a in range(n):
            if side[a] == "1":
                bad += bool(closure(n, adj, 1 << a, I) & ~V1)
                bad_wrong += bool(closure(n, leak, 1 << a, I) & ~V1)
    return cases, bad, bad_wrong


def main():
    c, bad, rnd, rbad, w = theorem2()
    print("Theorem 2 (spawn admission): all %d instances on 3 vertices, %d failures; %d random instances on 4 to 8 vertices, %d failures" % (c, bad, rnd, rbad))
    print("   wrong variant (mediators forgotten): %d failures" % w)
    c, bad, w = corollary_template()
    print("Corollary (worker wired like an existing one): %d random instances, %d violated" % (c, bad))
    print("   arbitrary worker instead: %d violated" % w)
    c, bad, w = noninterference()
    print("Theorem 1, value form (two runs agree outside the forbidden region): %d random instances, %d failures" % (c, bad))
    print("   wrong variant (mediator content not fixed): %d failures" % w)
    c, bad, w = control_objects()
    print("Theorem 3 (control objects): all %d valid traces up to length 7, %d effects without a trusted cause" % (c, bad))
    print("   wrong variant (an untrusted writer exists): %d traces with such an effect" % w)
    c, bad, w = delimiter_integrity()
    print("Theorem 4 (delimiter integrity): %d random renderings, %d forged markers" % (c, bad))
    print("   wrong variant (no encoding): %d renderings with a forged marker" % w)
    c, bad, w = composition()
    print("Theorem 6 (composition): %d random compositions, %d paths that skip the interface" % (c, bad))
    print("   wrong variant (caller holds levels inside the callee): %d such paths" % w)


if __name__ == "__main__":
    main()
