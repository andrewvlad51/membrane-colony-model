#!/usr/bin/env python3
"""Static independence checker for compartment (membrane) systems.

Companion artefact for the paper "Independence by Access: A Colony
Model of Separation of Duties in Autonomous AI Pipelines".

A system is a set of compartments (membranes) that never talk to each other
directly. Each compartment exchanges objects only with stores in a shared
environment, and an enforcement layer grants each compartment a level
(none / ro / rw) per store. Objects in a store belong to classes.

Two kinds of compartment exist:

* model-driven: its behaviour is not trusted. Under ACCESS semantics it may read
  every class of every store it holds `ro` or `rw` on, and may write every
  machine-writable class of every store it holds `rw` on. Under INSTRUCTION
  semantics it is assumed to follow its declared reads and writes.
* deterministic: fixed code. It reads and writes exactly its declared rules, and
  each output depends only on the inputs listed for it.

The checker builds the influence graph for the chosen semantics and tests eight
properties (P1-P8). It needs only the Python standard library.

Usage:  python3 independence_check.py            # table for all configurations
        python3 independence_check.py --verbose  # also print each violation
"""

import copy
import sys
import time
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

LEVEL = {"none": 0, "ro": 1, "rw": 2}


class Compartment:
    def __init__(
        self,
        name: str,
        role: str,
        model: bool,
        parent: Optional[str],
        acc: Dict[str, str],
        reads: Optional[Set[str]] = None,
        writes: Optional[Set[str]] = None,
        dep: Optional[Dict[str, Set[str]]] = None,
        spawn: Optional[List[str]] = None,
        inherits: bool = False,
    ) -> None:
        self.name = name
        self.role = role  # maker | checker | transport | writer | gate | foreign
        self.model = model  # True = model-driven, False = deterministic
        self.parent = parent
        self.acc = dict(acc)  # explicit levels per store; missing = undeclared
        self.reads = set(reads or set())  # declared (intended) reads, "store:class"
        self.writes = set(writes or set())  # declared (intended) writes
        self.dep = dep  # deterministic only: output node -> input nodes
        self.spawn = spawn  # None = undeclared (unrestricted); [] = may spawn nothing
        self.inherits = inherits  # True = works on its task with the parent's map


