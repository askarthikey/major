"""Canonical power, duration, energy, and unit conversions for marketplace trades."""

from dataclasses import dataclass

WH_PER_UNIT = 10.0
KWH_PER_UNIT = WH_PER_UNIT / 1000.0


@dataclass(frozen=True)
class EnergyContract:
    power_kw: float
    duration_hours: float

    def __post_init__(self):
        if self.power_kw <= 0 or self.duration_hours <= 0:
            raise ValueError("Power and duration must be greater than zero")

    @property
    def energy_kwh(self) -> float:
        return round(self.power_kw * self.duration_hours, 6)

    @property
    def units(self) -> int:
        return round(self.energy_kwh / KWH_PER_UNIT)

    def as_dict(self) -> dict:
        return {
            "power_kw": self.power_kw,
            "duration_hours": self.duration_hours,
            "amount_kwh": self.energy_kwh,
            "units": self.units,
            "unit_size_wh": WH_PER_UNIT,
        }


def contract_from_kwh(amount_kwh: float, duration_hours: float = 1.0) -> EnergyContract:
    """Keep legacy kWh callers compatible while exposing the new contract."""
    if amount_kwh <= 0 or duration_hours <= 0:
        raise ValueError("Energy and duration must be greater than zero")
    return EnergyContract(
        power_kw=round(amount_kwh / duration_hours, 6),
        duration_hours=duration_hours,
    )
