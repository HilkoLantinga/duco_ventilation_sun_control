# === tests/test_number.py ===
"""Test the Duco Ventilation System number platform."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_VALUE, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

# Import constants and types
from custom_components.duco_ventilation_sun_control.const import (
    DOMAIN,
    KEY_MODULE_FAN, # Used in mapping paths
    KEY_MODULE_VENTCTRL,
    KEY_PARAM_AUTOMAX,
    KEY_PARAM_MAXHIGHLEVEL,
    KEY_PARAM_TEMPCTRLHIGH,
    NODE_CONFIG_KEY_MAX,
    NODE_CONFIG_KEY_MIN,
    NODE_CONFIG_KEY_STEP,
    NODE_CONFIG_KEY_VALUE,
    NODE_INFO_KEY_ASSO_ID,
    NODE_INFO_KEY_OVERRULE_PCT,
    NODE_INFO_KEY_PARENT_ID,
    V1_CANCEL_OVERRULE_VALUE,
    DucoCoordinatorData,
)
from custom_components.duco_ventilation_sun_control.coordinator import (
    DucoDataUpdateCoordinator,
)

# Import fixtures and mock data
from .conftest import (
    MOCK_SERIAL,
    MOCK_NODE_DATA_BOX,
    MOCK_NODE_DATA_SENSOR_CO2,
    setup_integration_v1,
)

# Platform for assertions
PLATFORM = Platform.NUMBER
BOX_NODE_ID = 1
CO2_NODE_ID = 137

# Example Entity IDs using NEW hierarchical keys
BOX_MAX_HIGH_ENTITY_ID = f"{PLATFORM}.config_box_fan_maxhighlevel"
BOX_TEMP_HIGH_ENTITY_ID = f"{PLATFORM}.config_box_ventctrl_tempctrlhigh"
NODE_OVERRULE_ENTITY_ID = f"{PLATFORM}.node_info_overrule_percentage" # Box node overrule
NODE_AUTO_MAX_ENTITY_ID = f"{PLATFORM}.config_automax" # Node config


async def test_number_entity_creation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_integration_v1: ConfigEntry
) -> None:
    """Test that number entities are created correctly with hierarchical keys."""
    # Check device number (box config)
    entry_max_high = entity_registry.async_get(BOX_MAX_HIGH_ENTITY_ID)
    assert entry_max_high is not None
    # Unique ID uses the hierarchical key now
    assert entry_max_high.unique_id == f"duco_{setup_integration_v1.entry_id}_config.box.fan.maxhighlevel"

    # Check box node number (overrule) - linked to main device, key is node.info.*
    entry_overrule = entity_registry.async_get(NODE_OVERRULE_ENTITY_ID)
    assert entry_overrule is not None
    # Box node entities use main device base ID + hierarchical key
    assert entry_overrule.unique_id == f"duco_{setup_integration_v1.entry_id}_node.info.overrule_percentage"

    # Check node number (node config) - linked to node device, key is config.*
    entry_auto_max = entity_registry.async_get(NODE_AUTO_MAX_ENTITY_ID)
    assert entry_auto_max is not None
    # Node entities use node base ID + hierarchical key
    assert entry_auto_max.unique_id == f"{MOCK_SERIAL}_node_{CO2_NODE_ID}_config.automax"


@pytest.mark.parametrize(
    "entity_id, data_source_key, data_path, value_key, initial_api_value, expected_initial_state",
    [
        # Test Device Number (Box Config) using new key structure
        (BOX_MAX_HIGH_ENTITY_ID, "general_config", ['box', KEY_MODULE_FAN, KEY_PARAM_MAXHIGHLEVEL], NODE_CONFIG_KEY_VALUE, 90, 90.0),
        (BOX_MAX_HIGH_ENTITY_ID, "general_config", ['box', KEY_MODULE_FAN, KEY_PARAM_MAXHIGHLEVEL], NODE_CONFIG_KEY_VALUE, None, None),
        # Test Device Number with Formatter using new key structure
        (BOX_TEMP_HIGH_ENTITY_ID, "general_config", ['box', KEY_MODULE_VENTCTRL, KEY_PARAM_TEMPCTRLHIGH], NODE_CONFIG_KEY_VALUE, 285, 28.5),
        # Test Node Number (Overrule) using new key structure
        (NODE_OVERRULE_ENTITY_ID, "info", [NODE_INFO_KEY_OVERRULE_PCT], None, 50, 50.0),
        (NODE_OVERRULE_ENTITY_ID, "info", [NODE_INFO_KEY_OVERRULE_PCT], None, 0, 0.0),
        (NODE_OVERRULE_ENTITY_ID, "info", [NODE_INFO_KEY_OVERRULE_PCT], None, None, 0.0), # Overrule None maps to 0%
        # Test Node Number (Node Config) using new key structure
        (NODE_AUTO_MAX_ENTITY_ID, "config", [KEY_PARAM_AUTOMAX], NODE_CONFIG_KEY_VALUE, 85, 85.0),
    ]
)
async def test_number_state_update(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry,
    entity_id: str, data_source_key: str, data_path: list[str], value_key: str | None,
    initial_api_value: Any, expected_initial_state: float | None
) -> None:
    """Test number entity state updates based on coordinator data with hierarchical keys."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]

    # --- Setup Initial State ---
    current_data = coordinator.data or DucoCoordinatorData()
    new_data = DucoCoordinatorData( # Create new data object
        device_info=current_data.device_info.copy(),
        general_config=current_data.general_config.copy(),
        nodes=current_data.nodes.copy(),
        entities=[] )

    # Determine target dictionary based on entity type/source key
    target_dict: Any
    node_id_str: str | None = None
    if data_source_key == "general_config":
        target_dict = new_data.general_config
    elif data_source_key == "info":
        node_id_str = str(BOX_NODE_ID) if entity_id == NODE_OVERRULE_ENTITY_ID else str(CO2_NODE_ID) # Adjust node ID based on entity
        if node_id_str not in new_data.nodes: new_data.nodes[node_id_str] = {"info": {}, "config": {}}
        target_dict = new_data.nodes[node_id_str]["info"]
    elif data_source_key == "config":
         node_id_str = str(CO2_NODE_ID) # Assume node config entities belong to CO2 node for this test
         if node_id_str not in new_data.nodes: new_data.nodes[node_id_str] = {"info": {}, "config": {}}
         target_dict = new_data.nodes[node_id_str]["config"]
    else:
         pytest.fail(f"Unhandled data_source_key in number state test setup: {data_source_key}")

    # Set the value at the specified path within the target dictionary
    current_level = target_dict
    for i, key in enumerate(data_path):
        if i == len(data_path) - 1: # Last key is the parameter name
            param_key = key
            if value_key: # Value is nested under value_key (e.g., "Val")
                if param_key not in current_level or not isinstance(current_level.get(param_key), dict):
                    current_level[param_key] = {}
                if initial_api_value is None:
                    current_level[param_key].pop(value_key, None)
                    # Remove parent key if empty
                    if not current_level[param_key]: current_level.pop(param_key, None)
                else:
                    current_level[param_key][value_key] = initial_api_value
            else: # Value is stored directly under the parameter name (info path)
                if initial_api_value is None:
                    current_level.pop(param_key, None)
                else:
                    current_level[param_key] = initial_api_value
        else: # Navigate/create intermediate dicts (e.g., area, module for general_config)
            if key not in current_level: current_level[key] = {}
            current_level = current_level[key]

    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    # Check state
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found after state update."
    if expected_initial_state is None:
        assert state.state == STATE_UNAVAILABLE
    else:
        assert float(state.state) == pytest.approx(expected_initial_state)


