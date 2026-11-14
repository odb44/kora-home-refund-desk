"""
Reset the classwork to a clean slate (PROVIDED).

Restores the refund ledger to its seed and deletes sessions/, logs/ and tickets/.
Run it before each test scenario:  python reset_lab.py
"""
import shutil
from pathlib import Path

import kora_data

shutil.copy(kora_data.DATA_DIR / "refund_ledger.seed.json", kora_data.LEDGER_FILE)
for folder in ("sessions", "logs", "tickets"):
    shutil.rmtree(Path(folder), ignore_errors=True)
print("Ledger restored; sessions/, logs/ and tickets/ cleared.")
