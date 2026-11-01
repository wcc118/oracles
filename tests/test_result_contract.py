import json
from pathlib import Path

import pytest
from test_oracle import load_oracle_module, _tmp_repo, _marker_case, hash_file


@pytest.mark.parametrize('code,process_exit', [
    ('raise RuntimeError("infrastructure")', 1),
    ('print("not json"); raise SystemExit(1)', 1),
    ('print("[]"); raise SystemExit(1)', 1),
    ('print(\'{"ok": "false"}\'); raise SystemExit(1)', 1),
    ('print(\'{"ok": false}\')', 0),
    ('print(\'{"ok": true}\'); raise SystemExit(1)', 1),
    ('print(\'{"ok": false}\'); raise SystemExit(3)', 3),
    ('print(\'{"ok": false, "error": "fixture unavailable"}\'); raise SystemExit(1)', 1),
])
def test_real_process_errors_are_not_behavioral(tmp_path, code, process_exit):
    module = load_oracle_module(Path(__file__).resolve().parents[1])
    check = tmp_path / 'check.py'
    check.write_text(code)
    result = module.run_workspace(check, tmp_path, 'fixture', 'raw')
    assert result['process_exit_code'] == process_exit
    assert result['exit_code'] == 2
    assert result['outcome'] == 'inconclusive'
    assert module.classify_mutant_failure(result) == 'structural'


def test_real_assertion_failure_and_pass_remain_distinct(tmp_path):
    module = load_oracle_module(Path(__file__).resolve().parents[1])
    check = tmp_path / 'check.py'
    check.write_text('print(\'{"ok": false, "reason": "balance mismatch"}\'); raise SystemExit(1)')
    result = module.run_workspace(check, tmp_path, 'fixture', 'raw')
    assert result['exit_code'] == 1
    assert module.classify_mutant_failure(result) == 'behavioral'
    check.write_text('print(\'{"ok": true}\')')
    assert module.run_workspace(check, tmp_path, 'fixture', 'fix')['outcome'] == 'pass'


def test_run_and_admission_both_reject_crashing_check(tmp_path, capsys):
    repo = _tmp_repo(tmp_path)
    case_id = _marker_case(repo)
    case = repo / 'cases' / case_id
    check = case / 'oracle/check.py'
    check.write_text('import pathlib,sys\nif pathlib.Path(sys.argv[1], "PASS").exists():\n print(\'{"ok": true}\')\nelse:\n raise RuntimeError("fixture setup failed")\n')
    manifest = json.loads((case / 'manifest.json').read_text())
    manifest['hashes']['check'] = hash_file(check)
    (case / 'manifest.json').write_text(json.dumps(manifest))
    raw = tmp_path / 'raw'; raw.mkdir()
    fix = tmp_path / 'fix'; fix.mkdir(); (fix / 'PASS').touch()
    module = load_oracle_module(repo)
    assert module.run_case(case_id, str(raw), json_output=True) == 2
    assert json.loads(capsys.readouterr().out)['outcome'] == 'inconclusive'
    mutant2 = tmp_path / 'mutant2'; mutant2.mkdir()
    assert module.validate_case(case_id, str(raw), str(fix), {'mutant1': str(raw), 'mutant2': str(mutant2)}) == 1
    assert 'Validation FAILED' in capsys.readouterr().out


def test_reserved_names_and_duplicate_mutant_workspaces_are_rejected(tmp_path):
    repo = _tmp_repo(tmp_path)
    case_id = _marker_case(repo)
    module = load_oracle_module(repo)
    assert module.validate_case(case_id, str(tmp_path), str(tmp_path), {'raw': str(tmp_path)}) == 2
    assert module.validate_case(case_id, str(tmp_path), str(tmp_path), {'a': str(tmp_path), 'b': str(tmp_path / '.')}) == 2
