# === tests/test_switch.py ===
"""Test the Duco Ventilation System switch platform."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

# Import constants and types
from custom_components.duco_ventilation_sun_control.const import (
    ACTION_SET_INSTALLER_MODE,
    ACTION_SET_LINK_MODE,
    ACTION_SET_SHOW,
    DEVICE_INFO_KEY_INSTALLER_STATE,
    DOMAIN,
    KEY_MODULE_FAN, # Example module
    KEY_MODULE_TIME,
    KEY_PARAM_AUTO_DST,
    KEY_PARAM_RHDELTA,
    NODE_CONFIG_KEY_VALUE,
    NODE_INFO_KEY_LINK,
    NODE_INFO_KEY_SHOW,
    DucoCoordinatorData,
)
from custom_components.duco_ventilation_sun_control.coordinator import (
    DucoDataUpdateCoordinator,
)

# Import fixtures and mock data
from .conftest import (
    MOCK_SERIAL,
    MOCK_NODE_DATA_BOX,
    MOCK_NODE_DATA_SENSOR_RH,
    setup_integration_v1,
)

# Platform for assertions
PLATFORM = Platform.SWITCH
BOX_NODE_ID = 1
RH_NODE_ID = 138

# Example Entity IDs using NEW hierarchical keys
INSTALLER_MODE_ENTITY_ID = f"{PLATFORM}.action_installer_mode_toggle" # Action-based key
AUTO_DST_ENTITY_ID = f"{PLATFORM}.config_box_time_autodst" # Config-based key
NODE_LINK_MODE_ENTITY_ID = f"{PLATFORM}.action_link_mode_toggle" # Action-based key for node
NODE_RH_DELTA_ENTITY_ID = f"{PLATFORM}.config_rh_delta" # Config-based key for node


async def test_switch_entity_creation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_integration_v1: ConfigEntry
) -> None:
    """Test that switch entities are created correctly with hierarchical keys."""
    # Check device switch (installer mode - action based)
    entry_installer = entity_registry.async_get(INSTALLER_MODE_ENTITY_ID)
    assert entry_installer is not None
    assert entry_installer.unique_id == f"duco_{setup_integration_v1.entry_id}_action.installer_mode.toggle"

    # Check device switch (box config)
    entry_autodst = entity_registry.async_get(AUTO_DST_ENTITY_ID)
    assert entry_autodst is not None
    assert entry_autodst.unique_id == f"duco_{setup_integration_v1.entry_id}_config.box.time.autodst"

    # Check node switch (link mode - action based) - Assumes node 138 setup
    entry_link = entity_registry.async_get(NODE_LINK_MODE_ENTITY_ID)
    assert entry_link is not None
    assert entry_link.unique_id == f"{MOCK_SERIAL}_node_{RH_NODE_ID}_action.link_mode.toggle"

    # Check node switch (node config)
    entry_rhdelta = entity_registry.async_get(NODE_RH_DELTA_ENTITY_ID)
    assert entry_rhdelta is not None
    assert entry_rhdelta.unique_id == f"{MOCK_SERIAL}_node_{RH_NODE_ID}_config.rh.delta"


@pytest.mark.parametrize(
    "entity_id, entity_key, data_source_key, data_path, value_key, initial_api_value, on_value, expected_initial_state, service_to_call, coordinator_method_name, expected_api_call_args",
    [
        # Test Device Switch (Installer Mode - action based, reads from device_info)
        (INSTALLER_MODE_ENTITY_ID, "action.installer_mode.toggle", "device_info", [DEVICE_INFO_KEY_INSTALLER_STATE], None, "OPERATIONAL", "INSTALLER", STATE_OFF, SERVICE_TURN_ON, "async_box_toggle_installer_mode", (True,)),
        (INSTALLER_MODE_ENTITY_ID, "action.installer_mode.toggle", "device_info", [DEVICE_INFO_KEY_INSTALLER_STATE], None, "INSTALLER", "INSTALLER", STATE_ON, SERVICE_TURN_OFF, "async_box_toggle_installer_mode", (False,)),
        # Test Device Switch (Box Config - AutoDST)
        (AUTO_DST_ENTITY_ID, "config.box.time.autodst", "general_config", ['box', KEY_MODULE_TIME, KEY_PARAM_AUTO_DST], NODE_CONFIG_KEY_VALUE, 0, 1, STATE_OFF, SERVICE_TURN_ON, "async_box_set_config", (KEY_MODULE_TIME, KEY_PARAM_AUTO_DST, 1)),
        (AUTO_DST_ENTITY_ID, "config.box.time.autodst", "general_config", ['box', KEY_MODULE_TIME, KEY_PARAM_AUTO_DST], NODE_CONFIG_KEY_VALUE, 1, 1, STATE_ON, SERVICE_TURN_OFF, "async_box_set_config", (KEY_MODULE_TIME, KEY_PARAM_AUTO_DST, 0)),
        # Test Node Switch (Link Mode - action based, reads from node info)
        (NODE_LINK_MODE_ENTITY_ID, "action.link_mode.toggle", "info", [NODE_INFO_KEY_LINK], None, 0, 1, STATE_OFF, SERVICE_TURN_ON, "async_node_set_link_mode", (RH_NODE_ID, True)),
        (NODE_LINK_MODE_ENTITY_ID, "action.link_mode.toggle", "info", [NODE_INFO_KEY_LINK], None, 1, 1, STATE_ON, SERVICE_TURN_OFF, "async_node_set_link_mode", (RH_NODE_ID, False)),
        # Test Node Switch (Node Config - RHDelta)
        (NODE_RH_DELTA_ENTITY_ID, "config.rh.delta", "config", [KEY_PARAM_RHDELTA], NODE_CONFIG_KEY_VALUE, 0, 1, STATE_OFF, SERVICE_TURN_ON, "async_node_set_config", (RH_NODE_ID, KEY_PARAM_RHDELTA, 1, KEY_PARAM_RHDELTA)),
        (NODE_RH_DELTA_ENTITY_ID, "config.rh.delta", "config", [KEY_PARAM_RHDELTA], NODE_CONFIG_KEY_VALUE, 1, 1, STATE_ON, SERVICE_TURN_OFF, "async_node_set_config", (RH_NODE_ID, KEY_PARAM_RHDELTA, 0, KEY_PARAM_RHDELTA)),
    ]
)
async def test_switch_state_and_control(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry,
    entity_id: str, entity_key: str, data_source_key: str, data_path: list[str], value_key: str | None,
    initial_api_value: Any, on_value: Any, expected_initial_state: str,
    service_to_call: str, coordinator_method_name: str, expected_api_call_args: tuple
) -> None:
    """Test switch state updates and service calls with hierarchical keys."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    mock_api: MagicMock = coordinator.api # Although not directly used here, used by coordinator methods

    # --- Setup Initial State ---
    current_data = coordinator.data or DucoCoordinatorData()
    new_data = DucoCoordinatorData(
        device_info=current_data.device_info.copy(),
        general_config=current_data.general_config.copy(),
        nodes=current_data.nodes.copy(),
        entities=[] )

    # Place initial value in the correct location based on data_source_key
    target_dict: Any
    node_id_str: str | None = None

    if data_source_key == "device_info": target_dict = new_data.device_info
    elif data_source_key == "general_config": target_dict = new_data.general_config
    elif data_source_key == "info":
        node_id_str = str(RH_NODE_ID) # Assuming node switches are on RH node for this test
        if node_id_str not in new_data.nodes: new_data.nodes[node_id_str] = {"info": {}, "config": {}}
        target_dict = new_data.nodes[node_id_str]["info"]
    elif data_source_key == "config":
        node_id_str = str(RH_NODE_ID)
        if node_id_str not in new_data.nodes: new_data.nodes[node_id_str] = {"info": {}, "config": {}}
        target_dict = new_data.nodes[node_id_str]["config"]
    else: pytest.fail(f"Unhandled data_source_key in switch state test setup: {data_source_key}")

    # Set the value at the specified path within the target dictionary
    current_level = target_dict
    for i, key in enumerate(data_path):
        if i == len(data_path) - 1:
            param_key = key
            if value_key: # Nested under value_key
                if param_key not in current_level or not isinstance(current_level.get(param_key), dict): current_level[param_key] = {}
                if initial_api_value is None: current_level[param_key].pop(value_key, None); \
                    if not current_level[param_key]: current_level.pop(param_key, None)
                else: current_level[param_key][value_key] = initial_api_value
            else: # Direct value
                if initial_api_value is None: current_level.pop(param_key, None)
                else: current_level[param_key] = initial_api_value
        else:
            if key not in current_level: current_level[key] = {}
            current_level = current_level[key]

    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    # Check initial state
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found after state update."
    assert state.state == expected_initial_state

    # --- Test Service Call ---
    coordinator_method_to_patch = getattr(coordinator, coordinator_method_name)
    assert callable(coordinator_method_to_patch)

    with patch.object(coordinator, coordinator_method_name, wraps=coordinator_method_to_patch) as patched_method:
        await hass.services.async_call( SWITCH_DOMAIN, service_to_call, {ATTR_ENTITY_ID: entity_id}, blocking=True )
        await hass.async_block_till_done()
        patched_method.assert_awaited_once_with(*expected_api_call_args)


async def test_switch_api_error(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test error handling when API call fails during switch toggle."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    with patch.object(coordinator, "async_box_toggle_installer_mode", side_effect=HomeAssistantError("Simulated API fail")):
        with pytest.raises(HomeAssistantError) as excinfo:
            await hass.services.async_call( SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: INSTALLER_MODE_ENTITY_ID}, blocking=True )
        assert "Simulated API fail" in str(excinfo.value)