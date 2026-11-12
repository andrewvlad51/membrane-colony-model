#!/usr/bin/env python3
"""Run semantics of a compartment system as a taint-carrying colony.

Companion artefact for the paper "Independence by Access". The static checker
(independence_check.py) decides properties on the influence graph. This program executes
the colony itself: agents and nodes carry the mark of a forbidden source, and the mark moves
only by the rules of the colony (read, write, deterministic port).

It does four things, all deterministic and reproducible (fixed seeds):

  1. Differential test. On random small configurations it explores every interleaving of
     rule applications with worst-case workers and compares the outcome with the static
     checker. Theorem 1 says the two must agree. It also checks that the test can fail, by
     running it against a deliberately broken checker.
  2. Spawn admission. On random configurations it adds a random worker and compares the
     local admission test (Theorem 2) with a full check of the extended system.
  3. Ordering. The static checker reports a path for the looser reference configuration.
     The run model, with workers created and removed in the reference order, has no such
     run. With re-entry into the specification stage it has one.
  4. Incident replays. Recorded incidents are replayed as shortest witness traces.

Usage:  python3 dynamic.py            (about 20 seconds)
"""

import copy
import random
import sys
from collections import deque
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

import independence_check as ic
from independence_check import LEVEL, Compartment, System

Rule = Tuple[str, str, FrozenSet[str], str]   # (kind, agent, sources, target)


# ---- the colony: rules derived from the configuration, not from the influence graph ----

def colony_rules(s: System, mode: str) -> List[Rule]:
    """Read, write and port rules. Re-implements Definition 2 independently of System.graph."""
    rules: List[Rule] = []
    for c in s.comps.values():
        me = "@" + c.name
        if not c.model:
            declared_reads = set(c.reads)
            for n in sorted(c.writes):
                srcs = c.dep.get(n, declared_reads) if c.dep is not None else declared_reads
                rules.append(("port", c.name, frozenset(srcs), n))
            continue
        holder = c
        while holder.inherits and holder.parent:          # works with its parent's whole map
            holder = s.comps[holder.parent]
        by_access = mode == "access" or c.inherits
        reads: Set[str] = set() if by_access else set(c.reads)
        writes: Set[str] = set() if by_access else set(c.writes)
        for store, classes in s.stores.items():
            level = holder.acc[store] if store in holder.acc else s.default.get(store, "none")
            declared = store in c.acc
            if LEVEL[level] >= 1 and (by_access or not declared):
                reads |= {store + ":" + k for k in classes}
            if LEVEL[level] == 2 and by_access:
                allowed = s.machine_classes.get(store, set(classes))
                writes |= {store + ":" + k for k in allowed}
        for n in sorted(reads):
            rules.append(("read", me, frozenset([n]), me))
        for n in sorted(writes):
            rules.append(("write", me, frozenset([me]), n))
    return rules


def fire(rule: Rule, tainted: FrozenSet[str], mediators: Set[str]) -> FrozenSet[str]:
    """Worst-case application: the target takes the mark if any source carries it."""
    _, _, srcs, target = rule
    if target in mediators or target in tainted or not (srcs & tainted):
        return tainted
    return tainted | {target}


def explore(rules: List[Rule], sources: Set[str], target: str, mediators: Set[str],
            limit: int = 200000) -> Optional[List[Rule]]:
    """Every interleaving, breadth first. Returns a shortest witness trace or None."""
    start = frozenset(x for x in sources if x not in mediators)
    if target in start:
        return []
    seen = {start}
    queue = deque([(start, [])])
    while queue:
        tainted, trace = queue.popleft()
        for r in rules:
            nxt = fire(r, tainted, mediators)
            if nxt is tainted or nxt in seen:
                continue
            if target in nxt:
                return trace + [r]
            seen.add(nxt)
            if len(seen) > limit:
                raise RuntimeError("state limit reached")
            queue.append((nxt, trace + [r]))
    return None


def saturate(rules: List[Rule], tainted: Set[str], mediators: Set[str]) -> Set[str]:
    """Least fixed point. Exact for worst-case workers because marks only accumulate."""
    tainted = set(tainted)
    changed = True
    while changed:
        changed = False
        for _, _, srcs, target in rules:
            if target not in mediators and target not in tainted and srcs & tainted:
                tainted.add(target)
                changed = True
    return tainted


