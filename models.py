"""Small data contracts shared by the TalentGuard application."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ModelScore:
    name: str
    average_precision: float
    roc_auc: float
    f1_at_capacity: float
    recall_at_capacity: float
    precision_at_50: float
    recall_at_50: float
    lift_at_50: float
    capacity_threshold: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiskReason:
    feature: str
    explanation: str
    contribution: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