class System:
    def __init__(
        self,
        name: str,
        stores: Dict[str, List[str]],
        shared: Set[str],
        default: Dict[str, str],
        machine_classes: Dict[str, Set[str]],
    ) -> None:
        self.name = name
        self.stores = stores  # store -> classes
        self.shared = shared  # stores that are shared services (not private channels)
        self.default = default  # level applied when a compartment declares nothing
        self.machine_classes = machine_classes  # classes a machine identity can write
        self.comps: Dict[str, Compartment] = {}

    def add(self, comp: Compartment) -> None:
        self.comps[comp.name] = comp

    # ---- access -----------------------------------------------------------------
    def level(self, c: Compartment, store: str) -> str:
        if c.inherits and c.parent:
            return self.level(self.comps[c.parent], store)
        if store in c.acc:
            return c.acc[store]
        return self.default.get(store, "none")

    def nodes_of(self, store: str) -> Set[str]:
        return {store + ":" + k for k in self.stores[store]}

    def reads(self, c: Compartment, mode: str) -> Set[str]:
        if not c.model or (mode == "instruction" and not c.inherits):
            base = set(c.reads)
            if c.model:  # undeclared stores still merge their default level
                for s in self.stores:
                    if s not in c.acc and LEVEL[self.level(c, s)] >= 1:
                        base |= self.nodes_of(s)
            return base
        out: Set[str] = set()
        for s in self.stores:
            if LEVEL[self.level(c, s)] >= 1:
                out |= self.nodes_of(s)
        return out

    def writes(self, c: Compartment, mode: str) -> Set[str]:
        if not c.model or (mode == "instruction" and not c.inherits):
            return set(c.writes)
        out: Set[str] = set()
        for s in self.stores:
            if LEVEL[self.level(c, s)] == 2:
                allowed = self.machine_classes.get(s, set(self.stores[s]))
                out |= {s + ":" + k for k in allowed}
        return out

    # ---- influence graph ----------------------------------------------------------
    def graph(self, mode: str) -> Dict[str, Set[str]]:
        g: Dict[str, Set[str]] = {}

        def edge(a: str, b: str) -> None:
            g.setdefault(a, set()).add(b)
            g.setdefault(b, set())

        for c in self.comps.values():
            r, w = self.reads(c, mode), self.writes(c, mode)
            if c.model:
                me = "@" + c.name
                g.setdefault(me, set())
                for n in r:
                    edge(n, me)
                for n in w:
                    edge(me, n)
            else:
                for n in w:
                    port = "@" + c.name + ">" + n
                    edge(port, n)
                    srcs = c.dep.get(n, r) if c.dep is not None else r
                    for i in srcs:
                        edge(i, port)
        return g

    def reaches(self, g: Dict[str, Set[str]], sources: Set[str], target: str, avoid: Set[str]) -> bool:
        seen = set(s for s in sources if s not in avoid)
        queue = deque(seen)
        while queue:
            n = queue.popleft()
            if n == target:
                return True
            for m in g.get(n, ()):
                if m not in seen and m not in avoid:
                    seen.add(m)
                    queue.append(m)
        return False


    def forward_set(self, g: Dict[str, Set[str]], sources: Set[str], avoid: Set[str]) -> Set[str]:
        """F: every vertex reachable from a forbidden source on a path that avoids the mediators."""
        seen = set(s for s in sources if s not in avoid)
        queue = deque(seen)
        while queue:
            n = queue.popleft()
            for m in g.get(n, ()):
                if m not in seen and m not in avoid:
                    seen.add(m)
                    queue.append(m)
        return seen

    def backward_set(self, g: Dict[str, Set[str]], target: str, avoid: Set[str]) -> Set[str]:
        """B: every vertex from which the checker is reachable on a path that avoids the mediators."""
        rev: Dict[str, Set[str]] = {}
        for a, outs in g.items():
            for b in outs:
                rev.setdefault(b, set()).add(a)
        seen = {target}
        queue = deque(seen)
        while queue:
            n = queue.popleft()
            for m in rev.get(n, ()):
                if m not in seen and m not in avoid:
                    seen.add(m)
                    queue.append(m)
        return seen


# ---- spawn admission (Theorem 2) ------------------------------------------------------

def flows_of(sys_: System, c: Compartment, mode: str,
             task_from: Set[str], result_to: Set[str]) -> Tuple[Set[str], Set[str]]:
    """Inflow and outflow sets of a worker that is about to be created.

    Inflow: the nodes it may read by its levels, plus the nodes its task is rendered from.
    Outflow: the nodes it may write by its levels, plus the ports whose output will depend
    on its result. Its private task and result channels are new and are not listed.
    """
    private = {"in." + c.name + ":task", "out." + c.name + ":result"}
    return (sys_.reads(c, mode) - private) | set(task_from), (sys_.writes(c, mode) - private) | set(result_to)


def channels_private(sys_: System) -> bool:
    """True if no existing worker would hold a level on channels created for a new worker.

    A worker that runs on its host's whole map (a P6 violation) gains every level the host
    gains, so it can read and write the channels of every worker the host creates later.
    """
    return not any(c.model and c.inherits for c in sys_.comps.values())


