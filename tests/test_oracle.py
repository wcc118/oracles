"""Tests for the oracle CLI tool."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
CASES_DIR = ROOT_DIR / "cases"
SCHEMA_FILE = ROOT_DIR / "schema" / "case.schema.json"
ORACLE_SCRIPT = ROOT_DIR / "tools" / "oracle"
FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures"


def run_oracle(*args, check=False):
    """Run the oracle script and return result."""
    cmd = [sys.executable, str(ORACLE_SCRIPT)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=ROOT_DIR)
    if check and result.returncode != 0:
        pytest.fail(f"Command failed: {cmd}\nstdout: {result.stdout}\nstderr: {result.stderr}")
    return result


def hash_file(path):
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def _tmp_repo(tmp_path):
    """A throwaway copy of the tool layout, so fake cases never touch the real cases/ directory."""
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    shutil.copy2(ORACLE_SCRIPT, repo / "tools" / "oracle")
    (repo / "schema").mkdir()
    shutil.copy2(SCHEMA_FILE, repo / "schema" / "case.schema.json")
    (repo / "cases").mkdir()
    return repo


def _marker_case(repo, case_id="marker-case"):
    """Python-runtime case whose check passes if and only if the workspace contains a file named PASS."""
    case = repo / "cases" / case_id
    (case / "oracle").mkdir(parents=True)
    check = case / "oracle" / "check.py"
    check.write_text(
        "import json, os, sys\n"
        "ok = os.path.exists(os.path.join(sys.argv[1], 'PASS'))\n"
        "print(json.dumps({'ok': ok}))\n"
        "sys.exit(0 if ok else 1)\n"
    )
    task = case / "task.md"
    task.write_text("# marker case\n")
    manifest = {
        "id": case_id, "task_class": "test", "runtime": "python",
        "strength": "invariant-or-residual", "status": "probation", "suite": "tuning",
        "hashes": {"input": "x", "task": hash_file(task), "check": hash_file(check)},
        "origin": {"issue": "test"},
    }
    (case / "manifest.json").write_text(json.dumps(manifest))
    return case_id


def _workspace(tmp_path, name, passes):
    d = tmp_path / name
    d.mkdir()
    (d / ("PASS" if passes else "FAIL")).write_text("x")
    return d


def _run_tmp(repo, *args):
    return subprocess.run([sys.executable, str(repo / "tools" / "oracle"), *args],
                          capture_output=True, text=True, timeout=60, cwd=repo)


class TestManifestLoading:
    """Tests for manifest loading and validation."""

    def test_list_all_cases(self):
        """Test listing all cases."""
        result = run_oracle("list")
        assert result.returncode == 0
        assert "264-root-reaction-sign" in result.stdout
        assert "267-playback-clock" in result.stdout

    def test_list_by_suite(self):
        """Test filtering by suite."""
        result = run_oracle("list", "--suite", "tuning")
        assert result.returncode == 0
        assert "264-root-reaction-sign" in result.stdout
        assert "267-playback-clock" in result.stdout

        result = run_oracle("list", "--suite", "heldout")
        assert result.returncode == 0
        # No heldout cases exist
        assert "264-root-reaction-sign" not in result.stdout

    def test_list_by_status(self):
        """Test filtering by status."""
        result = run_oracle("list", "--status", "probation")
        assert result.returncode == 0
        assert "264-root-reaction-sign" in result.stdout

        result = run_oracle("list", "--status", "active")
        assert result.returncode == 0
        # No active cases exist
        assert "264-root-reaction-sign" not in result.stdout


class TestManifestValidation:
    """Tests for manifest validation without jsonschema."""

    def test_list_with_invalid_enum_strength(self, tmp_path):
        """Test list rejects invalid enum on strength without jsonschema."""
        case_dir = tmp_path / "invalid-strength"
        case_dir.mkdir()
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.mjs"
        check_file.write_text("console.log(JSON.stringify({ok:true}));")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "invalid-strength",
            "task_class": "test",
            "runtime": "node-vm",
            "strength": "totally-bogus",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "test",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "invalid-strength"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            # Run with jsonschema blocked
            import subprocess
            nojs_dir = tmp_path / "nojs"
            nojs_dir.mkdir()
            (nojs_dir / "jsonschema.py").write_text('raise ImportError("blocked")\n')

            result = subprocess.run(
                [sys.executable, str(ORACLE_SCRIPT), "list"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(ROOT_DIR),
                env={**os.environ, "PYTHONPATH": str(nojs_dir)}
            )
            assert result.returncode == 0
            assert "invalid-strength" not in result.stdout
            assert "invalid enum value 'totally-bogus' for field 'strength'" in result.stderr
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_list_with_invalid_enum_runtime(self, tmp_path):
        """Test list rejects invalid enum on runtime without jsonschema."""
        case_dir = tmp_path / "invalid-runtime"
        case_dir.mkdir()
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.mjs"
        check_file.write_text("console.log(JSON.stringify({ok:true}));")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "invalid-runtime",
            "task_class": "test",
            "runtime": "totally-bogus",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "test",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "invalid-runtime"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            import subprocess
            nojs_dir = tmp_path / "nojs"
            nojs_dir.mkdir()
            (nojs_dir / "jsonschema.py").write_text('raise ImportError("blocked")\n')

            result = subprocess.run(
                [sys.executable, str(ORACLE_SCRIPT), "list"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(ROOT_DIR),
                env={**os.environ, "PYTHONPATH": str(nojs_dir)}
            )
            assert result.returncode == 0
            assert "invalid-runtime" not in result.stdout
            assert "invalid enum value 'totally-bogus' for field 'runtime'" in result.stderr
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_list_with_invalid_enum_status(self, tmp_path):
        """Test list rejects invalid enum on status without jsonschema."""
        case_dir = tmp_path / "invalid-status"
        case_dir.mkdir()
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.mjs"
        check_file.write_text("console.log(JSON.stringify({ok:true}));")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "invalid-status",
            "task_class": "test",
            "runtime": "node-vm",
            "strength": "invariant-or-residual",
            "status": "totally-bogus",
            "suite": "tuning",
            "hashes": {
                "input": "test",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "invalid-status"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            import subprocess
            nojs_dir = tmp_path / "nojs"
            nojs_dir.mkdir()
            (nojs_dir / "jsonschema.py").write_text('raise ImportError("blocked")\n')

            result = subprocess.run(
                [sys.executable, str(ORACLE_SCRIPT), "list"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(ROOT_DIR),
                env={**os.environ, "PYTHONPATH": str(nojs_dir)}
            )
            assert result.returncode == 0
            assert "invalid-status" not in result.stdout
            assert "invalid enum value 'totally-bogus' for field 'status'" in result.stderr
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_list_with_invalid_enum_suite(self, tmp_path):
        """Test list rejects invalid enum on suite without jsonschema."""
        case_dir = tmp_path / "invalid-suite"
        case_dir.mkdir()
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.mjs"
        check_file.write_text("console.log(JSON.stringify({ok:true}));")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "invalid-suite",
            "task_class": "test",
            "runtime": "node-vm",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "totally-bogus",
            "hashes": {
                "input": "test",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "invalid-suite"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            import subprocess
            nojs_dir = tmp_path / "nojs"
            nojs_dir.mkdir()
            (nojs_dir / "jsonschema.py").write_text('raise ImportError("blocked")\n')

            result = subprocess.run(
                [sys.executable, str(ORACLE_SCRIPT), "list"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(ROOT_DIR),
                env={**os.environ, "PYTHONPATH": str(nojs_dir)}
            )
            assert result.returncode == 0
            assert "invalid-suite" not in result.stdout
            assert "invalid enum value 'totally-bogus' for field 'suite'" in result.stderr
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_list_with_wrong_type_hashes(self, tmp_path):
        """Test list rejects wrong type for hashes (string instead of object)."""
        case_dir = tmp_path / "wrong-type-hashes"
        case_dir.mkdir()
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.mjs"
        check_file.write_text("console.log(JSON.stringify({ok:true}));")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "wrong-type-hashes",
            "task_class": "test",
            "runtime": "node-vm",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": "totally-bogus-string",
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "wrong-type-hashes"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            import subprocess
            nojs_dir = tmp_path / "nojs"
            nojs_dir.mkdir()
            (nojs_dir / "jsonschema.py").write_text('raise ImportError("blocked")\n')

            result = subprocess.run(
                [sys.executable, str(ORACLE_SCRIPT), "list"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(ROOT_DIR),
                env={**os.environ, "PYTHONPATH": str(nojs_dir)}
            )
            assert result.returncode == 0
            assert "wrong-type-hashes" not in result.stdout
            assert "wrong type for field 'hashes'" in result.stderr
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_list_with_missing_nested_key(self, tmp_path):
        """Test list rejects missing required nested key (hashes.check)."""
        case_dir = tmp_path / "missing-nested-key"
        case_dir.mkdir()
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.mjs"
        check_file.write_text("console.log(JSON.stringify({ok:true}));")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "missing-nested-key",
            "task_class": "test",
            "runtime": "node-vm",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "test",
                "task": task_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "missing-nested-key"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            import subprocess
            nojs_dir = tmp_path / "nojs"
            nojs_dir.mkdir()
            (nojs_dir / "jsonschema.py").write_text('raise ImportError("blocked")\n')

            result = subprocess.run(
                [sys.executable, str(ORACLE_SCRIPT), "list"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(ROOT_DIR),
                env={**os.environ, "PYTHONPATH": str(nojs_dir)}
            )
            assert result.returncode == 0
            assert "missing-nested-key" not in result.stdout
            assert "missing required nested key 'hashes.check'" in result.stderr
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)


class TestRunCommand:
    """Tests for the run command."""

    def test_run_raw_workspace_exit_1(self):
        """Test running check on raw workspace returns exit 1."""
        raw_dir = FIXTURES_DIR / "264" / "raw"
        result = run_oracle("run", "264-root-reaction-sign", str(raw_dir))
        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert output.get("ok") is False
        assert output.get("case") == "264-root-reaction-sign"

    def test_run_fix_workspace_exit_0(self):
        """Test running check on fix workspace returns exit 0."""
        fix_dir = FIXTURES_DIR / "264" / "fix"
        result = run_oracle("run", "264-root-reaction-sign", str(fix_dir))
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output.get("ok") is True

    def test_run_with_json_output(self):
        """Test running with --json flag produces pretty-printed JSON."""
        raw_dir = FIXTURES_DIR / "264" / "raw"
        result = run_oracle("run", "264-root-reaction-sign", str(raw_dir), "--json")
        assert result.returncode == 1
        # Should be valid JSON with indentation
        output = json.loads(result.stdout)
        assert "case" in output
        assert "runtime" in output
        assert "commit" in output
        assert output["case"] == "264-root-reaction-sign"
        assert output["runtime"] == "node-vm"

    def test_run_browser_runtime_exit_2(self, tmp_path):
        """Test browser runtime returns exit 2 with error."""
        # Create a case with browser runtime
        case_dir = tmp_path / "browser-case"
        case_dir.mkdir()
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.mjs"
        check_file.write_text("console.log(JSON.stringify({ok:true}));")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        manifest = {
            "id": "browser-case",
            "task_class": "test",
            "runtime": "browser",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": hash_file(task_file),
                "check": hash_file(check_file)
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        # Temporarily add this case to CASES_DIR for testing
        dest_case = CASES_DIR / "browser-case"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            result = run_oracle("run", "browser-case", str(tmp_path / "ws"))
            assert result.returncode == 2
            output = json.loads(result.stdout)
            assert output.get("error") == "unsupported runtime: browser"
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_run_timeout(self, tmp_path):
        """Test timeout handling returns exit 2."""
        case_dir = tmp_path / "timeout-case"
        case_dir.mkdir()
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        # Create a simple script that just sleeps (will hit the 0.1s timeout)
        check_file = oracle_dir / "check.mjs"
        check_file.write_text("""