def show(trace: List[Rule]) -> str:
    out = []
    for kind, agent, srcs, target in trace:
        if kind == "read":
            out.append("%s reads %s" % (agent, next(iter(srcs))))
        elif kind == "write":
            out.append("%s writes %s" % (agent, target))
        else:
            out.append("fixed code %s writes %s" % (agent, target))
    return "; ".join(out)


# ---- 1. differential test ---------------------------------------------------------------

def random_system(rng: random.Random) -> System:
    stores = {"s%d" % i: ["k%d" % j for j in range(rng.randint(1, 3))] for i in range(rng.randint(2, 4))}
    names = list(stores)
    machine = {st: set(rng.sample(stores[st], rng.randint(0, len(stores[st])))) for st in names if rng.random() < 0.6}
    default = {st: rng.choice(["none", "none", "ro"]) for st in names}
    s = System("random", stores, set(names), default, machine)
    nodes = [st + ":" + k for st in names for k in stores[st]]
    host_acc = {st: "rw" for st in names}
    host_outs = rng.sample(nodes, rng.randint(0, 2))      # the host renders or collects a few nodes
    host_dep = {n: set(rng.sample(nodes, rng.randint(0, 2))) for n in host_outs}
    host_reads = set().union(*host_dep.values()) if host_dep else set()
    s.add(Compartment("host", "transport", False, None, host_acc, host_reads, set(host_outs), host_dep, spawn=[]))
    for i in range(rng.randint(0, 2)):                    # deterministic compartments
        outs = rng.sample(nodes, rng.randint(1, 2))
        dep = {n: set(rng.sample(nodes, rng.randint(0, 2))) for n in outs}
        reads = set().union(*dep.values()) if dep else set()
        s.add(Compartment("d%d" % i, "writer", False, "host", host_acc, reads, set(outs), dep, spawn=[]))
    for i in range(rng.randint(2, 4)):                    # model-driven compartments
        acc = {st: rng.choice(["none", "none", "ro", "rw"]) for st in names if rng.random() < 0.8}
        reads = set(rng.sample(nodes, rng.randint(0, 2)))
        writes = set(rng.sample(nodes, rng.randint(0, 1)))
        s.add(Compartment("m%d" % i, "other", True, "host", acc, reads, writes, spawn=[],
                          inherits=rng.random() < 0.15))
    return s


def random_requirement(rng: random.Random, s: System):
    nodes = [st + ":" + k for st in s.stores for k in s.stores[st]]
    models = ["@" + c.name for c in s.comps.values() if c.model]
    target = rng.choice(models)
    pool = nodes + [m for m in models if m != target]
    sources = set(rng.sample(pool, rng.randint(1, 2)))
    mediators = set(rng.sample(nodes, rng.randint(0, 2)))
    return sources, target, mediators


def broken_reaches(self, g, sources, target, avoid):       # a checker with a planted defect
    return System.reaches(self, g, sources, target, set())  # it ignores the mediators


def differential(n: int, seed: int, checker=System.reaches) -> Tuple[int, int, int]:
    rng = random.Random(seed)
    disagree = paths = 0
    for _ in range(n):
        s = random_system(rng)
        mode = rng.choice(["access", "instruction"])
        sources, target, mediators = random_requirement(rng, s)
        static = checker(s, s.graph(mode), sources, target, mediators)
        run = explore(colony_rules(s, mode), sources, target, mediators) is not None
        paths += static
        disagree += static != run
    return n, paths, disagree


# ---- 2. spawn admission -------------------------------------------------------------------

