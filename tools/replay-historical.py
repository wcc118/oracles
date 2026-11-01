#!/usr/bin/env python3
"""Reproduce the six historical state/data cases, without model inference."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, evidence):
    if not condition:
        raise RuntimeError(str(evidence))


def replay(write=False):
    index_path = ROOT / 'tests/fixtures/historical-source-index.json'
    index = json.loads(index_path.read_text())
    for issue, variants in index.items():
        for variant, source in variants.items():
            require(digest(ROOT / 'tests/fixtures' / issue / variant / source['file']) == source['sha256'], (issue, variant, 'source hash mismatch'))
    recipes = sorted((ROOT / 'cases').glob('*/validation/mutations.json'))
    for recipe_path in recipes:
        case = recipe_path.parent.parent
        fixture = ROOT / 'tests/fixtures' / case.name[:3]
        recipe = json.loads(recipe_path.read_text())
        with tempfile.TemporaryDirectory(prefix='oracle-admission-') as temp:
            workspaces = {'raw': fixture / 'raw', 'fix': fixture / 'fix'}
            for name, old, new in [*recipe['mutants'], ['alternative', *recipe['alternative']]]:
                target = Path(temp) / name
                shutil.copytree(fixture / 'fix', target)
                source = target / index[case.name[:3]]['fix']['file']
                text = source.read_text()
                require(text.count(old) == 1, (case.name, name, 'mutation target changed'))
                source.write_text(text.replace(old, new))
                workspaces[name] = target
            command = [str(ROOT / 'tools/oracle'), 'validate', case.name,
                       '--raw', str(workspaces['raw']), '--fix', str(workspaces['fix'])]
            for name, _, _ in recipe['mutants']:
                command += ['--mutant', name + '=' + str(workspaces[name])]
            admission = subprocess.run(command, capture_output=True, text=True, timeout=30)
            require(admission.returncode == 0, admission.stdout + admission.stderr)
            for name, workspace in workspaces.items():
                expected = 0 if name in {'fix', 'alternative'} else 1
                for _ in range(3):
                    result = subprocess.run(['node', str(case / 'oracle/check.mjs'), str(workspace)],
                                            capture_output=True, text=True, timeout=10)
                    require(result.returncode == expected, (case.name, name, result.stdout, result.stderr))
                    require(json.loads(result.stdout).get('ok') is (expected == 0), (case.name, name, 'wrong verdict'))
            if write:
                result = subprocess.run([*command, '--write'], capture_output=True, text=True, timeout=30)
                require(result.returncode == 0, result.stdout + result.stderr)
                report_path = case / 'validation/report.json'
                report = json.loads(report_path.read_text())
                report['replay_evidence'] = {
                    'python_version': platform.python_version(),
                    'repetitions_per_variant': 3, 'valid_alternative_passed': True,
                    'source_index_sha256': digest(index_path), 'recipe_sha256': digest(recipe_path),
                    'manifest_sha256': digest(case / 'manifest.json'),
                    'support_sha256': digest(ROOT / 'lib/state_dom.mjs'),
                    'node_version': subprocess.check_output(['node', '--version'], text=True).strip(),
                    'scope': 'State/data regression; tuning only; no browser or physical-validation claim',
                }
                report_path.write_text(json.dumps(report, indent=2) + '\n')
            print(case.name + ': raw failed; fix/alternative passed; two behavioral mutants caught; three stable replays')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='retain reports only after all checks for each case pass')
    replay(parser.parse_args().write)
