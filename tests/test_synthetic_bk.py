import pytest
import os
import json
from bookmakers.manual_refresh import _seeded_shift

def test_auto_files_have_four_bk():
    manual_dir = "data/manual"
    files = [f for f in os.listdir(manual_dir) if f.startswith("auto_") and f.endswith(".json")]
    assert len(files) > 0
    for f in files:
        with open(os.path.join(manual_dir, f)) as j:
            data = json.load(j)
            assert len(data["bookmakers"]) >= 4

def test_synthetic_bks_disagree():
    seed1 = "marathon:abc"
    seed2 = "winline:abc"
    assert _seeded_shift(seed1, 0) != _seeded_shift(seed2, 0)
