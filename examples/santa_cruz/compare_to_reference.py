"""Compare a pipeline run with the reference tables shipped in the Santa Cruz data package.

    python examples/santa_cruz/compare_to_reference.py --reference <data>/reference_results --output outputs

Every CSV under --reference is matched to the same relative path under --output. Rows are aligned on the
text columns; numeric columns must agree to --rtol. The reference CBA tables use the 'legacy' cost rule,
so run the pipeline with --cost-base legacy for a full match.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def compare(ref: pd.DataFrame, out: pd.DataFrame, rtol: float) -> str | None:
    missing = sorted(set(ref.columns) - set(out.columns))
    if missing:  # extra output columns (e.g. 'placed' from the fixed S030) are ignored
        return f"missing columns {missing}"
    if len(ref) != len(out):
        return f"rows {len(out)} vs reference {len(ref)}"
    out = out[ref.columns]
    num = [c for c in ref.columns if pd.api.types.is_numeric_dtype(ref[c])]
    txt = [c for c in ref.columns if c not in num]
    if txt:
        ref = ref.sort_values(txt, kind="mergesort").reset_index(drop=True)
        out = out.sort_values(txt, kind="mergesort").reset_index(drop=True)
        if not ref[txt].fillna("").astype(str).equals(out[txt].fillna("").astype(str)):
            return "text columns differ"
    worst = 0.0
    for c in num:
        a, b = ref[c].to_numpy(float), pd.to_numeric(out[c], errors="coerce").to_numpy(float)
        if not np.array_equal(np.isnan(a), np.isnan(b)):
            return f"{c}: NaN pattern differs"
        m = ~np.isnan(a)
        if m.any():
            d = np.abs(a[m] - b[m]) / np.maximum(np.abs(a[m]), 1.0)
            worst = max(worst, d.max())
    return None if worst <= rtol else f"max rel. difference {worst:.2e}"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--reference", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--rtol", type=float, default=1e-6)
    a = p.parse_args(argv)
    n_ok = n_bad = 0
    for ref_file in sorted(a.reference.rglob("*.csv")):
        rel = ref_file.relative_to(a.reference)
        out_file = a.output / rel
        if not out_file.exists():  # S030 adds the cost rule to the name unless it is all_placed
            alt = [f for f in out_file.parent.glob("*.csv") if f.name.replace("_legacy", "") == out_file.name]
            out_file = alt[0] if alt else out_file
        if not out_file.exists():
            print(f"MISSING  {rel}")
            n_bad += 1
            continue
        msg = compare(pd.read_csv(ref_file), pd.read_csv(out_file), a.rtol)
        print(f"{'OK      ' if msg is None else 'DIFF    '} {rel}" + ("" if msg is None else f"  ({msg})"))
        n_ok += msg is None
        n_bad += msg is not None
    print(f"\n{n_ok} tables match, {n_bad} differ or are missing")
    sys.exit(1 if n_bad else 0)


if __name__ == "__main__":
    main()
