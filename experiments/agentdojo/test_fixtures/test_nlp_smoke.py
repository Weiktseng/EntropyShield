#!/usr/bin/env python3
"""Smoke test: Mode NLP on attack fixtures."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import yaml
from entropyshield_defense_nlp import nlp_analyze, build_title, extract_freetext

# Load fixtures
with open(os.path.join(os.path.dirname(__file__), "attack_tool_outputs.yaml")) as f:
    attacks = yaml.safe_load(f)

with open(os.path.join(os.path.dirname(__file__), "normal_tool_outputs.yaml")) as f:
    normals = yaml.safe_load(f)

print("=" * 60)
print("MODE NLP SMOKE TEST")
print("=" * 60)

# Test attacks
print("\n── ATTACK OUTPUTS ──")
attack_detected = 0
attack_total = 0
for key, val in attacks.items():
    if key.startswith("_") or not isinstance(val, dict):
        continue
    attack_total += 1
    text = val["tool_output"]
    analysis = nlp_analyze(text)
    title = build_title(analysis)
    detected = len(analysis["findings"]) > 0
    if detected:
        attack_detected += 1
    status = "DETECTED" if detected else "MISSED"
    print(f"\n  [{status}] {key}")
    print(f"    Score: {analysis['score']:.2f}, Findings: {len(analysis['findings'])}")
    for f in analysis["findings"]:
        if f["type"] == "meta_marker":
            print(f"      - {f['type']}: {f['marker']}")
        elif f["type"] == "imperative":
            print(f"      - {f['type']}: verb={f['verb']}")
        elif f["type"] == "command_structure":
            print(f"      - {f['type']}: {f['verb']}({f['object']}→{f['targets']})")
        elif f["type"] == "entity_in_command":
            print(f"      - {f['type']}: {f['entity_type']}={f['entity']}")
        elif f["type"] == "style_anomaly":
            print(f"      - {f['type']}: pos={f['position']}")
        elif f["type"] == "exclamation_anomaly":
            print(f"      - {f['type']}: count={f['count']}")

print(f"\n  Attack detection: {attack_detected}/{attack_total}")

# Test normals
print("\n── NORMAL OUTPUTS ──")
normal_fp = 0
normal_total = 0
for key, val in normals.items():
    if key.startswith("_") or not isinstance(val, dict):
        continue
    normal_total += 1
    text = val["tool_output"]
    analysis = nlp_analyze(text)
    flagged = len(analysis["findings"]) > 0
    if flagged:
        normal_fp += 1
    status = "FALSE POS" if flagged else "CLEAN"
    print(f"\n  [{status}] {key}")
    print(f"    Score: {analysis['score']:.2f}, Findings: {len(analysis['findings'])}")
    for f in analysis["findings"]:
        ftype = f["type"]
        if ftype == "imperative":
            print(f"      - {ftype}: verb={f['verb']}, sent={f['sentence'][:60]}")
        elif ftype == "command_structure":
            print(f"      - {ftype}: {f['verb']}({f['object']}→{f['targets']})")
        elif ftype == "meta_marker":
            print(f"      - {ftype}: {f['marker']}")
        else:
            print(f"      - {ftype}")

print(f"\n  False positives: {normal_fp}/{normal_total}")

print(f"\n{'='*60}")
print(f"SUMMARY: Attacks detected {attack_detected}/{attack_total}, FP {normal_fp}/{normal_total}")
print(f"{'='*60}")
