import pytest
import voluptuous as vol

from component_loader import load_component_module

const = load_component_module("const")
schemas = load_component_module("schemas")


def test_default_utility_types_are_electric_only():
    assert const.DEFAULT_UTILITY_TYPES == ["ELECTRIC"]


def test_refresh_data_schema_accepts_optional_entry_id():
    assert schemas.SERVICE_REFRESH_DATA_SCHEMA({}) == {}
    assert schemas.SERVICE_REFRESH_DATA_SCHEMA({"entry_id": "abc123"}) == {
        "entry_id": "abc123"
    }


def test_clear_statistics_requires_explicit_confirmation():
    with pytest.raises(vol.Invalid):
        schemas.SERVICE_CLEAR_STATISTICS_SCHEMA({})

    with pytest.raises(vol.Invalid):
        schemas.SERVICE_CLEAR_STATISTICS_SCHEMA({"confirm_rebuild": False})

    assert schemas.SERVICE_CLEAR_STATISTICS_SCHEMA({"confirm_rebuild": True}) == {
        "confirm_rebuild": True
    }


def test_clear_statistics_accepts_entry_id_with_confirmation():
    assert schemas.SERVICE_CLEAR_STATISTICS_SCHEMA(
        {"entry_id": "abc123", "confirm_rebuild": True}
    ) == {"entry_id": "abc123", "confirm_rebuild": True}