def admit(sys_: System, mode: str, c: Compartment, task_from: Set[str],
          result_to: Set[str]) -> List[str]:
    """Local admission test. Returns the blindness requirements the new worker would break.

    Uses only the forward and backward sets of the existing system: the worker is refused
    exactly when its inflow meets F and its outflow meets B (outside the mediators).
    The closed form needs the new channels to be private. If they are not, the extended
    system is checked in full.
    """
    if not channels_private(sys_):
        return list(check(spawn(sys_, c, task_from, result_to), mode)["P1"])
    g = sys_.graph(mode)
    inflow, outflow = flows_of(sys_, c, mode, task_from, result_to)
    broken = []
    for label, checkers, forbidden, mediators in blindness_instances(sys_, mode):
        fwd = sys_.forward_set(g, forbidden, mediators)
        for k in checkers:
            if k not in sys_.comps:
                continue
            back = sys_.backward_set(g, "@" + k, mediators)
            if (inflow - mediators) & fwd and (outflow - mediators) & back:
                broken.append("%s: violated for %s" % (label, k))
    return broken


def spawn(sys_: System, c: Compartment, task_from: Set[str], result_to: Set[str]) -> System:
    """The system after the worker is created, with its private channels wired to the host."""
    s2 = copy.deepcopy(sys_)
    s2.stores["in." + c.name] = ["task"]
    s2.stores["out." + c.name] = ["result"]
    c = copy.deepcopy(c)
    c.acc.setdefault("in." + c.name, "ro")
    c.acc.setdefault("out." + c.name, "rw")
    c.reads |= {"in." + c.name + ":task"}
    c.writes |= {"out." + c.name + ":result"}
    s2.add(c)
    host = s2.comps["host"]
    host.acc["in." + c.name] = host.acc["out." + c.name] = "rw"
    host.dep["in." + c.name + ":task"] = set(task_from)
    host.writes.add("in." + c.name + ":task")
    host.reads |= set(task_from) | {"out." + c.name + ":result"}
    for port in result_to:                      # "@host>node": that output now depends on the result
        node = port.split(">", 1)[1]
        host.dep.setdefault(node, set()).add("out." + c.name + ":result")
        host.writes.add(node)
    return s2


# ---- properties ---------------------------------------------------------------------

# P1 blindness requirements B1-B4: (label, checkers, forbidden sources, mediators)
def blindness_instances(sys_: System, mode: str) -> List[Tuple[str, List[str], Set[str], Set[str]]]:
    foreign_out: Set[str] = set()
    for c in sys_.comps.values():
        if c.role == "foreign":
            foreign_out |= sys_.writes(c, mode)
    return [
        ("B1 blind extractor sees nothing the spec maker wrote", ["extractor"],
         {"@spec_maker"}, set()),
        ("B2 test author sees no implementation", ["test_author"],
         {"ws.implementer:scratch", "codehost:change"}, set()),
        ("B3 checkers see the maker only through the committed change",
         ["reviewer_a", "reviewer_b", "reconciler", "verifier"],
         {"ws.implementer:scratch"}, {"codehost:change"}),
        ("B4 checkers see no foreign machine text",
         ["extractor", "test_author", "reviewer_a", "reviewer_b", "reconciler", "verifier"],
         foreign_out, set()),
    ]


APPROVAL_NODES = {"codehost:review", "artifacts:verdict", "artifacts:gate"}
PROTECTED_NODES = ["codehost:change", "codehost:review", "artifacts:gate", "external:message"]
ROUTING_NODES = ["artifacts:gate"]


