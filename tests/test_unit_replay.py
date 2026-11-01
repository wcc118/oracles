"""Admission replay exercises production source, not a copied implementation."""
import json
from pathlib import Path
import subprocess
import sys


def test_historical_unit_failure_and_valid_alternative():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-O", str(root / "tools/replay-units.py")],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    variants = {item["variant"]: item for item in json.loads(result.stdout)["variants"]}
    assert variants["raw"]["outcome"] == "fail"
    assert variants["fix"]["outcome"] == variants["alternative"]["outcome"] == "pass"
    assert all(variants[name]["outcome"] == "fail"
               for name in ("force-unit", "couple-unit", "reaction-sign"))
    assert all(item["repetitions"] == 3 for item in variants.values())
