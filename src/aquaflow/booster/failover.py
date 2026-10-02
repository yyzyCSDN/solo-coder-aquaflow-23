from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    id: str
    healthy: bool
    rank: int
    capacity: float


@dataclass(frozen=True)
class FailoverPlan:
    selected: tuple[str, ...]
    excluded: tuple[str, ...]


def choose(rows: list[Unit], required: float, failed: str = "") -> FailoverPlan:
    """Pick healthy replacement units after a booster failover.

    The failed unit and every unhealthy unit are excluded, so a unit can never
    be re-selected just because it ranks highest.  Remaining units are taken in
    deterministic rank order (lower rank first, higher capacity first, then id)
    until their combined capacity meets the requirement.
    """
    excluded = {u.id for u in rows if not u.healthy}
    if failed:
        excluded.add(failed)

    candidates = sorted(
        (u for u in rows if u.healthy and u.id not in excluded),
        key=lambda u: (u.rank, -u.capacity, u.id),
    )

    selected: list[str] = []
    capacity = 0.0
    for unit in candidates:
        selected.append(unit.id)
        capacity += unit.capacity
        if capacity >= required:
            return FailoverPlan(tuple(selected), tuple(sorted(excluded)))

    raise ValueError("insufficient capacity")