def check(sys_: System, mode: str) -> Dict[str, List[str]]:
    """Return violations per property for one configuration and one semantics."""
    v: Dict[str, List[str]] = {"P%d" % i: [] for i in range(1, 9)}
    g = sys_.graph(mode)
    comps = sys_.comps

    # P1 blindness: every path from a forbidden source to a checker passes a mediator.
    for label, checkers, forbidden, mediators in blindness_instances(sys_, mode):
        for c in checkers:
            if c in comps and sys_.reaches(g, forbidden, "@" + c, mediators):
                v["P1"].append("%s: violated for %s" % (label, c))

    # P2 no self-judgment: a maker cannot write where verdicts are written.
    checker_out: Set[str] = set(APPROVAL_NODES)
    for c in comps.values():
        if c.role == "checker":
            checker_out |= {"out." + c.name + ":result"}
    for c in comps.values():
        if c.role == "maker":
            hit = sys_.writes(c, mode) & checker_out
            if hit:
                v["P2"].append("maker %s can write %s" % (c.name, sorted(hit)))

    # P3 monotone attenuation: a child never holds more than its parent.
    for c in comps.values():
        if c.parent:
            p = comps[c.parent]
            for s in sys_.stores:
                if LEVEL[sys_.level(c, s)] > LEVEL[sys_.level(p, s)]:
                    v["P3"].append("%s exceeds parent on %s" % (c.name, s))

    # P4 single deterministic writer for each protected node.
    for n in PROTECTED_NODES:
        writers = sorted(c.name for c in comps.values() if n in sys_.writes(c, mode))
        if len(writers) != 1 or comps[writers[0]].model:
            v["P4"].append("%s writable by %s" % (n, writers))

    # P5 model-free disposition: only deterministic compartments write routing state.
    for n in ROUTING_NODES:
        for c in comps.values():
            if c.model and n in sys_.writes(c, mode):
                v["P5"].append("model-driven %s can write %s" % (c.name, n))
    for c in comps.values():
        if c.role == "gate" and c.model:
            v["P5"].append("gate %s is model-driven" % c.name)

    # P6 task after privilege cut: nobody works on a task with an inherited map.
    for c in comps.values():
        if c.model and c.inherits:
            v["P6"].append("%s works with its parent's whole map" % c.name)

    # P7 declared delegation: undeclared spawn rights are unrestricted; makers get none.
    for c in comps.values():
        if c.model and c.role != "foreign":
            if c.spawn is None:
                v["P7"].append("%s has undeclared (unrestricted) spawn rights" % c.name)
            elif c.role == "maker" and c.spawn:
                v["P7"].append("maker %s may spawn %s" % (c.name, c.spawn))

    # P8 explicit levels: every shared store is declared, so no default merges in.
    for c in comps.values():
        if c.model and c.role != "foreign" and not c.inherits:
            missing = sorted(s for s in sys_.shared if s not in c.acc)
            if missing:
                v["P8"].append("%s leaves %s undeclared" % (c.name, missing))
    return v


def requirement_ids(v: Dict[str, List[str]]) -> Set[str]:
    """Violated requirements of P1, P2, P4 and P5 as short identifiers."""
    out: Set[str] = set()
    for line in v["P1"]:
        out.add("%s/%s" % (line.split()[0], line.rsplit(" ", 1)[1]))
    for line in v["P2"]:
        out.add("P2/" + line.split()[1])
    for line in v["P4"]:
        out.add("P4/" + line.split()[0])
    for line in v["P5"]:
        out.add("P5/" + line.split()[1])
    return out


def obedience_gap(sys_: System) -> Set[str]:
    """Requirements that hold if every worker obeys its instructions and fail under access."""
    return requirement_ids(check(sys_, "access")) - requirement_ids(check(sys_, "instruction"))


# ---- the encoded pipeline -------------------------------------------------------------

WORKERS = ["spec_maker", "extractor", "test_author", "implementer", "reviewer_a",
           "reviewer_b", "reconciler", "verifier"]


def base_system(name: str) -> System:
    stores = {
        "tracker": ["request", "note", "status"],   # request tracker
        "codehost": ["base", "change", "review"],   # code host
        "artifacts": ["spec", "reqs_maker", "reqs_indep", "tests", "drafts", "verdict", "gate"],
        "external": ["message"],                    # customer-facing channel
        "ws.implementer": ["scratch"],                    # the maker's private workspace
    }
    for w in WORKERS:
        stores["in." + w] = ["task"]                # facts rendered for the worker
        stores["out." + w] = ["result"]             # the worker's only output channel
    shared = {"tracker", "codehost", "artifacts", "external"}
    default = {"tracker": "ro", "codehost": "ro", "artifacts": "ro", "external": "none"}
    machine_classes = {
        "tracker": {"note", "status"},              # the tracker stamps machine authors
        "codehost": {"change", "review"},           # the base branch is protected
    }
    return System(name, stores, shared, default, machine_classes)


