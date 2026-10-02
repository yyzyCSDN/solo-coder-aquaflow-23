from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    id: str
    healthy: bool
    rank: int
    capacity: float


def choose(rows: list[Unit], required: float, failed: str) -> list[str]:
    """Select healthy booster units to replace a failed unit.

    The failed unit is excluded even when it has the best rank, and so is
    every unit that is not healthy.  Remaining candidates are visited in a
    deterministic order (rank, then larger capacity, then id) and added
    until their combined capacity meets the requirement.
    """
    candidates = sorted(
        (r for r in rows if r.healthy and r.id != failed),
        key=lambda r: (r.rank, -r.capacity, r.id),
    )
    selected: list[str] = []
    capacity = 0.0
    for unit in candidates:
        selected.append(unit.id)
        capacity += unit.capacity
        if capacity >= required:
            return selected
    raise ValueError("insufficient capacity")
