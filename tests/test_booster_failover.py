import unittest

from aquaflow.api import AquaFlowService
from aquaflow.booster.failover import FailoverPlan, Unit, choose


def _unit(u):
    return {"id": u[0], "healthy": u[1], "rank": u[2], "capacity": u[3]}


class FailoverChooseTest(unittest.TestCase):
    def test_top_ranked_unit_faulty_picks_next_healthy(self):
        # P1 ranks highest but is the failed unit; the flow must skip it.
        rows = [
            Unit("P1", False, 1, 100.0),
            Unit("P2", True, 2, 60.0),
            Unit("P3", True, 3, 60.0),
        ]
        plan = choose(rows, 50.0, "P1")
        self.assertEqual(plan, FailoverPlan(("P2",), ("P1",)))

    def test_failed_flag_excludes_even_if_flagged_healthy(self):
        # A unit marked failed must be excluded regardless of its healthy flag.
        rows = [
            Unit("P1", True, 1, 100.0),
            Unit("P2", True, 2, 60.0),
        ]
        plan = choose(rows, 50.0, "P1")
        self.assertEqual(plan, FailoverPlan(("P2",), ("P1",)))

    def test_equal_capacity_alternatives_break_ties_by_rank_then_id(self):
        rows = [
            Unit("P1", False, 1, 40.0),
            Unit("P2", True, 2, 40.0),
            Unit("P3", True, 2, 40.0),
        ]
        plan = choose(rows, 80.0, "P1")
        self.assertEqual(plan.selected, ("P2", "P3"))
        self.assertEqual(plan.excluded, ("P1",))

    def test_higher_capacity_preferred_within_rank_for_earliest_meet(self):
        # Same rank: higher capacity first, so the big unit alone meets demand.
        rows = [
            Unit("P1", False, 1, 100.0),
            Unit("BIG", True, 2, 80.0),
            Unit("SMALL", True, 2, 20.0),
        ]
        plan = choose(rows, 70.0, "P1")
        self.assertEqual(plan.selected, ("BIG",))

    def test_unhealthy_units_are_excluded_even_without_failed_flag(self):
        rows = [
            Unit("P1", False, 1, 100.0),
            Unit("P2", True, 2, 60.0),
        ]
        plan = choose(rows, 50.0, "")
        self.assertEqual(plan, FailoverPlan(("P2",), ("P1",)))

    def test_healthy_combo_still_insufficient_raises(self):
        rows = [
            Unit("P1", False, 1, 100.0),
            Unit("P2", True, 2, 30.0),
            Unit("P3", True, 3, 30.0),
        ]
        with self.assertRaises(ValueError) as ctx:
            choose(rows, 80.0, "P1")
        self.assertEqual(str(ctx.exception), "insufficient capacity")

    def test_choice_is_deterministic(self):
        rows = [
            Unit("P3", True, 3, 40.0),
            Unit("P1", False, 1, 40.0),
            Unit("P2", True, 2, 40.0),
        ]
        first = choose(rows, 80.0, "P1")
        second = choose(list(reversed(rows)), 80.0, "P1")
        self.assertEqual(first, second)
        self.assertEqual(first.selected, ("P2", "P3"))


class FailoverWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.svc = AquaFlowService()

    def test_workflow_publishes_selected_and_excluded(self):
        payload = {
            "units": [
                _unit(("P1", False, 1, 100.0)),
                _unit(("P2", True, 2, 60.0)),
                _unit(("P3", True, 3, 60.0)),
            ],
            "required": 50.0,
            "failed": "P1",
        }
        result = self.svc.run_workflow("booster_failover", payload)
        self.assertEqual(result["decision"], "reroute")
        self.assertEqual(result["value"], {"selected": ["P2"], "excluded": ["P1"]})
        self.assertEqual(result["evidence"]["failed"], "P1")
        self.assertEqual(result["evidence"]["selected_capacity"], 60.0)
        self.assertEqual(result["audit"]["contract"], "v1")

    def test_workflow_equal_capacity_alternatives(self):
        payload = {
            "units": [
                _unit(("P1", False, 1, 40.0)),
                _unit(("P3", True, 2, 40.0)),
                _unit(("P2", True, 2, 40.0)),
            ],
            "required": 80.0,
            "failed": "P1",
        }
        result = self.svc.run_workflow("booster_failover", payload)
        self.assertEqual(result["value"]["selected"], ["P2", "P3"])
        self.assertEqual(result["value"]["excluded"], ["P1"])

    def test_workflow_healthy_combo_insufficient_raises(self):
        payload = {
            "units": [
                _unit(("P1", False, 1, 100.0)),
                _unit(("P2", True, 2, 30.0)),
                _unit(("P3", True, 3, 30.0)),
            ],
            "required": 80.0,
            "failed": "P1",
        }
        with self.assertRaises(ValueError):
            self.svc.run_workflow("booster_failover", payload)


if __name__ == "__main__":
    unittest.main()
