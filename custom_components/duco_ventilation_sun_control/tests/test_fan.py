# === tests/test_fan.py ===
"""Test the Duco Ventilation System fan platform."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

# Import constants and types
from custom_components.duco_ventilation_sun_control.const import (
    ACTION_SET_OPER_STATE,
    ACTION_SET_OVERRULE,
    DOMAIN,
    DUCO_STATE_TO_PRESET_KEY, # Use the mapping
    HA_FAN_PRESET_MODE_KEYS, # Use the list of new keys
    NODE_INFO_KEY_DEVICE_TYPE,
    NODE_INFO_KEY_OVERRULE_PCT,
    NODE_INFO_KEY_STATE,
    NODE_INFO_KEY_TARGET_LEVEL,
    PRESET_KEY_AUTO, # New preset keys
    PRESET_KEY_AWAY,
    PRESET_KEY_HIGH_PERMANENT,
    PRESET_KEY_HIGH_TEMPORARY,
    PRESET_KEY_LOW_PERMANENT,
    PRESET_KEY_LOW_TEMPORARY,
    PRESET_KEY_MANUAL_OVERRIDE,
    PRESET_KEY_MEDIUM_PERMANENT,
    PRESET_KEY_MEDIUM_TEMPORARY,
    PRESET_KEY_TO_DUCO_STATE, # Use the mapping
    V1_CANCEL_OVERRULE_VALUE,
    DucoCoordinatorData,
    DucoNodeState, # Use Enum for states
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

# Expected fan entity ID based on naming convention and setup fixture
# Fan entity doesn't use hierarchical key, name comes from translation
FAN_ENTITY_ID = f"fan.ventilation"
BOX_NODE_ID = 1 # From fixture


async def test_fan_entity_creation_and_attributes(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_integration_v1: ConfigEntry
) -> None:
    """Test fan entity creation and basic attributes."""
    entry = entity_registry.async_get(FAN_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"duco_{setup_integration_v1.entry_id}_fan" # Fan unique ID is fixed
    assert entry.supported_features == (
        FanEntityFeature.PRESET_MODE | FanEntityFeature.SET_SPEED
    )
    # Assert uses the new preset keys list
    assert entry.preset_modes == HA_FAN_PRESET_MODE_KEYS

    state = hass.states.get(FAN_ENTITY_ID)
    assert state is not None
    # Initial state depends on mock data in setup_integration_v1 fixture
    # Assume initial state is AUTO, target 30% based on MOCK_RAW_NODEINFO_V1_BOX
    assert state.state == STATE_ON # AUTO is ON
    assert state.attributes.get(ATTR_PERCENTAGE) == 80 # actl from MOCK_RAW_NODEINFO_V1_BOX
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_KEY_AUTO


@pytest.mark.parametrize(
    "duco_state, overrule_pct, target_level, expected_state, expected_pct, expected_preset",
    [
        (DucoNodeState.AUTO, 0, 25, STATE_ON, 25, PRESET_KEY_AUTO),
        (DucoNodeState.AWAY, 0, 0, STATE_OFF, 0, PRESET_KEY_AWAY),
        (DucoNodeState.MANUAL_LOW, 0, 15, STATE_ON, 15, PRESET_KEY_LOW_TEMPORARY), # MAN1 maps to temp
        (DucoNodeState.TIMER_1, 0, 15, STATE_ON, 15, PRESET_KEY_LOW_PERMANENT), # CNT1 maps to perm
        (DucoNodeState.MANUAL_HIGH, 0, 90, STATE_ON, 90, PRESET_KEY_HIGH_TEMPORARY),
        (DucoNodeState.TIMER_3, 0, 90, STATE_ON, 90, PRESET_KEY_HIGH_PERMANENT),
        (DucoNodeState.AUTO, 60, 20, STATE_ON, 60, PRESET_KEY_MANUAL_OVERRIDE), # Overrule active
        (DucoNodeState.AWAY, 50, 0, STATE_ON, 50, PRESET_KEY_MANUAL_OVERRIDE), # Overrule active during Away
        (DucoNodeState.AUTO, None, 30, STATE_ON, 30, PRESET_KEY_AUTO), # No overrule data
        (DucoNodeState.AUTO, 0, None, STATE_ON, 10, PRESET_KEY_AUTO), # No target data, use fallback (assume 10%)
        (None, 0, 20, STATE_ON, 20, PRESET_KEY_AUTO), # No state data, assume auto
        (None, None, None, STATE_OFF, 0, PRESET_KEY_AWAY), # No data at all, assume Away
    ],
)
async def test_fan_state_mapping(
    hass: HomeAssistant,
    setup_integration_v1: ConfigEntry,
    duco_state, overrule_pct, target_level,
    expected_state, expected_pct, expected_preset
) -> None:
    """Test mapping of Duco states/overrule to HA fan state using new presets."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]

    new_box_node_info = MOCK_NODE_DATA_BOX["info"].copy()
    if duco_state is not None: new_box_node_info[NODE_INFO_KEY_STATE] = duco_state
    else: new_box_node_info.pop(NODE_INFO_KEY_STATE, None)
    if overrule_pct is not None: new_box_node_info[NODE_INFO_KEY_OVERRULE_PCT] = overrule_pct
    else: new_box_node_info.pop(NODE_INFO_KEY_OVERRULE_PCT, None)
    if target_level is not None: new_box_node_info[NODE_INFO_KEY_TARGET_LEVEL] = target_level
    else: new_box_node_info.pop(NODE_INFO_KEY_TARGET_LEVEL, None)

    # Mock fallback if needed
    patch_target = "custom_components.duco_ventilation_sun_control.fan.DucoFanEntity._calculate_expected_percentage"
    if target_level is None and duco_state is not None and duco_state != DucoNodeState.AWAY:
        with patch(patch_target, return_value=expected_pct):
            new_data = DucoCoordinatorData(
                device_info=coordinator.data.device_info, general_config=coordinator.data.general_config,
                nodes={str(BOX_NODE_ID): {"info": new_box_node_info, "config": coordinator.data.nodes.get(str(BOX_NODE_ID), {}).get("config", {})}},
                entities=[]
            )
            coordinator.async_set_updated_data(new_data)
            await hass.async_block_till_done()
    else:
        new_data = DucoCoordinatorData(
            device_info=coordinator.data.device_info, general_config=coordinator.data.general_config,
            nodes={str(BOX_NODE_ID): {"info": new_box_node_info, "config": coordinator.data.nodes.get(str(BOX_NODE_ID), {}).get("config", {})}},
            entities=[]
        )
        coordinator.async_set_updated_data(new_data)
        await hass.async_block_till_done()

    state = hass.states.get(FAN_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes.get(ATTR_PERCENTAGE) == expected_pct
    assert state.attributes.get(ATTR_PRESET_MODE) == expected_preset


async def test_fan_service_turn_on(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test turning the fan on using the turn_on service (defaults to Auto)."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    mock_api: MagicMock = coordinator.api

    # Set initial state to Off (Away)
    initial_data = DucoCoordinatorData(
        device_info=coordinator.data.device_info, general_config={},
        nodes={str(BOX_NODE_ID): {"info": {NODE_INFO_KEY_STATE: DucoNodeState.AWAY, NODE_INFO_KEY_OVERRULE_PCT: 0}, "config": {}}},
        entities=[] )
    coordinator.async_set_updated_data(initial_data); await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True )

    mock_api.perform_node_action.assert_has_awaits([
        call(BOX_NODE_ID, ACTION_SET_OPER_STATE, DucoNodeState.AUTO),
        call(BOX_NODE_ID, ACTION_SET_OVERRULE, V1_CANCEL_OVERRULE_VALUE), ])


async def test_fan_service_turn_off(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test turning the fan off using the turn_off service (sets Away)."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    mock_api: MagicMock = coordinator.api

    # Set initial state to On (Auto)
    initial_data = DucoCoordinatorData(
        device_info=coordinator.data.device_info, general_config={},
        nodes={str(BOX_NODE_ID): {"info": {NODE_INFO_KEY_STATE: DucoNodeState.AUTO, NODE_INFO_KEY_TARGET_LEVEL: 30, NODE_INFO_KEY_OVERRULE_PCT: 0}, "config": {}}},
        entities=[])
    coordinator.async_set_updated_data(initial_data); await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True)

    mock_api.perform_node_action.assert_has_awaits([
        call(BOX_NODE_ID, ACTION_SET_OPER_STATE, DucoNodeState.AWAY),
        call(BOX_NODE_ID, ACTION_SET_OVERRULE, V1_CANCEL_OVERRULE_VALUE), ])


async def test_fan_service_set_percentage(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test setting the fan speed using the set_percentage service."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    mock_api: MagicMock = coordinator.api

    percentage_to_set = 75
    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: percentage_to_set}, blocking=True)

    mock_api.perform_node_action.assert_awaited_once_with(BOX_NODE_ID, ACTION_SET_OVERRULE, percentage_to_set)

    mock_api.reset_mock()
    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_SET_PERCENTAGE, {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: 0}, blocking=True)

    mock_api.perform_node_action.assert_has_awaits([
        call(BOX_NODE_ID, ACTION_SET_OPER_STATE, DucoNodeState.AWAY),
        call(BOX_NODE_ID, ACTION_SET_OVERRULE, V1_CANCEL_OVERRULE_VALUE), ])