def none_all(**levels: str) -> Dict[str, str]:
    acc = {"tracker": "none", "codehost": "none", "artifacts": "none", "external": "none"}
    acc.update(levels)
    return acc


def add_host_and_writers(s: System) -> None:
    host_acc = {st: "rw" for st in s.stores}
    dep = {
        # facts rendered into each worker's task (instead of granting reads)
        "in.spec_maker:task": {"tracker:request", "codehost:base"},
        "in.extractor:task": {"tracker:request"},
        "in.test_author:task": {"artifacts:spec", "codehost:base"},
        "in.implementer:task": {"artifacts:spec", "artifacts:tests", "codehost:base"},
        "in.reviewer_a:task": {"artifacts:spec", "codehost:change"},
        "in.reviewer_b:task": {"artifacts:spec", "codehost:change"},
        "in.reconciler:task": {"artifacts:drafts", "codehost:change"},
        "in.verifier:task": {"artifacts:spec", "codehost:change"},
        # results collected from each worker's output channel
        "artifacts:spec": {"out.spec_maker:result"},
        "artifacts:reqs_maker": {"out.spec_maker:result"},
        "artifacts:reqs_indep": {"out.extractor:result"},
        "artifacts:tests": {"out.test_author:result"},
        "artifacts:drafts": {"out.reviewer_a:result", "out.reviewer_b:result"},
        "artifacts:verdict": {"out.reconciler:result", "out.verifier:result",
                              "artifacts:reqs_maker", "artifacts:reqs_indep"},
        # the tracker label is a mirror of the pipeline-owned decision
        "tracker:status": {"artifacts:gate"},
    }
    reads: Set[str] = set()
    for srcs in dep.values():
        reads |= srcs
    s.add(Compartment("host", "transport", False, None, host_acc, reads, set(dep), dep,
                      spawn=list(WORKERS)))
    s.add(Compartment("committer", "writer", False, "host",
                      none_all(codehost="rw", **{"ws.implementer": "ro"}),
                      {"ws.implementer:scratch"}, {"codehost:change"},
                      {"codehost:change": {"ws.implementer:scratch"}}, spawn=[]))
    s.add(Compartment("review_writer", "writer", False, "host",
                      none_all(codehost="rw", artifacts="ro"),
                      {"artifacts:verdict", "codehost:change"}, {"codehost:review"},
                      {"codehost:review": {"artifacts:verdict", "codehost:change"}}, spawn=[]))
    s.add(Compartment("gate", "gate", False, "host",
                      none_all(codehost="ro", artifacts="rw"),
                      {"codehost:review", "codehost:change", "artifacts:verdict"},
                      {"artifacts:gate"},
                      {"artifacts:gate": {"codehost:review", "codehost:change",
                                          "artifacts:verdict"}}, spawn=[]))
    s.add(Compartment("notifier", "writer", False, "host",
                      none_all(artifacts="ro", external="rw"),
                      {"artifacts:gate"}, {"external:message"},
                      {"external:message": {"artifacts:gate"}}, spawn=[]))
    # another pipeline's worker that shares the request tracker
    s.add(Compartment("foreign", "foreign", True, None, {"tracker": "rw"},
                      {"tracker:request", "tracker:note"}, {"tracker:note"}))


def worker(s: System, name: str, role: str, extra: Dict[str, str],
           reads: Set[str], writes: Set[str]) -> None:
    acc = none_all(**extra)
    acc["in." + name] = "ro"
    acc["out." + name] = "rw"
    s.add(Compartment(name, role, True, "host", acc,
                      {"in." + name + ":task"} | reads,
                      {"out." + name + ":result"} | writes, spawn=[]))


