"""A stand-in for an analysis: it writes the numbers its flags name, so a test decides every result.

    python3 fit.py --auc 0.58 [--positive-rate 0.07] [--seed 7] [--model logistic]
    python3 fit.py --raw '{"auc": {"mean": 0.58}}'    writes that text as the metrics file
    python3 fit.py --auc 0.58 --exit 3                 writes the metrics, then exits 3
"""

import argparse
import json
import sys
from pathlib import Path

WEIGHTS = None

parser = argparse.ArgumentParser()
parser.add_argument("--auc", type=float)
parser.add_argument("--positive-rate", type=float)
parser.add_argument("--seed", default="0")
parser.add_argument("--model", default="logistic")
parser.add_argument("--raw")
parser.add_argument("--exit", type=int, default=0)
args = parser.parse_args()

out = Path("out")
out.mkdir(exist_ok=True)
if args.raw is not None:
    (out / "metrics.json").write_text(args.raw)
elif args.auc is not None:
    metrics = {"auc": args.auc} | ({"positive_rate": args.positive_rate} if args.positive_rate is not None else {})
    (out / "metrics.json").write_text(json.dumps(metrics, sort_keys=True))
print(f"model {args.model}, seed {args.seed}, weights {WEIGHTS}")
sys.exit(args.exit)
