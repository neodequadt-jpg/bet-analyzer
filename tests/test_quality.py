import unittest


class FakeVB:
    def __init__(self, ev, kelly):
        self.ev = ev
        self.kelly = kelly


class TestQuality(unittest.TestCase):
    def test_accept(self):
        from scoring.quality import is_high_quality_value
        ok, _ = is_high_quality_value(FakeVB(0.06, 0.015))
        self.assertTrue(ok)

    def test_reject_low_ev(self):
        from scoring.quality import is_high_quality_value
        ok, _ = is_high_quality_value(FakeVB(0.01, 0.015))
        self.assertFalse(ok)

    def test_reject_high_ev(self):
        from scoring.quality import is_high_quality_value, MAX_EV
        ok, _ = is_high_quality_value(FakeVB(MAX_EV + 0.05, 0.015))
        self.assertFalse(ok)

    def test_reject_low_kelly(self):
        from scoring.quality import is_high_quality_value
        ok, _ = is_high_quality_value(FakeVB(0.06, 0.001))
        self.assertFalse(ok)

    def test_reject_high_kelly(self):
        from scoring.quality import is_high_quality_value
        ok, _ = is_high_quality_value(FakeVB(0.06, 0.05))
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