const workspace = process.argv[2];
const out = (r, code) => { console.log(JSON.stringify(r)); process.exit(code); };
// This will run longer than our 0.1s timeout
const start = Date.now();
while(Date.now() - start < 5000) {}
out({ok: true}, 0);
""")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        manifest = {
            "id": "timeout-case",
            "task_class": "test",
            "runtime": "node-vm",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": hash_file(task_file),
                "check": hash_file(check_file)
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "timeout-case"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            # The oracle script catches TimeoutExpired internally and returns 2
            # We just need to make sure we get exit 2 and the timeout flag
            result = run_oracle("run", "timeout-case", str(tmp_path / "ws"), "--timeout", "0.1", check=False)
            assert result.returncode == 2, f"Expected exit 2, got {result.returncode}"
            output = json.loads(result.stdout)
            assert output.get("timeout") is True
            assert output.get("error") is not None
            assert "timeout" in output.get("error", "")
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)


class TestValidateCommand:
    """Tests for the validate command."""

    @pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
    def test_validate_with_real_fixtures_264(self, tmp_path):
        """Test validate with real 264 fixtures and built mutants."""
        raw = FIXTURES_DIR / "264" / "raw"
        fix = FIXTURES_DIR / "264" / "fix"

        # The check expects workspace/src/flightloads/static/workbench.js
        # So we need to create the full path within the workspace

        workbench = fix / "src" / "flightloads" / "static" / "workbench.js"
        assert workbench.exists(), f"workbench.js not found at {workbench}"

        content = workbench.read_text()

        # Mutant 1: sum:a+others+g+n -> sum:a+others-g+n
        content_mut1 = content.replace("sum:a+others+g+n", "sum:a+others-g+n")
        mut1 = tmp_path / "mut1"
        mut1.mkdir()
        (mut1 / "src" / "flightloads" / "static").mkdir(parents=True)
        (mut1 / "src" / "flightloads" / "static" / "workbench.js").write_text(content_mut1)

        # Mutant 2: sum:a+others+g+n -> sum:a+g+n
        content_mut2 = content.replace("sum:a+others+g+n", "sum:a+g+n")
        mut2 = tmp_path / "mut2"
        mut2.mkdir()
        (mut2 / "src" / "flightloads" / "static").mkdir(parents=True)
        (mut2 / "src" / "flightloads" / "static" / "workbench.js").write_text(content_mut2)

        result = run_oracle(
            "validate", "264-root-reaction-sign",
            "--raw", str(raw),
            "--fix", str(fix),
            "--mutant", f"mut1={mut1}",
            "--mutant", f"mut2={mut2}",
            check=False
        )

        # Validation should pass (exit 0)
        assert result.returncode == 0, f"validate failed: {result.stdout}\n{result.stderr}"

    @pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
    def test_validate_with_real_fixtures_267(self, tmp_path):
        """Test validate with real 267 fixtures and built mutants."""
        raw = FIXTURES_DIR / "267" / "raw"
        fix = FIXTURES_DIR / "267" / "fix"

        workbench = fix / "src" / "flightloads" / "static" / "workbench.js"
        assert workbench.exists(), f"workbench.js not found at {workbench}"

        content = workbench.read_text()

        # Mutant 1: p.clock+=p.speed*(now-p.wall)/1000;p.wall=now; -> p.clock=times[getIndex()]+p.speed*(now-p.wall)/1000;p.wall=now;
        content_mut1 = content.replace(
            "p.clock+=p.speed*(now-p.wall)/1000;p.wall=now;",
            "p.clock=times[getIndex()]+p.speed*(now-p.wall)/1000;p.wall=now;"
        )
        mut1 = tmp_path / "mut1"
        mut1.mkdir()
        (mut1 / "src" / "flightloads" / "static").mkdir(parents=True)
        (mut1 / "src" / "flightloads" / "static" / "workbench.js").write_text(content_mut1)

        # Mutant 2: speed:playbackReducedMotion()?0.25:1 -> speed:1
        content_mut2 = content.replace("speed:playbackReducedMotion()?0.25:1", "speed:1")
        mut2 = tmp_path / "mut2"
        mut2.mkdir()
        (mut2 / "src" / "flightloads" / "static").mkdir(parents=True)
        (mut2 / "src" / "flightloads" / "static" / "workbench.js").write_text(content_mut2)

        result = run_oracle(
            "validate", "267-playback-clock",
            "--raw", str(raw),
            "--fix", str(fix),
            "--mutant", f"mut1={mut1}",
            "--mutant", f"mut2={mut2}",
            check=False
        )

        # Validation should pass (exit 0)
        assert result.returncode == 0, f"validate failed: {result.stdout}\n{result.stderr}"

    def test_validate_missing_mutants_fails(self, tmp_path):
        """Test validation without mutants fails (need at least 2)."""
        fix_dir = tmp_path / "fix"
        fix_dir.mkdir()
        (fix_dir / "workbench.js").write_text("ok")

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "workbench.js").write_text("bad")

        result = run_oracle("validate", "264-root-reaction-sign",
                           "--raw", str(raw_dir), "--fix", str(fix_dir), check=False)
        # Should fail due to missing mutants
        assert result.returncode == 1


class TestLeakcheckCommand:
    """Tests for the leakcheck command."""

    def test_leakcheck_clean_workspace(self, tmp_path):
        """Test leakcheck on clean workspace."""
        clean_dir = tmp_path / "clean"
        clean_dir.mkdir()
        (clean_dir / "file.txt").write_text("clean content")

        result = run_oracle("leakcheck", str(clean_dir))
        assert result.returncode == 0
        assert "PASSED" in result.stdout

    def test_leakcheck_path_containment_oracle(self):
        """Test leakcheck detects path containment in oracle dir."""
        oracle_dir = CASES_DIR / "264-root-reaction-sign" / "oracle"
        result = run_oracle("leakcheck", str(oracle_dir))
        assert result.returncode == 1
        assert "restricted" in result.stdout.lower()

    def test_leakcheck_path_containment_validation(self):
        """Test leakcheck detects path containment in validation dir."""
        validation_dir = CASES_DIR / "264-root-reaction-sign" / "validation"
        result = run_oracle("leakcheck", str(validation_dir))
        assert result.returncode == 1
        assert "restricted" in result.stdout.lower()

    def test_leakcheck_symlink_to_oracle_file(self, tmp_path):
        """Test leakcheck with symlink to oracle file."""
        oracle_file = CASES_DIR / "264-root-reaction-sign" / "oracle" / "check.mjs"
        link_dir = tmp_path / "link"
        link_dir.mkdir()
        link_file = link_dir / "check.mjs"
        link_file.symlink_to(oracle_file)

        result = run_oracle("leakcheck", str(link_dir))
        # Should detect the symlinked file
        assert result.returncode == 1
        assert "identical" in result.stdout.lower()

    def test_leakcheck_registry_dir(self):
        """Test leakcheck detects path containment in registry dir."""
        registry_dir = ROOT_DIR / "registry"
        result = run_oracle("leakcheck", str(registry_dir))
        assert result.returncode == 1
        assert "restricted" in result.stdout.lower()

    def test_leakcheck_ledger_dir(self):
        """Test leakcheck detects path containment in ledger dir."""
        ledger_dir = ROOT_DIR / "ledger"
        result = run_oracle("leakcheck", str(ledger_dir))
        assert result.returncode == 1
        assert "restricted" in result.stdout.lower()

    def test_leakcheck_symlink_to_oracle_directory(self, tmp_path):
        """Test leakcheck with symlink to oracle directory."""
        oracle_dir = CASES_DIR / "264-root-reaction-sign" / "oracle"
        link_dir = tmp_path / "link"
        link_dir.mkdir()
        link_oracle = link_dir / "oracle_link"
        link_oracle.symlink_to(oracle_dir)

        result = run_oracle("leakcheck", str(link_dir))
        assert result.returncode == 1
        assert "symlink to restricted" in result.stdout.lower() or "identical" in result.stdout.lower()

    def test_leakcheck_symlink_to_validation_directory(self, tmp_path):
        """Test leakcheck with symlink to validation directory."""
        validation_dir = CASES_DIR / "264-root-reaction-sign" / "validation"
        link_dir = tmp_path / "link"
        link_dir.mkdir()
        link_validation = link_dir / "validation_link"
        link_validation.symlink_to(validation_dir)

        result = run_oracle("leakcheck", str(link_dir))
        assert result.returncode == 1
        assert "symlink to restricted" in result.stdout.lower() or "identical" in result.stdout.lower()

    def test_leakcheck_nested_symlink_to_oracle_directory(self, tmp_path):
        """Test leakcheck with symlink nested two levels down to oracle directory."""
        oracle_dir = CASES_DIR / "264-root-reaction-sign" / "oracle"
        link_dir = tmp_path / "link"
        link_dir.mkdir()
        nested_dir = link_dir / "nested"
        nested_dir.mkdir()
        deep_dir = nested_dir / "deep"
        deep_dir.mkdir()
        link_oracle = deep_dir / "oracle_link"
        link_oracle.symlink_to(oracle_dir)

        result = run_oracle("leakcheck", str(link_dir))
        assert result.returncode == 1
        assert "symlink to restricted" in result.stdout.lower() or "identical" in result.stdout.lower()

    def test_leakcheck_symlink_cycle(self, tmp_path):
        """Test leakcheck with symlink cycle (terminates, exit 0 when no leak)."""
        link_dir = tmp_path / "link"
        link_dir.mkdir()
        # Create a cycle: cycle_a -> cycle_b -> cycle_a (both inside workspace)
        cycle_a = link_dir / "cycle_a"
        cycle_b = link_dir / "cycle_b"
        cycle_a.symlink_to(cycle_b)
        cycle_b.symlink_to(cycle_a)

        result = run_oracle("leakcheck", str(link_dir))
        assert result.returncode == 0
        assert "PASSED" in result.stdout

    def test_leakcheck_dangling_symlink(self, tmp_path):
        """Test leakcheck with dangling symlink (no crash, exit 0)."""
        link_dir = tmp_path / "link"
        link_dir.mkdir()
        dangling = link_dir / "dangling"
        dangling.symlink_to("/nonexistent/file")

        result = run_oracle("leakcheck", str(link_dir))
        assert result.returncode == 0
        assert "PASSED" in result.stdout


class TestIntegration:
    """Integration tests."""

    def test_oracle_help(self):
        """Test oracle --help works."""
        result = run_oracle("--help")
        assert result.returncode == 0
        assert "list" in result.stdout
        assert "run" in result.stdout
        assert "validate" in result.stdout
        assert "leakcheck" in result.stdout

    def test_oracle_list_help(self):
        """Test oracle list --help works."""
        result = run_oracle("list", "--help")
        assert result.returncode == 0
        assert "--suite" in result.stdout
        assert "--status" in result.stdout

    def test_oracle_run_help(self):
        """Test oracle run --help works."""
        result = run_oracle("run", "--help")
        assert result.returncode == 0
        assert "--json" in result.stdout
        assert "--timeout" in result.stdout

    def test_oracle_validate_help(self):
        """Test oracle validate --help works."""
        result = run_oracle("validate", "--help")
        assert result.returncode == 0
        assert "--raw" in result.stdout
        assert "--fix" in result.stdout
        assert "--mutant" in result.stdout
        assert "--write" in result.stdout


class TestHashMismatch:
    """Tests for hash mismatch detection (criterion 2)."""

    def test_hash_mismatch_tampered_task_md(self, tmp_path):
        """Test hash mismatch on tampered task.md returns exit 2 with case and file name."""
        case_dir = tmp_path / "cases" / "hash-test-task"
        case_dir.mkdir(parents=True)
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.mjs"
        check_file.write_text("console.log(JSON.stringify({ok:false, reason:'fail'}));")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "hash-test-task",
            "task_class": "test",
            "runtime": "node-vm",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "hash-test-task"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            # Tamper with task.md AFTER copy - modify dest_case version
            dest_task = dest_case / "task.md"
            dest_task.write_text("# Tampered task")

            result = run_oracle("run", "hash-test-task", str(tmp_path / "ws"), check=False)
            assert result.returncode == 2
            assert "hash-test-task" in result.stderr
            assert "task.md" in result.stderr
            assert "hash mismatch" in result.stderr.lower()
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_hash_mismatch_tampered_check_file(self, tmp_path):
        """Test hash mismatch on tampered oracle/check.* returns exit 2 with case and check file name."""
        case_dir = tmp_path / "cases" / "hash-test-check"
        case_dir.mkdir(parents=True)
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.mjs"
        check_file.write_text("console.log(JSON.stringify({ok:false, reason:'fail'}));")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "hash-test-check",
            "task_class": "test",
            "runtime": "node-vm",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "hash-test-check"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            # Tamper with check file AFTER copy - modify dest_case version
            dest_check = dest_case / "oracle" / "check.mjs"
            dest_check.write_text("console.log(JSON.stringify({ok:true, reason:'tampered'}));")

            result = run_oracle("run", "hash-test-check", str(tmp_path / "ws"), check=False)
            assert result.returncode == 2
            assert "hash-test-check" in result.stderr
            assert "check" in result.stderr.lower()
            assert "hash mismatch" in result.stderr.lower()
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_hash_mismatch_untampered_copy_normal_result(self, tmp_path):
        """Test untampered copy of case works normally (exit 0 for pass, exit 1 for fail)."""
        case_dir = tmp_path / "cases" / "hash-test-clean"
        case_dir.mkdir(parents=True)
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.mjs"
        check_file.write_text("console.log(JSON.stringify({ok:false, reason:'fail'})); process.exit(1);")

        task_file = case_dir / "task.md"
        task_file.write_text("# Task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "hash-test-clean",
            "task_class": "test",
            "runtime": "node-vm",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "hash-test-clean"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            # No tampering - run should work
            ws = tmp_path / "ws"
            ws.mkdir()
            (ws / "test.txt").write_text("content")

            result = run_oracle("run", "hash-test-clean", str(ws), check=False)
            # Check returns ok:false, so exit should be 1
            assert result.returncode == 1
            output = json.loads(result.stdout)
            assert output.get("ok") is False
            assert output.get("case") == "hash-test-clean"
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)


class TestLeakcheckRegularFileCopies:
    """Tests for leakcheck on REGULAR-FILE copies (criterion 5)."""

    def test_leakcheck_identical_copy_in_workspace_different_name(self, tmp_path):
        """Test leakcheck detects byte-identical copy of check file under different name -> exit 1."""
        oracle_file = CASES_DIR / "264-root-reaction-sign" / "oracle" / "check.mjs"
        ws_dir = tmp_path / "workspace"
        ws_dir.mkdir()
        # Place identical copy with different name in workspace
        copy_file = ws_dir / "different_name.mjs"
        copy_file.write_bytes(oracle_file.read_bytes())

        result = run_oracle("leakcheck", str(ws_dir))
        assert result.returncode == 1
        assert "identical" in result.stdout.lower()
        assert str(copy_file) in result.stdout

    def test_leakcheck_identical_copy_nested_two_directories(self, tmp_path):
        """Test leakcheck detects identical copy nested two directories deep -> exit 1."""
        oracle_file = CASES_DIR / "264-root-reaction-sign" / "oracle" / "check.mjs"
        ws_dir = tmp_path / "workspace"
        ws_dir.mkdir()
        nested_dir = ws_dir / "level1" / "level2"
        nested_dir.mkdir(parents=True)
        # Place identical copy at nested path
        copy_file = nested_dir / "check.mjs"
        copy_file.write_bytes(oracle_file.read_bytes())

        result = run_oracle("leakcheck", str(ws_dir))
        assert result.returncode == 1
        assert "identical" in result.stdout.lower()
        assert str(copy_file) in result.stdout

    def test_leakcheck_identical_copy_validation_report(self, tmp_path):
        """Test leakcheck detects byte-identical copy of validation/report.json -> exit 1."""
        # Use 264 validation/report.json if it exists, otherwise use a created one
        validation_dir = CASES_DIR / "264-root-reaction-sign" / "validation"
        validation_dir.mkdir(exist_ok=True)
        report_file = validation_dir / "report.json"
        if not report_file.exists():
            report_file.write_text(json.dumps({"timestamp": "test", "verdict": True}))

        ws_dir = tmp_path / "workspace"
        ws_dir.mkdir()
        copy_file = ws_dir / "report.json"
        copy_file.write_bytes(report_file.read_bytes())

        result = run_oracle("leakcheck", str(ws_dir))
        assert result.returncode == 1
        assert "identical" in result.stdout.lower()
        assert str(copy_file) in result.stdout

    def test_leakcheck_copy_with_one_extra_byte_appended_exit_0(self, tmp_path):
        """Test leakcheck on copy with one extra byte appended -> exit 0 (accepted limitation)."""
        oracle_file = CASES_DIR / "264-root-reaction-sign" / "oracle" / "check.mjs"
        ws_dir = tmp_path / "workspace"
        ws_dir.mkdir()
        # Copy with one extra byte appended
        copy_file = ws_dir / "check.mjs"
        copy_file.write_bytes(oracle_file.read_bytes() + b"x")

        result = run_oracle("leakcheck", str(ws_dir))
        assert result.returncode == 0
        assert "PASSED" in result.stdout


class TestValidateExpectationViolations:
    """Tests for validate expectation violations (criterion 4)."""

    def test_validate_raw_must_fail_is_enforced_on_its_own(self, tmp_path):
        """Raw passes while two mutants fail: only the raw rule can produce the error."""
        repo = _tmp_repo(tmp_path)
        case = _marker_case(repo)
        raw, fix = _workspace(tmp_path, "raw", True), _workspace(tmp_path, "fix", True)
        m1, m2 = _workspace(tmp_path, "m1", False), _workspace(tmp_path, "m2", False)
        result = _run_tmp(repo, "validate", case, "--raw", str(raw), "--fix", str(fix),
                          "--mutant", f"m1={m1}", "--mutant", f"m2={m2}")
        assert result.returncode == 1
        assert "raw: expected exit 1" in result.stdout
        assert "mutants:" not in result.stdout
        assert "fix: expected" not in result.stdout

    def test_validate_each_mutant_must_fail_on_its_own(self, tmp_path):
        """Two mutants fail (count rule satisfied) but a third passes: only the per-mutant rule can fire."""
        repo = _tmp_repo(tmp_path)
        case = _marker_case(repo)
        raw, fix = _workspace(tmp_path, "raw", False), _workspace(tmp_path, "fix", True)
        m1, m2 = _workspace(tmp_path, "m1", False), _workspace(tmp_path, "m2", False)
        m3 = _workspace(tmp_path, "m3", True)
        result = _run_tmp(repo, "validate", case, "--raw", str(raw), "--fix", str(fix),
                          "--mutant", f"m1={m1}", "--mutant", f"m2={m2}", "--mutant", f"m3={m3}")
        assert result.returncode == 1
        assert "m3: expected exit 1" in result.stdout
        assert "mutants: at least 2" not in result.stdout
        assert "raw: expected" not in result.stdout

    def test_validate_control_all_expectations_met(self, tmp_path):
        """Control for the two tests above: the same harness exits 0 when every expectation holds."""
        repo = _tmp_repo(tmp_path)
        case = _marker_case(repo)
        raw, fix = _workspace(tmp_path, "raw", False), _workspace(tmp_path, "fix", True)
        m1, m2 = _workspace(tmp_path, "m1", False), _workspace(tmp_path, "m2", False)
        result = _run_tmp(repo, "validate", case, "--raw", str(raw), "--fix", str(fix),
                          "--mutant", f"m1={m1}", "--mutant", f"m2={m2}")
        assert result.returncode == 0, result.stdout
        assert "Validation PASSED" in result.stdout
    def test_validate_fix_workspace_fails_exit_1(self, tmp_path):
        """Test validate with fix workspace that FAILS -> exit 1, says fix must pass."""
        case_dir = tmp_path / "cases" / "validate-fix-fail"
        case_dir.mkdir(parents=True)
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.py"
        check_file.write_text("""
