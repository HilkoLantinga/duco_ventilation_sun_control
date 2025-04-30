# === tests/test_select.py ===
"""Test the Duco Ventilation System select platform."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN, SERVICE_SELECT_OPTION
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, STATE_UNAVAILABLE, Platform, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

# Import constants and types
from custom_components.duco_ventilation_sun_control.const import (
    ACTION_SET_CALIBRATION,
    ACTION_SET_OPER_STATE,
    ALL_CALIBRATION_COMMANDS,
    ALL_NODE_STATES,
    DEVICE_INFO_KEY_CALIB_STATE,
    DOMAIN,
    KEY_MODULE_NIGHTBOOST,
    KEY_MODULE_VENTCOOL,
    KEY_PARAM_NB_STARTMONTH,
    KEY_PARAM_VC_MODE,
    MONTH_MAP,
    MONTH_MAP_INV,
    NODE_CONFIG_KEY_VALUE,
    NODE_INFO_KEY_STATE,
    VENTCOOL_MODE_MAP,
    VENTCOOL_MODE_MAP_INV,
    DucoCoordinatorData,
    DucoCalibCommand,
    DucoNodeState,
)
from custom_components.duco_ventilation_sun_control.coordinator import (
    DucoDataUpdateCoordinator,
)

# Import fixtures and mock data
from .conftest import (
    MOCK_SERIAL,
    MOCK_NODE_DATA_BOX,
    setup_integration_v1,
)

# Platform for assertions
PLATFORM = Platform.SELECT
BOX_NODE_ID = 1

# Example Entity IDs using NEW hierarchical keys
CALIB_COMMAND_ENTITY_ID = f"{PLATFORM}.action_calibration_command"
NB_START_MONTH_ENTITY_ID = f"{PLATFORM}.config_box_nightboost_startmonth"
VC_MODE_ENTITY_ID = f"{PLATFORM}.config_box_ventcool_mode"
NODE_STATE_ENTITY_ID = f"{PLATFORM}.node_info_state" # Box node state


async def test_select_entity_creation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_integration_v1: ConfigEntry
) -> None:
    """Test that select entities are created correctly with hierarchical keys."""
    # Check device selects
    entry_calib = entity_registry.async_get(CALIB_COMMAND_ENTITY_ID)
    assert entry_calib is not None
    assert entry_calib.unique_id == f"duco_{setup_integration_v1.entry_id}_action.calibration_command"
    assert sorted(entry_calib.capabilities["options"]) == sorted(ALL_CALIBRATION_COMMANDS)

    entry_month = entity_registry.async_get(NB_START_MONTH_ENTITY_ID)
    assert entry_month is not None
    assert entry_month.unique_id == f"duco_{setup_integration_v1.entry_id}_config.box.nightboost.startmonth"
    assert sorted(entry_month.capabilities["options"]) == sorted(list(MONTH_MAP.values()))

    entry_vc = entity_registry.async_get(VC_MODE_ENTITY_ID)
    assert entry_vc is not None
    assert entry_vc.unique_id == f"duco_{setup_integration_v1.entry_id}_config.box.ventcool.mode"
    assert sorted(entry_vc.capabilities["options"]) == sorted(list(VENTCOOL_MODE_MAP.values()))

    # Check node select (box node state)
    entry_node_state = entity_registry.async_get(NODE_STATE_ENTITY_ID)
    assert entry_node_state is not None
    assert entry_node_state.unique_id == f"duco_{setup_integration_v1.entry_id}_node.info.state"
    assert sorted(entry_node_state.capabilities["options"]) == sorted(ALL_NODE_STATES)


@pytest.mark.parametrize(
    "entity_id, data_source_key, data_path, value_key, initial_api_value, expected_initial_state",
    [
        # Test Device Select (Month - uses mapping) using new key structure
        (NB_START_MONTH_ENTITY_ID, "general_config", ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STARTMONTH], NODE_CONFIG_KEY_VALUE, 5, "May"),
        (NB_START_MONTH_ENTITY_ID, "general_config", ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STARTMONTH], NODE_CONFIG_KEY_VALUE, None, None),
        # Test Device Select (VC Mode - uses mapping) using new key structure
        (VC_MODE_ENTITY_ID, "general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_MODE], NODE_CONFIG_KEY_VALUE, 2, "Automatic"),
        (VC_MODE_ENTITY_ID, "general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_MODE], NODE_CONFIG_KEY_VALUE, 0, "Not Activated"),
        # Test Node Select (Node State - direct value) using new key structure
        (NODE_STATE_ENTITY_ID, "info", [NODE_INFO_KEY_STATE], None, "AUTO", "AUTO"),
        (NODE_STATE_ENTITY_ID, "info", [NODE_INFO_KEY_STATE], None, "MAN2", "MAN2"),
        # Test Calibration Command (Action only - should always be None/Unknown/Unavailable) using new key structure
        (CALIB_COMMAND_ENTITY_ID, "device_info", [DEVICE_INFO_KEY_CALIB_STATE], None, "IDLE", None),
    ]
)
async def test_select_state_update(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry,
    entity_id: str, data_source_key: str, data_path: list[str], value_key: str | None,
    initial_api_value: Any, expected_initial_state: str | None
) -> None:
    """Test select entity state updates based on coordinator data with hierarchical keys."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]

    # --- Setup Initial State ---
    current_data = coordinator.data or DucoCoordinatorData()
    new_data = DucoCoordinatorData(
        device_info=current_data.device_info.copy(),
        general_config=current_data.general_config.copy(),
        nodes=current_data.nodes.copy(),
        entities=[] )

    # Place initial value in the correct location based on data_source_key
    target_dict: Any
    if data_source_key == "general_config": target_dict = new_data.general_config
    elif data_source_key == "info": # Node state comes from Box Node info
        if str(BOX_NODE_ID) not in new_data.nodes: new_data.nodes[str(BOX_NODE_ID)] = {"info": {}, "config": {}}
        target_dict = new_data.nodes[str(BOX_NODE_ID)]["info"]
    elif data_source_key == "device_info": # Calibration state from device_info
        target_dict = new_data.device_info
    else: pytest.fail(f"Unhandled data_source_key in select state test setup: {data_source_key}")

    # Set the value at the specified path within the target dictionary
    current_level = target_dict
    for i, key in enumerate(data_path):
         if i == len(data_path) - 1: # Last key is the parameter name
             param_key = key
             if value_key: # Value is nested under value_key
                 if param_key not in current_level or not isinstance(current_level.get(param_key), dict): current_level[param_key] = {}
                 if initial_api_value is None: current_level[param_key].pop(value_key, None); \
                     if not current_level[param_key]: current_level.pop(param_key, None)
                 else: current_level[param_key][value_key] = initial_api_value
             else: # Value stored directly under the key (info path)
                 if initial_api_value is None: current_level.pop(param_key, None)
                 else: current_level[param_key] = initial_api_value
         else: # Navigate/create intermediate dicts
             if key not in current_level: current_level[key] = {}
             current_level = current_level[key]

    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    # Check state
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found after state update."
    if expected_initial_state is None:
        assert state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) # Use HA const for unknown/unavailable
    else:
        assert state.state == expected_initial_state


