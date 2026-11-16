"""Execute the eighteen scripts generated from the confirmed KSJ decisions."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    decisions = json.loads((ROOT / 'data/exp/data-preprocessing/ksj-eighteen-facilities/decisions.json').read_text())
    assert decisions['confirmed'] and len(decisions['datasets']) == 18
    for spec in decisions['datasets'].values():
        result = subprocess.run([sys.executable, str(ROOT / spec['script'])], cwd=ROOT,
                                capture_output=True, text=True)
        print(result.stdout.strip(), flush=True)
        if result.returncode:
            print(result.stderr, file=sys.stderr)
            raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