import json
import os
import sys

workspace = sys.argv[1] if len(sys.argv) > 1 else "."
test_file = os.path.join(workspace, "test.txt")
content = open(test_file).read() if os.path.exists(test_file) else ""
# Pass on raw, fail on fix - this is the bug: fix workspace should pass
if "raw" in os.path.basename(workspace):
    print(json.dumps({"ok": True, "reason": "raw passed"}))
    sys.exit(0)
else:
    print(json.dumps({"ok": False, "reason": "fix failed - BUG"}))
    sys.exit(1)
""")

        task_file = case_dir / "task.md"
        task_file.write_text("# Test task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "validate-fix-fail",
            "task_class": "test",
            "runtime": "python",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "validate-fix-fail"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            (raw_dir / "test.txt").write_text("content")

            fix_dir = tmp_path / "fix"
            fix_dir.mkdir()
            (fix_dir / "test.txt").write_text("content")

            result = run_oracle("validate", "validate-fix-fail",
                               "--raw", str(raw_dir), "--fix", str(fix_dir), check=False)
            assert result.returncode == 1
            assert "fix" in result.stdout
            assert "must pass" in result.stdout or "expected exit 0" in result.stdout
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_validate_fewer_than_two_mutants_exit_1(self, tmp_path):
        """Test validate with fewer than two mutants -> exit 1."""
        case_dir = tmp_path / "cases" / "validate-few-mutants"
        case_dir.mkdir(parents=True)
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.py"
        check_file.write_text("""
