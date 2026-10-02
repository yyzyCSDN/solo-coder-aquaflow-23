import unittest

from aquaflow.api import AquaFlowService
from aquaflow.booster.failover import Unit, choose


def unit(uid, capacity, rank, healthy=True):
    return Unit(uid, healthy, rank, capacity)


class FailoverTests(unittest.TestCase):
    def test_top_ranked_failed_unit_is_excluded(self):
        # B-1 ranks highest but is the failed device; the healthy next-ranked
        # unit must take over instead of re-selecting B-1.
        rows = [
            unit("B-1", 100.0, rank=1),
            unit("B-2", 80.0, rank=2),
            unit("B-3", 60.0, rank=3),
        ]
        self.assertEqual(choose(rows, 75.0, "B-1"), ["B-2"])
        self.assertEqual(choose(rows, 140.0, "B-1"), ["B-2", "B-3"])

    def test_unhealthy_units_are_skipped_even_when_ranked_high(self):
        rows = [
            unit("B-1", 100.0, rank=1, healthy=False),
            unit("B-2", 80.0, rank=2),
        ]
        self.assertEqual(choose(rows, 80.0, "B-3"), ["B-2"])

    def test_tied_capacity_alternatives_break_ties_deterministically(self):
        # Same rank and capacity: the lexicographically smallest healthy id
        # is selected, regardless of input ordering.
        rows = [
            unit("B-9", 50.0, rank=2),
            unit("B-7", 50.0, rank=2),
            unit("B-8", 50.0, rank=2),
        ]
        self.assertEqual(choose(rows, 50.0, "B-0"), ["B-7"])
        self.assertEqual(choose(rows, 100.0, "B-0"), ["B-7", "B-8"])

    def test_insufficient_healthy_capacity_raises(self):
        rows = [
            unit("B-1", 100.0, rank=1),
            unit("B-2", 40.0, rank=2),
        ]
        with self.assertRaisesRegex(ValueError, "insufficient capacity"):
            choose(rows, 50.0, "B-1")

    def test_end_to_end_publishes_substitutes_and_excluded_failure(self):
        payload = {
            "units": [
                {"id": "B-1", "healthy": True, "rank": 1, "capacity": 100.0},
                {"id": "B-2", "healthy": True, "rank": 2, "capacity": 80.0},
                {"id": "B-3", "healthy": True, "rank": 3, "capacity": 60.0},
            ],
            "required": 75.0,
            "failed": "B-1",
        }
        result = AquaFlowService().run_workflow("booster_failover", payload)
        self.assertEqual(result["decision"], "reroute")
        self.assertEqual(result["value"], ["B-2"])
        self.assertEqual(result["evidence"]["excluded"], ["B-1"])
        self.assertEqual(result["evidence"]["failed"], "B-1")
        self.assertEqual(result["audit"]["contract"], "v1")

    def test_end_to_end_insufficient_capacity_surfaces_error(self):
        payload = {
            "units": [
                {"id": "B-1", "healthy": True, "rank": 1, "capacity": 100.0},
                {"id": "B-2", "healthy": True, "rank": 2, "capacity": 40.0},
            ],
            "required": 50.0,
            "failed": "B-1",
        }
        with self.assertRaisesRegex(ValueError, "insufficient capacity"):
            AquaFlowService().run_workflow("booster_failover", payload)


if __name__ == "__main__":
    unittest.main()