async def test_select_select_option_success(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test successfully selecting an option via service call with hierarchical keys."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]

    # --- Test setting device select (Month) ---
    option_to_select = "July"; expected_api_value = MONTH_MAP_INV[option_to_select]
    with patch.object(coordinator, "async_box_set_config") as mock_set_box_config:
        await hass.services.async_call( SELECT_DOMAIN, SERVICE_SELECT_OPTION, {ATTR_ENTITY_ID: NB_START_MONTH_ENTITY_ID, ATTR_OPTION: option_to_select}, blocking=True)
        await hass.async_block_till_done()
        mock_set_box_config.assert_awaited_once_with(KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STARTMONTH, expected_api_value)

    # --- Test setting device select (VC Mode) ---
    mock_set_box_config.reset_mock()
    option_to_select_vc = "Time Controlled"; expected_api_value_vc = VENTCOOL_MODE_MAP_INV[option_to_select_vc]
    with patch.object(coordinator, "async_box_set_config") as mock_set_box_config:
        await hass.services.async_call( SELECT_DOMAIN, SERVICE_SELECT_OPTION, {ATTR_ENTITY_ID: VC_MODE_ENTITY_ID, ATTR_OPTION: option_to_select_vc}, blocking=True)
        await hass.async_block_till_done()
        mock_set_box_config.assert_awaited_once_with(KEY_MODULE_VENTCOOL, KEY_PARAM_VC_MODE, expected_api_value_vc)

    # --- Test setting device select (Calibration Command - special action) ---
    with patch.object(coordinator, "async_box_set_calibration") as mock_set_calib:
        await hass.services.async_call( SELECT_DOMAIN, SERVICE_SELECT_OPTION, {ATTR_ENTITY_ID: CALIB_COMMAND_ENTITY_ID, ATTR_OPTION: DucoCalibCommand.VERIFY_LOW.value}, blocking=True)
        await hass.async_block_till_done()
        mock_set_calib.assert_awaited_once_with(DucoCalibCommand.VERIFY_LOW.value)

    # --- Test setting node select (Node State - special action) ---
    with patch.object(coordinator, "async_node_set_operation_state") as mock_set_node_state:
        await hass.services.async_call( SELECT_DOMAIN, SERVICE_SELECT_OPTION, {ATTR_ENTITY_ID: NODE_STATE_ENTITY_ID, ATTR_OPTION: DucoNodeState.MANUAL_HIGH.value}, blocking=True) # Use Enum value
        await hass.async_block_till_done()
        mock_set_node_state.assert_awaited_once_with(BOX_NODE_ID, DucoNodeState.MANUAL_HIGH.value)


async def test_select_select_option_invalid(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test selecting an invalid option."""
    with pytest.raises(ValueError):
         await hass.services.async_call( SELECT_DOMAIN, SERVICE_SELECT_OPTION, {ATTR_ENTITY_ID: NODE_STATE_ENTITY_ID, ATTR_OPTION: "INVALID_STATE"}, blocking=True)


async def test_select_select_option_api_error(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test error handling when API call fails during select_option."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    with patch.object(coordinator, "async_box_set_config", side_effect=HomeAssistantError("Simulated API fail")):
        with pytest.raises(HomeAssistantError) as excinfo:
            await hass.services.async_call( SELECT_DOMAIN, SERVICE_SELECT_OPTION, {ATTR_ENTITY_ID: NB_START_MONTH_ENTITY_ID, ATTR_OPTION: "January"}, blocking=True)
        assert isinstance(excinfo.value, HomeAssistantError)