import json
import os
import sys

print(json.dumps({"ok": False, "reason": "default fail"}))
""")

        task_file = case_dir / "task.md"
        task_file.write_text("# Test task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "validate-few-mutants",
            "task_class": "test",
            "runtime": "python",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "validate-few-mutants"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            (raw_dir / "test.txt").write_text("content")

            fix_dir = tmp_path / "fix"
            fix_dir.mkdir()
            (fix_dir / "test.txt").write_text("content")

            # Only one mutant - should fail
            mutant_dir = tmp_path / "mutant"
            mutant_dir.mkdir()
            (mutant_dir / "test.txt").write_text("content")

            result = run_oracle("validate", "validate-few-mutants",
                               "--raw", str(raw_dir), "--fix", str(fix_dir),
                               "--mutant", f"mut1={mutant_dir}", check=False)
            assert result.returncode == 1
            assert "at least 2" in result.stdout or "mutants" in result.stdout
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_validate_all_expectations_met_exit_0_write_report(self, tmp_path):
        """Test validate with all expectations met -> exit 0 and report.json written."""
        case_dir = tmp_path / "cases" / "validate-all-pass"
        case_dir.mkdir(parents=True)
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.py"
        check_file.write_text("""
import json
import os
import sys

workspace = sys.argv[1] if len(sys.argv) > 1 else "."
test_file = os.path.join(workspace, "test.txt")
content = open(test_file).read() if os.path.exists(test_file) else ""
if "fail" in content:
    print(json.dumps({"ok": False, "reason": "failed as expected"}))
    sys.exit(1)