def admission(n: int, seed: int) -> Dict[str, int]:
    """Local test (forward and backward sets of the old system) against a full check.

    Counted separately for systems whose new channels are private and for systems in which
    some worker runs on its host's whole map, where the closed form does not apply.
    """
    rng = random.Random(seed)
    out = {"private": 0, "private refused": 0, "private disagree": 0, "shared": 0, "shared disagree": 0}
    done = 0
    while done < n:
        s = random_system(rng)
        sources, target, mediators = random_requirement(rng, s)
        g = s.graph("access")
        if s.reaches(g, sources, target, mediators):
            continue                                        # the requirement must hold beforehand
        done += 1
        nodes = [st + ":" + k for st in s.stores for k in s.stores[st]]
        acc = {st: rng.choice(["none", "ro", "rw"]) for st in s.stores}
        new = Compartment("w", "other", True, "host", acc, set(), set(), spawn=[])
        task_from = set(rng.sample(nodes, rng.randint(0, 2)))
        host_ports = [v for v in g if v.startswith("@host>")]
        result_to = set(rng.sample(host_ports, min(len(host_ports), rng.randint(0, 1))))
        inflow, outflow = ic.flows_of(s, new, "access", task_from, result_to)
        fwd = s.forward_set(g, sources, mediators)
        back = s.backward_set(g, target, mediators)
        local = bool((inflow - mediators) & fwd) and bool((outflow - mediators) & back)
        s2 = ic.spawn(s, new, task_from, result_to)
        full = s2.reaches(s2.graph("access"), sources, target, mediators)
        if ic.channels_private(s):
            out["private"] += 1
            out["private refused"] += local
            out["private disagree"] += local != full
        else:
            out["shared"] += 1
            out["shared disagree"] += local != full
    return out


# ---- 3. ordering: creation, removal and a promoter ---------------------------------------

def lifecycle_run(s: System, phases: List[Set[str]], edges: Dict[int, List[int]],
                  sources: Set[str], target: str, mediators: Set[str]) -> Optional[List[str]]:
    """Explore every path through a lifecycle. Each phase names the workers that exist.

    A worker's rules apply only while it exists. When a worker is removed its contents and its
    private channels are deleted with it (dissolution with loss). Within a phase the marks are
    saturated, which is exact because marks only accumulate and no rule is disabled by a mark.
    """
    rules = colony_rules(s, "access")
    models = {"@" + c.name for c in s.comps.values() if c.model}

    def enabled(alive: Set[str]) -> List[Rule]:
        return [r for r in rules if r[0] == "port" or r[1] in alive]

    def private(agent: str) -> Set[str]:
        name = agent[1:]
        return {agent, "in." + name + ":task", "out." + name + ":result", "ws." + name + ":scratch"}

    start = frozenset(saturate(enabled(phases[0]), {x for x in sources if x in phases[0] or x not in models}, mediators))
    seen = {(0, start)}
    queue = deque([(0, start, ["phase 0"])])
    while queue:
        i, tainted, path = queue.popleft()
        if target in tainted:
            return path
        for j in edges.get(i, []):
            kept = set(tainted)
            for gone in phases[i] - phases[j]:
                kept -= private(gone)
            born = {x for x in sources if x in phases[j] and x in models}
            nxt = frozenset(saturate(enabled(phases[j]), kept | born, mediators))
            if (j, nxt) not in seen:
                seen.add((j, nxt))
                queue.append((j, nxt, path + ["phase %d" % j]))
    return None


def ordering() -> List[Tuple[str, str]]:
    s = ic.reference_ro_spec_maker()
    sources, target = {"@implementer"}, "@test_author"
    static = s.reaches(s.graph("access"), sources, target, set())
    reviewers = {"@reviewer_a", "@reviewer_b", "@reconciler", "@verifier"}
    phases = [
        {"@spec_maker", "@extractor"},        # 0 specification
        {"@spec_maker", "@test_author"},      # 1 tests are written
        {"@spec_maker"},                      # 2 tests frozen, test author removed
        {"@spec_maker", "@implementer"},      # 3 implementation (promoter: tests frozen)
        reviewers,                            # 4 review
    ]
    in_order = {0: [1], 1: [2], 2: [3], 3: [4]}
    re_entry = {0: [1], 1: [2], 2: [3], 3: [4, 1]}
    out = [("static checker (no order)", "path reported" if static else "no path")]
    for label, edges in (("run model, reference order", in_order),
                         ("run model, item may return to the specification stage", re_entry)):
        w = lifecycle_run(s, phases, edges, sources, target, set())
        out.append((label, "no run reaches the test author" if w is None else "run found: " + " > ".join(w)))
    return out


# ---- 4. incident replays -------------------------------------------------------------------

