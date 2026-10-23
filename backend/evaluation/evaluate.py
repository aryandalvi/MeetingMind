"""Evaluate MeetingMind against the manually labelled transcripts in labels.json.

Usage (from backend/):
    python -m evaluation.evaluate                 # extractive summaries (fast; extraction is unaffected)
    python -m evaluation.evaluate --split test    # only the held-out split

Reports precision / recall / F1 per category (items matched by evidence sentence), plus owner,
deadline, decision-status and risk-kind accuracy over matched items. A naive keyword baseline
is evaluated with the same matching for comparison. Results are written to RESULTS.md / results.json.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.config import get_settings  # noqa: E402
from app.nlp.models import ModelRegistry  # noqa: E402
from app.nlp.pipeline import analyze  # noqa: E402
from app.nlp.preprocessing import parse_transcript  # noqa: E402
from app.schemas import AnalyzeRequest  # noqa: E402

CATEGORIES = ["actions", "decisions", "risks", "questions"]


def _match(gold: list[dict], predicted: list[tuple[list[str], dict]]):
    """Greedy one-to-one matching: a prediction matches a gold item if one of its evidence
    sentences contains one of the gold evidence substrings."""
    used: set[int] = set()
    pairs = []
    for g in gold:
        alts = [a.lower() for a in g["evidence"]]
        for i, (texts, attrs) in enumerate(predicted):
            if i in used:
                continue
            if any(alt in t.lower() for t in texts for alt in alts):
                used.add(i)
                pairs.append((g, attrs))
                break
    return pairs


def _deadline_ok(gold, predicted) -> bool:
    return predicted in gold if isinstance(gold, list) else gold == predicted


def _prf(tp: int, n_pred: int, n_gold: int) -> dict:
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "predicted": n_pred, "gold": n_gold, "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


def system_predictions(report) -> dict:
    return {
        "actions": [([e.text for e in a.evidence], {"owner": a.owner, "deadline": a.deadline.normalized_date.isoformat() if a.deadline and a.deadline.normalized_date else None}) for a in report.action_items],
        "decisions": [([e.text for e in d.evidence], {"status": d.status}) for d in report.decisions],
        "risks": [([e.text for e in r.evidence], {"kind": r.kind}) for r in report.risks],
        "questions": [([e.text for e in q.evidence], {}) for q in report.questions],
    }


BASE_ACTION = re.compile(r"(?i)\b(will|'ll|need to|needs to|should|can you|could you|please|going to|let me|action)\b")
BASE_DECISION = re.compile(r"(?i)\b(decided|agreed|decision|approved|go with|won't|will not)\b")
BASE_RISK = re.compile(r"(?i)\b(risk|blocked|blocker|worried|concern|problem|issue|delay|waiting)\b")


def baseline_predictions(text: str, nlp) -> dict:
    """Naive keyword baseline: one item per sentence containing a cue word; owner = speaker."""
    t = parse_transcript(text, nlp)
    out = {k: [] for k in CATEGORIES}
    for s in t.sentences:
        if BASE_ACTION.search(s.text):
            out["actions"].append(([s.text], {"owner": s.speaker or "Unassigned", "deadline": None}))
        if BASE_DECISION.search(s.text):
            out["decisions"].append(([s.text], {"status": "confirmed"}))
        if BASE_RISK.search(s.text):
            out["risks"].append(([s.text], {"kind": "blocker" if "block" in s.text.lower() else "risk"}))
        if s.text.strip().endswith("?"):
            out["questions"].append(([s.text], {}))
    return out


def score(items: list[tuple[dict, dict]]) -> dict:
    totals = {c: {"tp": 0, "pred": 0, "gold": 0} for c in CATEGORIES}
    attr = {"owner": [0, 0], "deadline": [0, 0], "status": [0, 0], "kind": [0, 0]}
    for gold, pred in items:
        for c in CATEGORIES:
            pairs = _match(gold.get(c, []), pred[c])
            totals[c]["tp"] += len(pairs)
            totals[c]["pred"] += len(pred[c])
            totals[c]["gold"] += len(gold.get(c, []))
            for g, p in pairs:
                if c == "actions":
                    attr["owner"][0] += g["owner"].lower() == p["owner"].lower()
                    attr["owner"][1] += 1
                    attr["deadline"][0] += _deadline_ok(g["deadline"], p["deadline"])
                    attr["deadline"][1] += 1
                if c == "decisions":
                    attr["status"][0] += g["status"] == p["status"]
                    attr["status"][1] += 1
                if c == "risks":
                    attr["kind"][0] += g["kind"] == p["kind"]
                    attr["kind"][1] += 1
    result = {c: _prf(v["tp"], v["pred"], v["gold"]) for c, v in totals.items()}
    tp = sum(v["tp"] for v in totals.values())
    result["micro"] = _prf(tp, sum(v["pred"] for v in totals.values()), sum(v["gold"] for v in totals.values()))
    result["attributes"] = {k: {"correct": a, "of": n, "accuracy": round(a / n, 3) if n else None} for k, (a, n) in attr.items()}
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test", "holdout2", "all"], default="all")
    ap.add_argument("--details", action="store_true", help="print unmatched gold items and false positives")
    args = ap.parse_args()

    labels = json.loads((HERE / "labels.json").read_text(encoding="utf-8"))["transcripts"]
    registry = ModelRegistry(dataclasses.replace(get_settings(), summary_mode="extractive"))
    nlp = registry.get("spacy")
    by_split: dict[str, dict[str, list]] = {}
    for entry in labels:
        if args.split != "all" and entry["split"] != args.split:
            continue
        text = (HERE / entry["file"]).read_text(encoding="utf-8")
        report = analyze(
            AnalyzeRequest(transcript=text, meeting_date=date.fromisoformat(entry["meeting_date"])), registry=registry
        )
        sys_pred = system_predictions(report)
        if args.details:
            for c in CATEGORIES:
                pairs = _match(entry.get(c, []), sys_pred[c])
                matched_gold = [id(g) for g, _ in pairs]
                for g in entry.get(c, []):
                    if id(g) not in matched_gold:
                        print(f"[{entry['id']}] MISSED {c}: {g['evidence'][0]}")
                for g, p in pairs:
                    if c == "actions" and (g["owner"].lower() != p["owner"].lower() or not _deadline_ok(g["deadline"], p["deadline"])):
                        print(f"[{entry['id']}] ATTR action '{g['evidence'][0]}': gold {g['owner']}/{g['deadline']} vs {p['owner']}/{p['deadline']}")
                    if c == "decisions" and g["status"] != p["status"]:
                        print(f"[{entry['id']}] ATTR decision '{g['evidence'][0]}': gold {g['status']} vs {p['status']}")
                gold_alts = [a.lower() for g in entry.get(c, []) for a in g["evidence"]]
                for texts, _ in sys_pred[c]:
                    if not any(a in t.lower() for t in texts for a in gold_alts):
                        print(f"[{entry['id']}] FALSE POSITIVE {c}: {texts[0][:100]}")
        bucket = by_split.setdefault(entry["split"], {"system": [], "baseline": []})
        bucket["system"].append((entry, sys_pred))
        bucket["baseline"].append((entry, baseline_predictions(text, nlp)))

    results = {}
    for split, data in by_split.items():
        results[split] = {
            "transcripts": len(data["system"]),
            "system": score(data["system"]),
            "baseline": score(data["baseline"]),
        }
    (HERE / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    md = ["# MeetingMind evaluation results", "",
          "Generated by `python -m evaluation.evaluate`. Items are matched to gold labels by evidence sentence.",
          "The baseline flags every sentence containing a cue word (e.g. 'will', 'decided', 'risk', '?').", ""]
    titles = {
        "dev": "Dev split (used for rule development)",
        "test": "Test split (post-hoc: changed after error analysis; the frozen held-out run is in RESULTS_heldout_v1.md)",
        "holdout2": "Holdout-2 split (written after all changes, evaluated once)",
    }
    for split in ("dev", "test", "holdout2"):
        if split not in results:
            continue
        r = results[split]
        md += [f"## {titles[split]} — {r['transcripts']} transcripts", "",
               "| Category | System P | System R | System F1 | Baseline P | Baseline R | Baseline F1 | Gold items |",
               "|---|---|---|---|---|---|---|---|"]
        for c in CATEGORIES + ["micro"]:
            s, b = r["system"][c], r["baseline"][c]
            md.append(f"| {c} | {s['precision']:.2f} | {s['recall']:.2f} | {s['f1']:.2f} | {b['precision']:.2f} | {b['recall']:.2f} | {b['f1']:.2f} | {s['gold']} |")
        md += ["", "| Attribute (on matched items) | System | Baseline |", "|---|---|---|"]
        for k, v in r["system"]["attributes"].items():
            bv = r["baseline"]["attributes"][k]
            fmt = lambda x: f"{x['accuracy']:.2f} ({x['correct']}/{x['of']})" if x["of"] else "—"
            md.append(f"| {k} accuracy | {fmt(v)} | {fmt(bv)} |")
        md.append("")
    (HERE / "RESULTS.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