else:
    print(json.dumps({"ok": True, "reason": "passed as expected"}))
    sys.exit(0)
""")

        task_file = case_dir / "task.md"
        task_file.write_text("# Test task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "validate-all-pass",
            "task_class": "test",
            "runtime": "python",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "validate-all-pass"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            (raw_dir / "test.txt").write_text("content fail")

            fix_dir = tmp_path / "fix"
            fix_dir.mkdir()
            (fix_dir / "test.txt").write_text("content")

            # Create two mutants that fail
            mut1_dir = tmp_path / "mut1"
            mut1_dir.mkdir()
            (mut1_dir / "test.txt").write_text("content fail")

            mut2_dir = tmp_path / "mut2"
            mut2_dir.mkdir()
            (mut2_dir / "test.txt").write_text("content fail")

            # Get manifest hash before write
            manifest_path = CASES_DIR / "validate-all-pass" / "manifest.json"
            manifest_hash_before = hash_file(manifest_path)

            result = run_oracle("validate", "validate-all-pass",
                               "--raw", str(raw_dir), "--fix", str(fix_dir),
                               "--mutant", f"mut1={mut1_dir}",
                               "--mutant", f"mut2={mut2_dir}", "--write", check=False)
            assert result.returncode == 0

            # Check report.json was written
            validation_dir = CASES_DIR / "validate-all-pass" / "validation"
            report_file = validation_dir / "report.json"
            assert report_file.exists(), "report.json not written"

            # Check manifest.json is unchanged
            manifest_hash_after = hash_file(manifest_path)
            assert manifest_hash_after == manifest_hash_before, "manifest.json was modified"
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)


class TestPythonRuntimeDispatch:
    """Tests for python runtime dispatch (criterion 3)."""

    def test_python_runtime_dispatch(self, tmp_path):
        """Test python runtime with check.py passes through JSON and exit code 0/1/2."""
        case_dir = tmp_path / "cases" / "python-runtime-test"
        case_dir.mkdir(parents=True)
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.py"
        check_file.write_text("""
