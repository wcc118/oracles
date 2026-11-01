"""Replay actual source snapshots; admission errors are not behavioral detections."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX = json.loads((ROOT / 'tests/fixtures/historical-source-index.json').read_text())
CASES = sorted(path.parent.parent.name for path in (ROOT / 'cases').glob('*/validation/mutations.json'))


def test_source_snapshot_and_support_hashes():
    for issue, variants in INDEX.items():
        for variant, source in variants.items():
            assert len(source['commit']) == 40
            data = (ROOT / 'tests/fixtures' / issue / variant / source['file']).read_bytes()
            assert hashlib.sha256(data).hexdigest() == source['sha256']
    for name in CASES:
        manifest = json.loads((ROOT / 'cases' / name / 'manifest.json').read_text())
        assert manifest['hashes']['input'] == INDEX[name[:3]]['raw']['sha256']
        for relative, expected in manifest['support_files'].items():
            assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def make_variant(destination, case, recipe):
    source = ROOT / 'tests/fixtures' / case[:3] / 'fix'
    shutil.copytree(source, destination)
    path = destination / INDEX[case[:3]]['fix']['file']
    text = path.read_text()
    old, new = recipe
    assert text.count(old) == 1, (case, old, text.count(old))
    path.write_text(text.replace(old, new))
    return destination


@pytest.mark.parametrize('case', CASES)
def test_historical_case_admission_and_valid_alternative(tmp_path, case):
    recipe = json.loads((ROOT / 'cases' / case / 'validation/mutations.json').read_text())
    fixture = ROOT / 'tests/fixtures' / case[:3]
    command = [str(ROOT / 'tools/oracle'), 'validate', case, '--raw', str(fixture / 'raw'), '--fix', str(fixture / 'fix')]
    for name, old, new in recipe['mutants']:
        workspace = make_variant(tmp_path / name, case, [old, new])
        command += ['--mutant', name + '=' + str(workspace)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Validation PASSED' in result.stdout
    alternate = make_variant(tmp_path / 'alternative', case, recipe['alternative'])
    check = ROOT / 'cases' / case / 'oracle/check.mjs'
    for _ in range(3):
        result = subprocess.run(['node', str(check), str(alternate)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)['ok'] is True
