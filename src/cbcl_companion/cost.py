"""Pricing table and usage accounting. Prices are Anthropic list prices (USD per 1M tokens)."""
from __future__ import annotations

from dataclasses import dataclass, field

# input, output, cache_write (1.25x input), cache_read
PRICING = {
    "claude-opus-5-5":   {"in": 4.00, "out": 20.00, "cache_write": 5.00,  "cache_read": 0.20},
    "claude-sonnet-5-5": {"in": 2.00, "out": 10.00, "cache_write": 2.50,  "cache_read": 0.20},
    "claude-haiku-5-5":  {"in": 0.10, "out": 0.50,  "cache_write": 0.125, "cache_read": 0.01},
}


@dataclass
class UsageRecord:
    label: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        p = PRICING.get(self.model)
        if not p:
            return 0.0
        return (
            self.input_tokens * p["in"]
            + self.output_tokens * p["out"]
            + self.cache_write_tokens * p["cache_write"]
            + self.cache_read_tokens * p["cache_read"]
        ) / 1_000_000


@dataclass
class UsageTracker:
    records: list[UsageRecord] = field(default_factory=list)

    def add(self, label: str, model: str, usage) -> UsageRecord:
        rec = UsageRecord(
            label=label,
            model=model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        )
        self.records.append(rec)
        return rec

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)

    def table(self) -> str:
        rows = [f"{'label':<22}{'model':<20}{'in':>7}{'out':>7}{'cache_w':>9}{'cache_r':>9}{'USD':>10}"]
        for r in self.records:
            rows.append(
                f"{r.label:<22}{r.model:<20}{r.input_tokens:>7}{r.output_tokens:>7}"
                f"{r.cache_write_tokens:>9}{r.cache_read_tokens:>9}{r.cost_usd:>10.4f}"
            )
        rows.append(f"{'TOTAL':<22}{'':<20}{'':>7}{'':>7}{'':>9}{'':>9}{self.total_cost_usd:>10.4f}")
        return "\n".join(rows)
