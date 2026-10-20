#!/usr/bin/env python3
"""
hook-log.py - read the log that templates/debug-wrap.sh writes.

Usage:
    python3 hook-log.py               # last 40 runs
    python3 hook-log.py --errors      # runs that exited non-zero and not 2
    python3 hook-log.py --slow 50     # runs that took 50ms or more
    python3 hook-log.py --summary     # per hook: runs, blocks, errors, median and max ms
    python3 hook-log.py --watch       # follow new runs
    python3 hook-log.py --clear

Log line: <iso-time> <runtime> <event> exit=<code> <ms>ms <hook>
Log path: $HOOK_DEBUG_LOG, default ~/.cache/agent-hooks/debug.log
"""

import argparse
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path

LOG = Path(os.environ.get("HOOK_DEBUG_LOG", Path.home() / ".cache/agent-hooks/debug.log"))


def parse(line: str):
    parts = line.split()
    if len(parts) < 6 or not parts[3].startswith("exit=") or not parts[4].endswith("ms"):
        return None
    return {
        "time": parts[0],
        "runtime": parts[1],
        "event": parts[2],
        "code": int(parts[3][5:]),
        "ms": int(parts[4][:-2]),
        "hook": " ".join(parts[5:]),
    }


def fmt(r) -> str:
    status = {0: "ok", 2: "BLOCK"}.get(r["code"], f"ERR {r['code']}")
    return f"{r['time']}  {r['runtime']:<6} {r['event']:<18} {status:<7} {r['ms']:>6}ms  {r['hook']}"


def keep(r, args) -> bool:
    if args.errors and r["code"] in (0, 2):
        return False
    return not (args.slow is not None and r["ms"] < args.slow)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--errors", action="store_true")
    p.add_argument("--slow", type=int, metavar="MS")
    p.add_argument("--summary", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--clear", action="store_true")
    p.add_argument("-n", type=int, default=40, help="runs to show (default 40)")
    args = p.parse_args()

    if args.clear:
        LOG.write_text("")
        print(f"cleared {LOG}")
        return
    if not LOG.exists():
        print(f"no log at {LOG}: wrap a hook command with debug-wrap.sh first")
        return

    runs = [r for r in map(parse, LOG.read_text().splitlines()) if r]

    if args.summary:
        by_hook = defaultdict(list)
        for r in runs:
            by_hook[(r["runtime"], r["event"], r["hook"])].append(r)
        print(f"{'runtime':<7} {'event':<18} {'runs':>5} {'block':>5} {'err':>4} {'p50ms':>6} {'maxms':>6}  hook")
        for (rt, ev, hook), rs in sorted(by_hook.items()):
            ms = [r["ms"] for r in rs]
            blocks = sum(r["code"] == 2 for r in rs)
            errs = sum(r["code"] not in (0, 2) for r in rs)
            print(f"{rt:<7} {ev:<18} {len(rs):>5} {blocks:>5} {errs:>4} {statistics.median(ms):>6.0f} {max(ms):>6}  {hook}")
        return

    for r in [r for r in runs if keep(r, args)][-args.n:]:
        print(fmt(r))

    if args.watch:
        with LOG.open() as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.3)
                    continue
                r = parse(line)
                if r and keep(r, args):
                    print(fmt(r), flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