async def test_number_set_value_success(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test successfully setting a number value via service call with hierarchical keys."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]

    # --- Test setting device number (Box Config - MaxHigh) ---
    value_to_set = 88.0
    with patch.object(coordinator, "async_box_set_config") as mock_set_box_config:
        await hass.services.async_call(
            NUMBER_DOMAIN, SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: BOX_MAX_HIGH_ENTITY_ID, ATTR_VALUE: value_to_set}, blocking=True)
        await hass.async_block_till_done()
        mock_set_box_config.assert_awaited_once_with(KEY_MODULE_FAN, KEY_PARAM_MAXHIGHLEVEL, int(value_to_set)) # Uses original API params

    # --- Test setting device number with formatter (TempHigh * 10) ---
    mock_set_box_config.reset_mock()
    value_to_set_temp = 29.5; expected_api_temp = 295
    with patch.object(coordinator, "async_box_set_config") as mock_set_box_config:
        await hass.services.async_call(
            NUMBER_DOMAIN, SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: BOX_TEMP_HIGH_ENTITY_ID, ATTR_VALUE: value_to_set_temp}, blocking=True)
        await hass.async_block_till_done()
        mock_set_box_config.assert_awaited_once_with(KEY_MODULE_VENTCTRL, KEY_PARAM_TEMPCTRLHIGH, expected_api_temp)

    # --- Test setting node number (Overrule - special action) ---
    with patch.object(coordinator, "async_node_set_overrule") as mock_set_overrule:
        await hass.services.async_call(
            NUMBER_DOMAIN, SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: NODE_OVERRULE_ENTITY_ID, ATTR_VALUE: 65.0}, blocking=True)
        await hass.async_block_till_done()
        mock_set_overrule.assert_awaited_once_with(BOX_NODE_ID, 65)

    # Test setting overrule to 0
    mock_set_overrule.reset_mock()
    with patch.object(coordinator, "async_node_set_overrule") as mock_set_overrule:
        await hass.services.async_call(
            NUMBER_DOMAIN, SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: NODE_OVERRULE_ENTITY_ID, ATTR_VALUE: 0.0}, blocking=True)
        await hass.async_block_till_done()
        mock_set_overrule.assert_awaited_once_with(BOX_NODE_ID, V1_CANCEL_OVERRULE_VALUE)

    # --- Test setting node number (Node Config - AutoMax) ---
    with patch.object(coordinator, "async_node_set_config") as mock_set_node_config:
        await hass.services.async_call(
            NUMBER_DOMAIN, SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: NODE_AUTO_MAX_ENTITY_ID, ATTR_VALUE: 95.0}, blocking=True)
        await hass.async_block_till_done()
        # Verify coordinator call uses original API param name
        mock_set_node_config.assert_awaited_once_with(CO2_NODE_ID, KEY_PARAM_AUTOMAX, 95, module=KEY_PARAM_AUTOMAX)


