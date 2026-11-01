#!/usr/bin/env python3
"""Reproduce the actual unpublished unit defect and independent mutation probes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASE = "264-backend-units"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def replay(write=False):
    fixture = ROOT / "tests/fixtures/264-backend"
    provenance = json.loads((fixture / "provenance.json").read_text())
    for variant, record in provenance.items():
        source = fixture / variant / record["file"]
        require(hashlib.sha256(source.read_bytes()).hexdigest() == record["sha256"],
                variant + " source changed")
    force = "f_mass = s['masses'][:, None]*(g_B - a_i)"
    couple = "c_mass = -np.einsum('kij,j->ki', s['inertias'], alpha) - np.cross(omega, np.einsum('kij,j->ki', s['inertias'], omega))"
    changes = {
        "force-unit": (force, force + " / 12.0"),
        "couple-unit": (couple, couple.replace("c_mass = ", "c_mass = (") + ") / 144.0"),
        "reaction-sign": ("force, moment = -total_f, -total_m", "force, moment = total_f, total_m"),
        "alternative": (force, "f_mass = np.multiply(s['masses'][:, None], np.subtract(g_B, a_i))"),
    }
    with tempfile.TemporaryDirectory(prefix="oracle-unit-replay-") as temporary:
        workspaces = {name: fixture / name for name in ("raw", "fix")}
        for name, (old, new) in changes.items():
            target = Path(temporary) / name
            shutil.copytree(fixture / "fix", target)
            source = target / "station_loads.py"
            text = source.read_text()
            require(text.count(old) == 1, name + " mutation target changed")
            source.write_text(text.replace(old, new))
            workspaces[name] = target
        checks = []
        for name, workspace in workspaces.items():
            expected = name in {"fix", "alternative"}
            for _ in range(3):
                result = subprocess.run(
                    [sys.executable, "-O", str(ROOT / "cases" / CASE / "oracle/check.py"), str(workspace)],
                    capture_output=True, text=True, timeout=15)
                data = json.loads(result.stdout)
                require(result.returncode == (0 if expected else 1)
                        and data.get("ok") is expected and not data.get("error"),
                        name + ": " + result.stdout + result.stderr)
            checks.append({"variant": name, "outcome": "pass" if expected else "fail",
                           "repetitions": 3})
        command = [sys.executable, str(ROOT / "tools/oracle"), "validate", CASE,
                   "--raw", str(workspaces["raw"]), "--fix", str(workspaces["fix"])]
        for name in changes:
            if name != "alternative":
                command += ["--mutant", name + "=" + str(workspaces[name])]
        if write:
            command.append("--write")
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        require(result.returncode == 0, result.stdout + result.stderr)
        if write:
            path = ROOT / "cases" / CASE / "validation/report.json"
            report = json.loads(path.read_text())
            report["replay_evidence"] = {
                "variants": checks, "python_optimization": True,
                "provenance_sha256": hashlib.sha256((fixture / "provenance.json").read_bytes()).hexdigest(),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "scope": "Focused units regression; tuning; no whole-model physical validation",
            }
            path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"case": CASE, "variants": checks}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    replay(parser.parse_args().write)
