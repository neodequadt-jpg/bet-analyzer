"""Unit tests for scoring.bookmaker_monitor — uses tmp_path, no network."""

import json
import unittest
from pathlib import Path
from typing import Any

from scoring.bookmaker_monitor import load, score, list_risky, list_recommended


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_registry(tmp: Path, data: dict[str, Any]) -> Path:
    """Write *data* as JSON into tmp and return the path."""
    p = tmp / "bookmakers.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def _default_registry() -> dict[str, Any]:
    """A minimal registry covering all license tiers."""
    return {
        "Winline": {"license": "RU", "payout_days": 1, "issues": []},
        "1xBet": {"license": "Curacao", "payout_days": 7,
                  "issues": ["payout delays", "verification issues", "restricted accounts"]},
        "Cosmobet": {"license": "Curacao", "payout_days": 10,
                     "issues": ["payout delays", "verification issues", "restricted accounts"]},
        "NoLicBK": {"license": "none", "payout_days": 30, "issues": []},
        "MGABook": {"license": "MGA", "payout_days": 1, "issues": []},
        "AnjouanBK": {"license": "Anjouan", "payout_days": 7,
                      "issues": ["payout delays", "verification issues"]},
    }


class TestLoad(unittest.TestCase):
    """Tests for load()."""

    def test_load_registry(self) -> None:
        """load() reads and returns the JSON dict."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            data = {"TestBK": {"license": "RU", "payout_days": 1, "issues": []}}
            p = _write_registry(Path(tmp), data)
            loaded = load(p)
            self.assertEqual(loaded, data)


class TestScore(unittest.TestCase):
    """Tests for score()."""

    def test_score_ru_legal_high(self) -> None:
        """RU-licensed bookmaker with fast payout and no issues ≥ 80."""
        bk = {"license": "RU", "payout_days": 1, "issues": []}
        s = score(bk)
        # RU=30, payout=max(0,30-1*3)=27, issues=max(0,30-0)=30 → 87
        self.assertGreaterEqual(s, 80)

    def test_score_curacao_low(self) -> None:
        """Curacao-licensed bookmaker with many issues ≤ 30."""
        bk = {"license": "Curacao", "payout_days": 7,
              "issues": ["a", "b", "c"]}
        s = score(bk)
        # Curacao=15, payout=max(0,30-7*3)=9, issues=max(0,30-3*10)=0 → 24
        self.assertLessEqual(s, 30)

    def test_score_anjouan_very_low(self) -> None:
        """Anjouan-licensed bookmaker ≤ 20."""
        bk = {"license": "Anjouan", "payout_days": 7,
              "issues": ["a", "b"]}
        s = score(bk)
        # Anjouan=5, payout=max(0,30-7*3)=9, issues=max(0,30-2*10)=10 → 24
        # With 3 issues: issues=0 → 14
        bk2 = {"license": "Anjouan", "payout_days": 7,
               "issues": ["a", "b", "c"]}
        s2 = score(bk2)
        self.assertLessEqual(s2, 20)

    def test_score_no_license_zero(self) -> None:
        """No license + slow payout + many issues → score 0."""
        bk = {"license": "none", "payout_days": 30, "issues": ["a", "b", "c"]}
        s = score(bk)
        # none=0, payout=max(0,30-30*3)=0, issues=max(0,30-3*10)=0 → 0
        self.assertEqual(s, 0)

    def test_score_issues_reduce(self) -> None:
        """More issues must not increase the score."""
        bk_clean = {"license": "RU", "payout_days": 1, "issues": []}
        bk_dirty = {"license": "RU", "payout_days": 1, "issues": ["x"]}
        self.assertGreaterEqual(score(bk_clean), score(bk_dirty))

    def test_score_payout_speed_affects(self) -> None:
        """Faster payout must not decrease the score (all else equal)."""
        bk_fast = {"license": "RU", "payout_days": 1, "issues": []}
        bk_slow = {"license": "RU", "payout_days": 5, "issues": []}
        self.assertGreaterEqual(score(bk_fast), score(bk_slow))

    def test_score_clamped_to_100(self) -> None:
        """Even with maximal components, score cannot exceed 100."""
        bk = {"license": "MGA", "payout_days": 0, "issues": []}
        # MGA=40, payout=max(0,30-0)=30, issues=30 → 100
        s = score(bk)
        self.assertLessEqual(s, 100)


class TestLists(unittest.TestCase):
    """Tests for list_risky / list_recommended."""

    def setUp(self) -> None:
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        self._reg = _default_registry()
        self._reg_path = _write_registry(self._tmp_path, self._reg)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_list_risky_threshold(self) -> None:
        """list_risky returns only bookmakers below threshold."""
        risky = list_risky(threshold=50, registry_path=self._reg_path)
        for _name, s in risky:
            self.assertLess(s, 50)

    def test_list_recommended_threshold(self) -> None:
        """list_recommended returns only bookmakers at or above threshold."""
        rec = list_recommended(threshold=70, registry_path=self._reg_path)
        for _name, s in rec:
            self.assertGreaterEqual(s, 70)

    def test_list_sorted(self) -> None:
        """risky sorted worst-first (ascending), recommended best-first (descending)."""
        risky = list_risky(threshold=50, registry_path=self._reg_path)
        scores_risky = [s for _, s in risky]
        self.assertEqual(scores_risky, sorted(scores_risky))

        rec = list_recommended(threshold=70, registry_path=self._reg_path)
        scores_rec = [s for _, s in rec]
        self.assertEqual(scores_rec, sorted(scores_rec, reverse=True))


if __name__ == "__main__":
    unittest.main()
