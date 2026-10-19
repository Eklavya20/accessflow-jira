"""Run offline verification with temporary files confined to this workspace."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    (root / "reports").mkdir(exist_ok=True)
    checks = [
        ["pytest", "-q", "--tb=short", "--junitxml=reports/offline-tests.xml"],
        ["ruff", "check", "src", "tests", "scripts"],
        ["ruff", "format", "--check", "src", "tests", "scripts"],
        ["pip", "check"],
    ]
    # A unique directory avoids stale temporary-file permissions from another run/account.
    with tempfile.TemporaryDirectory(prefix="offline-check-", dir=root / "reports") as temp_root:
        env = {**os.environ, "PYTEST_DEBUG_TEMPROOT": temp_root}
        for check in checks:
            result = subprocess.run([sys.executable, "-m", *check], cwd=root, env=env, check=False)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
