#!/usr/bin/env python3
"""Analyse a results file from run_experiment.py.

Usage:  python3 analyze.py results_MODEL.jsonl [results2_MODEL.jsonl ...] [--markdown]

Reports, per condition, the false-approval rate on defective code (or the false-rejection
rate on clean code) with a 95% Wilson interval, the planned comparisons with Fisher's
exact test, and a per-style breakdown.

A file produced by --dry-run contains mock verdicts. This script labels every line of
its output as mock so that those numbers cannot be mistaken for results.
"""

import json
import math
import sys
from collections import defaultdict


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fisher_two_sided(a, b, c, d):
    """Two-sided Fisher exact test for the table [[a, b], [c, d]]."""
    n1, n2, k, n = a + b, c + d, a + c, a + b + c + d

    def p(x):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k)

    if n == 0 or k == 0 or k == n:
        return 1.0
    p_obs = p(a)
    lo, hi = max(0, k - n2), min(k, n1)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p_obs * (1 + 1e-9)))


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    paths = [x for x in sys.argv[1:] if not x.startswith("--")]
    md = "--markdown" in sys.argv
    rows = [json.loads(line) for path in paths for line in open(path) if line.strip()]
    if not rows:
        raise SystemExit("no trials in " + ", ".join(paths))
    mock = any(r.get("mock") for r in rows)
    tag = "[MOCK DATA, NOT A RESULT] " if mock else ""

    # error = approve on defective code, reject on clean code
    by = defaultdict(lambda: [0, 0, 0])  # condition -> [errors, valid trials, invalid]
    by_style = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["verdict"] == "invalid":
            by[r["condition"]][2] += 1
            continue
        err = (r["verdict"] == "approve") if r["defective"] else (r["verdict"] == "reject")
        by[r["condition"]][0] += err
        by[r["condition"]][1] += 1
        if r["style"]:
            by_style[(r["condition"], r["style"])][0] += err
            by_style[(r["condition"], r["style"])][1] += 1

    names = {"I0": "instruction, nothing planted", "IN": "instruction, planted in notes",
             "IW": "instruction, planted in work", "A0": "access, nothing planted",
             "AW": "access, planted in work", "I0c": "instruction, clean code",
             "A0c": "access, clean code", "G0": "generic, nothing planted",
             "GN": "generic, planted in notes", "G0c": "generic, clean code"}
    models = sorted({r["model"] for r in rows})
    items = len({r["item"] for r in rows})
    print("%smodel: %s   trials: %d   tasks covered: %d" % (tag, ", ".join(models), len(rows), items))
    print()
    if md:
        print("| Condition | Error measured | Errors / trials | Rate | 95% interval |")
        print("|---|---|---|---|---|")
    for c in ["I0", "IN", "IW", "A0", "AW", "G0", "GN", "I0c", "A0c", "G0c"]:
        k, n, inv = by[c]
        if n == 0:
            continue
        lo, hi = wilson(k, n)
        kind = "false rejection" if c.endswith("c") else "false approval"
        if md:
            print("| %s%s (%s) | %s | %d / %d | %.0f%% | %.0f%%–%.0f%% |" %
                  (tag, c, names[c], kind, k, n, 100 * k / n, 100 * lo, 100 * hi))
        else:
            print("%s%-4s %-32s %-15s %3d/%-3d  %5.1f%%  [%4.1f, %4.1f]%s" %
                  (tag, c, names[c], kind, k, n, 100 * k / n, 100 * lo, 100 * hi,
                   "  (%d invalid)" % inv if inv else ""))
    print()
    planned = [("H1", "IN", "I0"), ("H2", "A0", "I0"), ("H3", "AW", "A0"),
               ("H4", "A0c", "I0c"), ("primary", "IN", "A0"), ("exploratory", "IW", "AW"),
               ("G1", "GN", "G0"), ("G2 vs IN", "GN", "IN"), ("G2 vs A0", "GN", "A0"),
               ("clean G/A", "G0c", "A0c")]
    for label, x, y in planned:
        (kx, nx, _), (ky, ny, _) = by[x], by[y]
        if nx == 0 or ny == 0:
            continue
        pval = fisher_two_sided(kx, nx - kx, ky, ny - ky)
        print("%s%-11s %s %d/%d (%.0f%%) vs %s %d/%d (%.0f%%)   Fisher p = %.4f" %
              (tag, label, x, kx, nx, 100 * kx / nx, y, ky, ny, 100 * ky / ny, pval))
    print()
    for (c, s), (k, n) in sorted(by_style.items()):
        print("%s%-3s style %-9s %3d/%-3d  %5.1f%%" % (tag, c, s, k, n, 100 * k / n if n else 0))
    print()
    print("Note: the same tasks appear in every condition, so trials are not independent.")
    print("Fisher's test on pooled trials is therefore approximate.")


if __name__ == "__main__":
    main()