import json
import sys

# Simple pass check
print(json.dumps({"ok": True, "message": "success"}))
""")

        task_file = case_dir / "task.md"
        task_file.write_text("# Test task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "python-runtime-test",
            "task_class": "test",
            "runtime": "python",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "python-runtime-test"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            ws = tmp_path / "ws"
            ws.mkdir()
            (ws / "test.txt").write_text("content")

            result = run_oracle("run", "python-runtime-test", str(ws))
            assert result.returncode == 0
            output = json.loads(result.stdout)
            assert output.get("ok") is True
            assert output.get("case") == "python-runtime-test"
            assert output.get("runtime") == "python"
            assert output.get("strength") == "invariant-or-residual"
            assert output.get("status") == "probation"
            assert "commit" in output
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_python_runtime_exit_1_fail(self, tmp_path):
        """Test python runtime check that fails returns exit 1."""
        case_dir = tmp_path / "cases" / "python-runtime-fail"
        case_dir.mkdir(parents=True)
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.py"
        check_file.write_text("""
import json
import sys

print(json.dumps({"ok": False, "reason": "intentional fail"}))
sys.exit(1)
""")

        task_file = case_dir / "task.md"
        task_file.write_text("# Test task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "python-runtime-fail",
            "task_class": "test",
            "runtime": "python",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "python-runtime-fail"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            ws = tmp_path / "ws"
            ws.mkdir()
            (ws / "test.txt").write_text("content")

            result = run_oracle("run", "python-runtime-fail", str(ws), check=False)
            assert result.returncode == 1
            output = json.loads(result.stdout)
            assert output.get("ok") is False
            assert output.get("case") == "python-runtime-fail"
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)

    def test_python_runtime_exit_2_error(self, tmp_path):
        """Test python runtime with error returns exit 2."""
        case_dir = tmp_path / "cases" / "python-runtime-error"
        case_dir.mkdir(parents=True)
        oracle_dir = case_dir / "oracle"
        oracle_dir.mkdir()

        check_file = oracle_dir / "check.py"
        check_file.write_text("""
import json
import sys

print(json.dumps({"ok": False, "error": "runtime error"}))
sys.exit(2)
""")

        task_file = case_dir / "task.md"
        task_file.write_text("# Test task")

        task_hash = hash_file(task_file)
        check_hash = hash_file(check_file)

        manifest = {
            "id": "python-runtime-error",
            "task_class": "test",
            "runtime": "python",
            "strength": "invariant-or-residual",
            "status": "probation",
            "suite": "tuning",
            "hashes": {
                "input": "abc",
                "task": task_hash,
                "check": check_hash
            },
            "origin": {"issue": "test"}
        }
        (case_dir / "manifest.json").write_text(json.dumps(manifest))

        dest_case = CASES_DIR / "python-runtime-error"
        if dest_case.exists():
            shutil.rmtree(dest_case)
        shutil.copytree(case_dir, dest_case)

        try:
            ws = tmp_path / "ws"
            ws.mkdir()
            (ws / "test.txt").write_text("content")

            result = run_oracle("run", "python-runtime-error", str(ws), check=False)
            assert result.returncode == 2
            output = json.loads(result.stdout)
            assert output.get("ok") is False
            assert output.get("case") == "python-runtime-error"
        finally:
            if dest_case.exists():
                shutil.rmtree(dest_case)
