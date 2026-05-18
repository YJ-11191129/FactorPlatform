from __future__ import annotations

import argparse
import json

from app.services.similar_period_engine import (
    SimilarPeriodParams,
    persist_similar_outputs,
    run_similar_period_lookup,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, help="Path to regime_snapshot_daily.parquet")
    parser.add_argument("--out-dir", default="D:/FactorPlatform/data/exports/regime_engine", help="Output directory")
    parser.add_argument("--eps", type=float, default=1.5)
    parser.add_argument("--min-samples", type=int, default=10)
    parser.add_argument("--topk", type=int, default=20)
    parser.add_argument("--lookback-exclude", type=int, default=40)
    parser.add_argument("--sequence-window", type=int, default=5)
    parser.add_argument("--pca-dim", type=int, default=6)
    args = parser.parse_args()

    params = SimilarPeriodParams(
        eps=args.eps,
        min_samples=args.min_samples,
        topk=args.topk,
        lookback_exclude=args.lookback_exclude,
        sequence_window=args.sequence_window,
        pca_dim=args.pca_dim,
    )
    lookup, profile = run_similar_period_lookup(args.snapshot, params)
    paths = persist_similar_outputs(lookup, profile, args.out_dir)
    print(
        json.dumps(
            {
                "ok": True,
                "rows_lookup": int(len(lookup)),
                "rows_profile": int(len(profile)),
                "current": profile.iloc[0].to_dict() if not profile.empty else {},
                "paths": paths,
            },
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()