async def test_fan_service_set_preset_mode_new_keys(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test setting the fan speed using the set_preset_mode service with new keys."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    mock_api: MagicMock = coordinator.api

    # Test setting to High Temporary
    preset_to_set = PRESET_KEY_HIGH_TEMPORARY
    expected_duco_state = DucoNodeState.MANUAL_HIGH # Map temp preset to MANx state

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: preset_to_set}, blocking=True)

    mock_api.perform_node_action.assert_has_awaits([
        call(BOX_NODE_ID, ACTION_SET_OPER_STATE, expected_duco_state),
        call(BOX_NODE_ID, ACTION_SET_OVERRULE, V1_CANCEL_OVERRULE_VALUE), ])

    # Test setting to Medium Permanent
    mock_api.reset_mock()
    preset_to_set_perm = PRESET_KEY_MEDIUM_PERMANENT
    expected_duco_state_perm = DucoNodeState.TIMER_2 # Map perm preset to CNTx state

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: preset_to_set_perm}, blocking=True)

    mock_api.perform_node_action.assert_has_awaits([
        call(BOX_NODE_ID, ACTION_SET_OPER_STATE, expected_duco_state_perm),
        call(BOX_NODE_ID, ACTION_SET_OVERRULE, V1_CANCEL_OVERRULE_VALUE), ])


async def test_fan_service_set_manual_override_preset(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test setting the manual_override preset mode raises an error."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: PRESET_KEY_MANUAL_OVERRIDE},
            blocking=True)