def reference() -> System:
    """Independence by access: workers hold no write path to shared services.

    Workers downstream of the implementation hold `ro` on the code host and no push
    identity. The spec maker, the blind extractor and the test author hold nothing on
    shared services and work from facts rendered into their task.
    """
    s = base_system("Ref     strict reference")
    add_host_and_writers(s)
    code = {"codehost:base", "codehost:change", "codehost:review"}
    worker(s, "spec_maker", "maker", {}, set(), set())
    worker(s, "extractor", "checker", {}, set(), set())
    worker(s, "test_author", "checker", {}, set(), set())
    worker(s, "implementer", "maker", {"codehost": "ro", "ws.implementer": "rw"},
           code | {"ws.implementer:scratch"}, {"ws.implementer:scratch"})
    worker(s, "reviewer_a", "checker", {"codehost": "ro"}, code, set())
    worker(s, "reviewer_b", "checker", {"codehost": "ro"}, code, set())
    worker(s, "reconciler", "checker", {"codehost": "ro"}, code, set())
    worker(s, "verifier", "checker", {"codehost": "ro"}, code, set())
    return s


def reference_ro_spec_maker() -> System:
    """The looser reference rule: every code-reading worker holds `ro`.

    The spec maker then reads the whole code host, including earlier change
    branches, so implementation text can reach the test author through the spec.
    """
    s = reference()
    s.name = "Ref-ro  spec maker reads code host"
    s.comps["spec_maker"].acc["codehost"] = "ro"
    s.comps["spec_maker"].reads |= {"codehost:base", "codehost:change", "codehost:review"}
    return s


def observed() -> System:
    """Independence partly by instruction: levels recorded for an operational pipeline.

    The reference topology with the access levels recorded for one operational
    pipeline's maker and review roles: `rw` on the code host and `ro` on
    the request tracker. The workflow tells the maker not to push and tells two of
    the three review roles not to write. The blind extractor is cut by access.
    This is not a full model of that pipeline: roles whose levels were not
    recorded keep their reference levels.
    """
    s = reference()
    s.name = "Prod    recorded operational levels"
    for n in ("implementer", "reviewer_a", "reviewer_b", "reconciler"):
        s.comps[n].acc["codehost"] = "rw"
        s.comps[n].acc["tracker"] = "ro"
        s.comps[n].reads |= {"tracker:request"}
    s.comps["reconciler"].writes |= {"codehost:review"}  # the one intended writer
    # in this configuration the review marker is written by the reconciler itself
    del s.comps["review_writer"]
    return s


def mutations() -> List[Tuple[str, System]]:
    out: List[Tuple[str, System]] = []

    m = reference(); m.name = "M1 maker may delegate"
    m.comps["implementer"].spawn = None
    out.append((m.name, m))

    m = reference(); m.name = "M2 machine text classed as human"
    m.machine_classes["tracker"] = {"note", "status", "request"}
    out.append((m.name, m))

    m = reference(); m.name = "M3 worker files out of band"
    m.comps["verifier"].acc["external"] = "rw"
    out.append((m.name, m))

    m = reference(); m.name = "M4 no privilege cut before the task"
    m.comps["extractor"].inherits = True
    out.append((m.name, m))

    m = reference(); m.name = "M5 read-only identity widened"
    for c in m.comps.values():
        if c.model and c.acc.get("codehost") == "ro":
            c.acc["codehost"] = "rw"
    out.append((m.name, m))

    m = reference(); m.name = "M6 checkers share the maker's workspace"
    for n in ("reviewer_a", "reviewer_b"):
        m.comps[n].acc["ws.implementer"] = "ro"
    out.append((m.name, m))

    m = reference(); m.name = "M7 maker shares the verifier's channel"
    m.comps["implementer"].acc["out.verifier"] = "rw"
    out.append((m.name, m))

    m = reference(); m.name = "M8 level left to the default"
    del m.comps["extractor"].acc["artifacts"]
    out.append((m.name, m))

    m = reference(); m.name = "M9 model placed in the gate"
    m.comps["gate"].model = True
    out.append((m.name, m))

    m = reference(); m.name = "M10 child granted more than its parent"
    m.comps["host"].acc["external"] = "ro"
    out.append((m.name, m))
    return out


