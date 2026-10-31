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
