# backend/importers/cli.py
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Type

from pydantic import BaseModel, ValidationError

# Import canonical contracts
from backend.contracts.models import (
    Segment, Event, CodebookItem, EventLabel, ReviewDecision
)

KIND_TO_MODEL: Dict[str, Type[BaseModel]] = {
    "segment": Segment,
    "event": Event,
    "codebook": CodebookItem,
    "label": EventLabel,
    "review": ReviewDecision,
}

def iter_csv(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}

def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def load_rows(path: Path) -> Iterable[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return iter_csv(path)
    elif suffix in (".jsonl", ".ndjson"):
        return iter_jsonl(path)
    elif suffix == ".json":
        # JSON array of objects
        return json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"Unsupported file type: {path}")

def validate_rows(kind: str, rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    Model = KIND_TO_MODEL[kind]
    ok, bad = 0, 0
    errors: List[Dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        try:
            Model.model_validate(row)  # pydantic v2
            ok += 1
        except ValidationError as ve:
            bad += 1
            errors.append({"row": i, "errors": json.loads(ve.json())})
    return {"ok": ok, "bad": bad, "errors": errors}

def cmd_dry_run(args: argparse.Namespace) -> int:
    kind = args.kind
    files = [Path(p) for p in args.files]
    grand = {"ok": 0, "bad": 0, "errors": []}
    for fp in files:
        print(f"Validating {fp} as {kind}...")
        rows = load_rows(fp)
        report = validate_rows(kind, rows)
        print(f"  OK: {report['ok']}  BAD: {report['bad']}")
        if report["errors"]:
            print("  Sample errors:")
            for e in report["errors"][:3]:
                print("   - row", e["row"], "->", e["errors"])
        grand["ok"] += report["ok"]
        grand["bad"] += report["bad"]
        grand["errors"].extend([{"file": str(fp), **e} for e in report["errors"]])
    print("\n=== SUMMARY ===")
    print(json.dumps(grand, ensure_ascii=False, indent=2))
    return 0 if grand["bad"] == 0 else 2

def cmd_import(args: argparse.Namespace) -> int:
    # Phase 0.5: we only validate, then (optionally) write normalized JSONL to ./backend/fixtures/
    out_dir = Path(args.out or "backend/fixtures/imported")
    out_dir.mkdir(parents=True, exist_ok=True)
    kind = args.kind
    Model = KIND_TO_MODEL[kind]
    counter = 0
    for fp in [Path(p) for p in args.files]:
        print(f"Importing {fp} as {kind} (normalize -> JSONL)...")
        rows = load_rows(fp)
        out_path = out_dir / f"{fp.stem}.{kind}.jsonl"
        with out_path.open("w", encoding="utf-8") as w:
            for row in rows:
                try:
                    obj = Model.model_validate(row)
                    w.write(obj.model_dump_json(ensure_ascii=False) + "\n")
                    counter += 1
                except ValidationError as ve:
                    print(f"  Skipping invalid row in {fp}: {ve}")
    print(f"Wrote {counter} normalized records to {out_dir}")
    return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="qa-import", description="QualiAgent Importer CLI (Phase 0.5)")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--kind", required=True, choices=list(KIND_TO_MODEL.keys()), help="Type of records in files")
    common.add_argument("files", nargs="+", help="Input files (csv/json/jsonl)")

    p_dry = sub.add_parser("dry-run", parents=[common], help="Validate files against contracts")
    p_dry.set_defaults(func=cmd_dry_run)

    p_imp = sub.add_parser("import", parents=[common], help="Normalize and write JSONL (no DB write in Phase 0.5)")
    p_imp.add_argument("--out", help="Output directory for normalized JSONL")
    p_imp.set_defaults(func=cmd_import)

    return p

def main():
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