async def test_number_set_value_api_error(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test error handling when API call fails during set_value."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    with patch.object(coordinator, "async_box_set_config", side_effect=HomeAssistantError("Simulated API fail")):
        with pytest.raises(HomeAssistantError) as excinfo:
            await hass.services.async_call(
                NUMBER_DOMAIN, SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: BOX_MAX_HIGH_ENTITY_ID, ATTR_VALUE: 80.0}, blocking=True)
        assert "Simulated API fail" in str(excinfo.value)


async def test_number_dynamic_range_update(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test that number entity range updates from coordinator data with hierarchical keys."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    entity_id = NODE_AUTO_MAX_ENTITY_ID # Node config number

    state_initial = hass.states.get(entity_id); assert state_initial is not None
    assert state_initial.attributes.get("min") == 0.0; assert state_initial.attributes.get("max") == 100.0; assert state_initial.attributes.get("step") == 1.0

    # Update coordinator data with new range
    current_data = coordinator.data or DucoCoordinatorData()
    new_nodes = current_data.nodes.copy()
    if str(CO2_NODE_ID) not in new_nodes: new_nodes[str(CO2_NODE_ID)] = {"info": {}, "config": {}}
    # Use the original API param key (KEY_PARAM_AUTOMAX) to update the mock config data
    new_nodes[str(CO2_NODE_ID)]["config"][KEY_PARAM_AUTOMAX] = {
        NODE_CONFIG_KEY_VALUE: 85, NODE_CONFIG_KEY_MIN: 10, NODE_CONFIG_KEY_MAX: 90, NODE_CONFIG_KEY_STEP: 5,
    }
    new_data = DucoCoordinatorData(device_info=current_data.device_info, general_config=current_data.general_config, nodes=new_nodes, entities=[])
    coordinator.async_set_updated_data(new_data); await hass.async_block_till_done()

    state_updated = hass.states.get(entity_id); assert state_updated is not None
    assert state_updated.attributes.get("min") == 10.0; assert state_updated.attributes.get("max") == 90.0; assert state_updated.attributes.get("step") == 5.0