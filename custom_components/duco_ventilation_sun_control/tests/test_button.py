# === tests/test_button.py ===
"""Test the Duco Ventilation System button platform."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

# Import constants and types
from custom_components.duco_ventilation_sun_control.const import (
    ACTION_CLEAR_NETWORK,
    ACTION_LOAD_DEFAULTS_NODE,
    ACTION_REBOOT_DEVICE,
    ACTION_RESET_NODE,
    ACTION_SET_CALIBRATION, # For parameters
    ACTION_SET_OVERRULE,    # For parameters
    DOMAIN,
    V1_CANCEL_OVERRULE_VALUE, # Parameter for clear overrule action
    DucoCalibCommand, # Enum for calibration params
)
from custom_components.duco_ventilation_sun_control.coordinator import (
    DucoDataUpdateCoordinator,
)

# Import fixtures and mock data
from .conftest import (
    MOCK_SERIAL,
    MOCK_NODE_DATA_SENSOR_RH, # Use node for node button tests
    setup_integration_v1,
)

# Platform for assertions
PLATFORM = Platform.BUTTON
RH_NODE_ID = 138 # Assume node 138 is RH sensor in test data

# Example Entity IDs using NEW action-based hierarchical keys
CLEAR_NETWORK_ENTITY_ID = f"{PLATFORM}.action_clear_network"
REBOOT_ENTITY_ID = f"{PLATFORM}.action_reboot"
START_CALIB_ENTITY_ID = f"{PLATFORM}.action_calibration_start"
NODE_CLEAR_OVERRULE_ENTITY_ID = f"{PLATFORM}.action_overrule_clear" # Node button
NODE_LOAD_DEFAULTS_ENTITY_ID = f"{PLATFORM}.action_load_defaults" # Node button


async def test_button_entity_creation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_integration_v1: ConfigEntry
) -> None:
    """Test that button entities are created correctly with hierarchical keys."""
    # Check device buttons
    entry_clear = entity_registry.async_get(CLEAR_NETWORK_ENTITY_ID)
    assert entry_clear is not None
    assert entry_clear.unique_id == f"duco_{setup_integration_v1.entry_id}_{ACTION_CLEAR_NETWORK}" # Uses action constant as key part

    entry_reboot = entity_registry.async_get(REBOOT_ENTITY_ID)
    assert entry_reboot is not None
    assert entry_reboot.unique_id == f"duco_{setup_integration_v1.entry_id}_{ACTION_REBOOT_DEVICE}"

    entry_start_calib = entity_registry.async_get(START_CALIB_ENTITY_ID)
    assert entry_start_calib is not None
    assert entry_start_calib.unique_id == f"duco_{setup_integration_v1.entry_id}_action.calibration.start" # Uses custom action key

    # Check node buttons (assume node 138 is present from setup)
    entry_clear_ovr = entity_registry.async_get(NODE_CLEAR_OVERRULE_ENTITY_ID)
    assert entry_clear_ovr is not None
    assert entry_clear_ovr.unique_id == f"{MOCK_SERIAL}_node_{RH_NODE_ID}_action.overrule.clear"

    entry_load_def = entity_registry.async_get(NODE_LOAD_DEFAULTS_ENTITY_ID)
    assert entry_load_def is not None
    assert entry_load_def.unique_id == f"{MOCK_SERIAL}_node_{RH_NODE_ID}_{ACTION_LOAD_DEFAULTS_NODE}"


@pytest.mark.parametrize(
    "entity_id, coordinator_method_name, expected_call_args",
    [
        # Device Buttons
        (CLEAR_NETWORK_ENTITY_ID, "async_box_clear_network", ()),
        (REBOOT_ENTITY_ID, "async_board_reset", ()),
        (START_CALIB_ENTITY_ID, "async_box_set_calibration", (DucoCalibCommand.START.value,)),
        # Node Buttons (RH_NODE_ID = 138 assumed)
        (NODE_CLEAR_OVERRULE_ENTITY_ID, "async_node_set_overrule", (RH_NODE_ID, V1_CANCEL_OVERRULE_VALUE)),
        (NODE_LOAD_DEFAULTS_ENTITY_ID, "async_node_load_defaults", (RH_NODE_ID,)),
    ]
)
async def test_button_press_success(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry,
    entity_id: str, coordinator_method_name: str, expected_call_args: tuple
) -> None:
    """Test pressing buttons successfully triggers coordinator actions."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]

    # Ensure the entity exists before pressing
    assert hass.states.get(entity_id) is not None

    # Patch the specific coordinator method expected to be called
    coordinator_method_to_patch = getattr(coordinator, coordinator_method_name)
    assert callable(coordinator_method_to_patch)

    with patch.object(coordinator, coordinator_method_name, wraps=coordinator_method_to_patch) as patched_method:
        # Press the button
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        await hass.async_block_till_done()

        # Assert the coordinator method was called with correct args
        patched_method.assert_awaited_once_with(*expected_call_args)


async def test_button_press_api_error(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test error handling when API call fails during button press."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]

    # Patch the coordinator method to simulate failure
    with patch.object(coordinator, "async_board_reset", side_effect=HomeAssistantError("Simulated API fail")):
        with pytest.raises(HomeAssistantError) as excinfo:
            await hass.services.async_call(
                BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: REBOOT_ENTITY_ID}, blocking=True
            )
        # Check if the error propagated (HA service call wrapper might add details)
        # Direct assertion on the raised error might be needed if HA wraps it differently
        assert "Simulated API fail" in str(excinfo.getrepr()) # Check representation