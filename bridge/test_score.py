import unittest

from bridge import WeatherScore


class WeatherScoreTest(unittest.TestCase):
    def test_warmup_is_zero(self):
        score = WeatherScore(warmup_seconds=20)
        self.assertEqual(score.update(2.0), 0)
        self.assertEqual(score.update(3.0), 0)

    def test_change_after_warmup_is_bounded(self):
        score = WeatherScore(warmup_seconds=0)
        score.update(2.0)
        for _ in range(20):
            value = score.update(4.0)
        self.assertGreater(value, 0)
        self.assertLessEqual(value, 100)

    def test_non_finite_value_is_ignored(self):
        score = WeatherScore(warmup_seconds=0)
        self.assertEqual(score.update(float("nan")), 0)


if __name__ == "__main__":
    unittest.main()