def spawn_candidates(ref: System):
    code = {"codehost:base", "codehost:change", "codehost:review"}
    third = Compartment("reviewer_c", "checker", True, "host",
                        none_all(codehost="ro"), set(code), set(), spawn=[])
    helper = Compartment("helper", "transport", True, "host", {}, set(), set(), spawn=[], inherits=True)
    scribe = Compartment("scribe", "transport", True, "host",
                         none_all(**{"ws.implementer": "ro"}), {"ws.implementer:scratch"}, set(), spawn=[])
    reader = Compartment("reader", "transport", True, "host",
                         none_all(**{"ws.implementer": "ro"}), {"ws.implementer:scratch"}, set(), spawn=[])
    return [
        ("third reviewer, wired like an existing reviewer", third,
         {"artifacts:spec", "codehost:change"}, {"@host>artifacts:drafts"}),
        ("helper created with its host's whole map", helper, {"tracker:request"}, set()),
        ("reads the maker's workspace, result feeds the drafts", scribe,
         {"tracker:request"}, {"@host>artifacts:drafts"}),
        ("reads the maker's workspace, result is not consumed", reader, {"tracker:request"}, set()),
    ]


def main() -> None:
    verbose = "--verbose" in sys.argv
    props = ["P%d" % i for i in range(1, 9)]
    rows: List[Tuple[str, str, Dict[str, List[str]]]] = []
    t0 = time.perf_counter()
    ref, ref1, obs = reference(), reference_ro_spec_maker(), observed()
    rows.append((ref.name, "access", check(ref, "access")))
    rows.append((ref1.name, "access", check(ref1, "access")))
    rows.append((obs.name, "instruction", check(obs, "instruction")))
    rows.append((obs.name, "access", check(obs, "access")))
    for name, m in mutations():
        rows.append((name, "access", check(m, "access")))
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    g = ref.graph("access")
    edges = sum(len(x) for x in g.values())
    print("strict reference: %d compartments, %d graph nodes, %d edges" %
          (len(ref.comps), len(g), edges))
    print("all %d checks ran in %.1f ms\n" % (len(rows), elapsed_ms))

    width = max(len(r[0]) for r in rows)
    print("%-*s  %-11s  %s" % (width, "configuration", "semantics", "  ".join(props)))
    for name, mode, v in rows:
        cells = "  ".join(" x" if v[p] else " ." for p in props)
        print("%-*s  %-11s  %s" % (width, name, mode, cells))
    print("\n. = holds, x = violated")

    print("\nobedience gap (holds under instruction, fails under access)")
    for label, system in (("Ref", ref), ("Ref-ro", ref1), ("Prod", obs)):
        gap = sorted(obedience_gap(system))
        print("  %-7s %d  %s" % (label, len(gap), ", ".join(gap) if gap else "-"))

    print("\nspawn admission on Ref (local test, then the full check on the extended system)")
    for label, comp, task_from, result_to in spawn_candidates(ref):
        local = admit(ref, "access", comp, task_from, result_to)
        full = [x for x in check(spawn(ref, comp, task_from, result_to), "access")["P1"]]
        verdict = "refused" if local else "admitted"
        agree = "agree" if bool(local) == bool(full) else "DISAGREE"
        print("  %-52s %-8s (%d broken; full check %d; %s)" % (label, verdict, len(local), len(full), agree))
        if verbose:
            for line in local:
                print("      " + line)
    if verbose:
        for name, mode, v in rows:
            print("\n== %s (%s)" % (name, mode))
            for p in props:
                for line in v[p]:
                    print("  %s  %s" % (p, line))


if __name__ == "__main__":
    main()
