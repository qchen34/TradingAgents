#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from futu import OpenQuoteContext, RET_OK, UserSecurityGroupType


def fetch_full_watchlist(host: str, port: int) -> pd.DataFrame:
    quote_ctx = OpenQuoteContext(host=host, port=port)
    try:
        ret, groups = quote_ctx.get_user_security_group(group_type=UserSecurityGroupType.ALL)
        if ret != RET_OK:
            raise RuntimeError(f"get_user_security_group failed: {groups}")

        all_frames: list[pd.DataFrame] = []
        for _, g in groups.iterrows():
            group_name = str(g.get("group_name", "")).strip()
            if not group_name:
                continue
            ret2, sec = quote_ctx.get_user_security(group_name)
            if ret2 != RET_OK:
                print(f"[WARN] get_user_security failed for group={group_name}: {sec}")
                continue
            if sec is None or sec.empty:
                continue
            sec = sec.copy()
            sec["group_name"] = group_name
            all_frames.append(sec)

        if not all_frames:
            return pd.DataFrame(columns=["group_name", "code", "name"])

        out = pd.concat(all_frames, ignore_index=True)
        out = out.drop_duplicates(subset=["group_name", "code"], keep="first")
        first_cols = ["group_name", "code", "name"]
        ordered_cols = [c for c in first_cols if c in out.columns] + [c for c in out.columns if c not in first_cols]
        return out[ordered_cols]
    finally:
        quote_ctx.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export all Futu watchlist groups to CSV/JSON.")
    parser.add_argument("--host", default="127.0.0.1", help="OpenD host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=11111, help="OpenD port (default: 11111)")
    parser.add_argument("--csv", default="", help="Output CSV path")
    parser.add_argument("--json", default="", help="Output JSON path")
    args = parser.parse_args()

    output_dir = Path(__file__).resolve().parent
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = Path(args.csv) if args.csv else output_dir / f"futu_watchlist_full_{ts}.csv"
    json_path = Path(args.json) if args.json else output_dir / f"futu_watchlist_full_{ts}.json"

    df = fetch_full_watchlist(host=args.host, port=args.port)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    records = json.loads(df.to_json(orient="records", force_ascii=False))
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Exported rows: {len(df)}")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()

