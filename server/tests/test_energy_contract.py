import pytest

from market.energy_contract import EnergyContract, contract_from_kwh


def test_power_duration_derives_energy_and_units():
    contract = EnergyContract(power_kw=2.5, duration_hours=2)

    assert contract.energy_kwh == 5
    assert contract.units == 500
    assert contract.as_dict()["unit_size_wh"] == 10


def test_legacy_kwh_conversion_preserves_energy():
    contract = contract_from_kwh(1.5, duration_hours=0.5)

    assert contract.power_kw == 3
    assert contract.energy_kwh == 1.5


def test_invalid_contract_is_rejected():
    with pytest.raises(ValueError):
        EnergyContract(power_kw=0, duration_hours=1)
