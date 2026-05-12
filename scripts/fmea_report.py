#!/usr/bin/env python3
"""Print the FMEA register with computed RPNs and highlight open high-risk modes.

Usage: python scripts/fmea_report.py [--threshold 100]
"""

import argparse
import sys
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="TQM FMEA report")
    parser.add_argument("--threshold", type=int, default=100, help="RPN threshold for high-risk")
    args = parser.parse_args()

    fmea_path = Path(__file__).parent.parent / "config" / "fmea.yaml"
    data = yaml.safe_load(fmea_path.read_text(encoding="utf-8"))

    modes = data["failure_modes"]
    print(f"\n{'='*72}")
    print(f"  TQM FMEA Register  (threshold RPN > {args.threshold})")
    print(f"{'='*72}\n")
    print(f"{'ID':<8} {'S':>3} {'O':>3} {'D':>3} {'RPN':>5}  {'Open':>5}  Name")
    print("-" * 72)

    high_open: list[dict] = []
    for mode in modes:
        s, o = mode["S"], mode["O"]
        # Use residual D if controls are in place, else raw D
        d_raw = mode["D"]
        d_residual = mode.get("residual_D", d_raw)
        rpn_raw = s * o * d_raw
        rpn_residual = s * o * d_residual
        open_flag = mode.get("open", False)

        row_flag = "🔴" if (open_flag and rpn_residual > args.threshold) else (
            "🟡" if open_flag else "✅"
        )
        print(
            f"{mode['id']:<8} {s:>3} {o:>3} {d_residual:>3} {rpn_residual:>5}  "
            f"{str(open_flag):>5}  {row_flag} {mode['name'][:50]}"
        )
        if open_flag and rpn_residual > args.threshold:
            high_open.append(mode)

    print(f"\n{'='*72}")
    if high_open:
        print(f"\n🔴  {len(high_open)} HIGH-RISK OPEN FAILURE MODE(S) (RPN > {args.threshold}):\n")
        for mode in high_open:
            s, o = mode["S"], mode["O"]
            d = mode.get("residual_D", mode["D"])
            rpn = s * o * d
            print(f"  [{mode['id']}] RPN={rpn}  {mode['name']}")
            if mode.get("action"):
                print(f"       Action: {mode['action'].strip()[:120]}")
            print()
        print("  Pipeline must not run automated delivery until these are mitigated.")
        sys.exit(1)
    else:
        print("\n✅  All high-risk failure modes are controlled or closed.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