def replay(label: str, s: System, sources: Set[str], target: str, mediators: Set[str]) -> Tuple[str, str]:
    w = explore_small(s, sources, target, mediators)
    return label, ("no run" if w is None else "%d steps: %s" % (len(w), show(w)))


def explore_small(s: System, sources: Set[str], target: str, mediators: Set[str]) -> Optional[List[Rule]]:
    """Shortest witness on a full-size configuration: breadth-first over single marks."""
    rules = colony_rules(s, "access")
    start = [x for x in sources if x not in mediators]
    prev: Dict[str, Tuple[Optional[str], Optional[Rule]]] = {x: (None, None) for x in start}
    queue = deque(start)
    while queue:
        v = queue.popleft()
        if v == target:
            trace = []
            while prev[v][1] is not None:
                trace.append(prev[v][1])
                v = prev[v][0]
            return trace[::-1]
        for r in rules:
            if v in r[2] and r[3] not in prev and r[3] not in mediators:
                prev[r[3]] = (v, r)
                queue.append(r[3])
    return None


def task_after_cut(second_path_guarded: bool) -> Optional[List[str]]:
    """A worker must not hold its task while it still has its parent's levels.

    State: (levels cut?, promoter present?, worker holds the task?). The cut rule writes the
    promoter into the host's control store. Delivery rules are promoted by it. The recorded
    incident is a second delivery path that did not carry the promoter.
    """
    start = (False, False, False)
    seen = {start}
    queue = deque([(start, [])])
    while queue:
        (cut, kappa, holds), trace = queue.popleft()
        if holds and not cut:
            return trace
        moves = [("cut", (True, True, holds))]
        if kappa:
            moves.append(("deliver by the intended path", (cut, kappa, True)))
        if kappa or not second_path_guarded:
            moves.append(("deliver by the second path", (cut, kappa, True)))
        for name, nxt in moves:
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, trace + [name]))
    return None


def incidents() -> List[Tuple[str, str]]:
    muts = dict((name.split()[0], m) for name, m in ic.mutations())
    out = []
    ref = ic.reference()
    foreign = "@foreign"
    out.append(replay("Ref: foreign machine text to the blind extractor", ref, {foreign}, "@extractor", set()))
    out.append(replay("M2 machine text classed as human, to the blind extractor", muts["M2"], {foreign}, "@extractor", set()))
    out.append(replay("Ref: verifier to the external channel, bypassing the gate", ref, {"@verifier"}, "external:message", {"artifacts:gate"}))
    out.append(replay("M3 worker files out of band", muts["M3"], {"@verifier"}, "external:message", {"artifacts:gate"}))
    out.append(replay("M1 maker's helper: maker to a reviewer, bypassing the change", muts["M1"], {"@implementer"}, "@reviewer_a", {"codehost:change"}))
    out.append(replay("M4 no cut before the task: maker's requirement list to the blind extractor", muts["M4"], {"@spec_maker"}, "@extractor", set()))
    for guarded in (True, False):
        w = task_after_cut(guarded)
        out.append(("task delivery, second path %s the promoter" % ("carries" if guarded else "lacks"),
                    "no run delivers the task before the cut" if w is None else "run found: " + "; ".join(w)))
    return out


def main() -> None:
    n = 20000
    total, paths, bad = differential(n, seed=1)
    print("1. differential test: %d random configurations, %d with a path, %d disagreements" % (total, paths, bad))
    _, _, caught = differential(2000, seed=2, checker=broken_reaches)
    print("   against a checker that ignores mediators: %d disagreements in 2000 (the test can fail)" % caught)
    a = admission(n, seed=3)
    print("2. spawn admission, closed form against the full check on %d random spawns" % n)
    print("   new channels private:     %d spawns, %d refused, %d disagreements" % (a["private"], a["private refused"], a["private disagree"]))
    print("   a sibling on its host's map: %d spawns, %d wrongly admitted by the closed form" % (a["shared"], a["shared disagree"]))
    print("3. ordering (requirement B2 on Ref-ro)")
    for label, result in ordering():
        print("   %-56s %s" % (label, result))
    print("4. incident replays (shortest witness traces)")
    for label, result in incidents():
        print("   %s\n      %s" % (label, result))


if __name__ == "__main__":
    main()
