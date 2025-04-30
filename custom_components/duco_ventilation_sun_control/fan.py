# === custom_components/duco_ventilation_sun_control/fan.py ===
"""Platform setup for the Duco fan entity."""

from __future__ import annotations

import logging
import math
from typing import Any, Final, Optional, cast

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Local integration imports
from .const import (
    DOMAIN,
    DUCO_STATE_TO_PRESET_KEY,
    HA_FAN_PRESET_MODE_KEYS,
    IdentifiedEntity,
    KEY_PARAM_AUTOMIN,
    KEY_PARAM_MANUAL1,
    KEY_PARAM_MANUAL2,
    KEY_PARAM_MANUAL3,
    NODE_CONFIG_KEY_VALUE,
    NODE_INFO_KEY_OVERRULE_PCT,
    NODE_INFO_KEY_SENSOR_DEMAND,
    NODE_INFO_KEY_STATE,
    NODE_INFO_KEY_TARGET_LEVEL,
    NODE_STATE_AUTO,
    NODE_STATE_AWAY,
    NODE_STATE_MANUAL_HIGH,
    NODE_STATE_MANUAL_LOW,
    NODE_STATE_MANUAL_MEDIUM,
    NODE_STATE_TIMER_1,
    NODE_STATE_TIMER_2,
    NODE_STATE_TIMER_3,
    PRESET_KEY_AWAY,
    PRESET_KEY_MANUAL_SPEED,
    PRESET_KEY_TO_DUCO_STATE,
    V1_CANCEL_OVERRULE_VALUE, # Needed for cancelling overrule
)
from .coordinator import DucoDataUpdateCoordinator
from .entity import DucoBoxNodeEntity # Fan entity is linked to the Box Node

_LOGGER = logging.getLogger(__name__)

# Define supported features for the fan entity
SUPPORTED_FAN_FEATURES: Final = (
    FanEntityFeature.PRESET_MODE | FanEntityFeature.SET_SPEED
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Duco fan entity based on identified entities."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    identified_entities: list[IdentifiedEntity] = []
    if coordinator.data and hasattr(coordinator.data, "entities"):
        identified_entities = coordinator.data.entities
    else:
        _LOGGER.warning("Coordinator data or entities list not available during fan setup")
        return

    entities_to_add: list[FanEntity] = []
    for identified_entity in identified_entities:
        # Look for the fan entity specifically marked as the box node entity
        if (
            identified_entity.platform == Platform.FAN
            and identified_entity.is_box_node_entity
        ):
            node_id = identified_entity.node_id
            if node_id is not None:
                entities_to_add.append(DucoFanEntity(coordinator, node_id))
                _LOGGER.info("Adding Duco Fan entity for box node %d", node_id)
                break # Assume only one main fan entity per device
            else:
                _LOGGER.error("Identified Fan entity is missing required node_id.")

    if entities_to_add:
        async_add_entities(entities_to_add)
    else:
        _LOGGER.warning("No box node fan entity was identified for setup.")


class DucoFanEntity(DucoBoxNodeEntity[DucoDataUpdateCoordinator], FanEntity):
    """Represents the main DucoBox ventilation fan control entity."""

    _attr_should_poll = False # State updates are handled by the coordinator
    _attr_translation_key = "ventilation" # Use translation key for name/attributes
    entity_description = EntityDescription(key="fan") # Basic entity description
    _attr_supported_features = SUPPORTED_FAN_FEATURES
    _attr_preset_modes = HA_FAN_PRESET_MODE_KEYS

    # Internal HA state attributes
    _attr_is_on: bool | None = None
    _attr_percentage: int | None = None
    _attr_preset_mode: str | None = None

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int, # Box node ID
    ) -> None:
        """Initialize the Duco fan entity."""
        _LOGGER.debug("Node %s (Fan Entity): Initializing...", node_id)
        # Map info is None for the fan entity as it derives state complexly
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=None)
        self._duco_platform = Platform.FAN # Identify platform for base class
        # Use the main device unique ID as the base for the fan
        self._attr_unique_id = f"{self._entry_unique_id_base}_fan"

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        # Calculate initial state after coordinator linking
        if self.coordinator.data:
            _LOGGER.debug("Node %s (Fan Entity): Calculating initial state.", self._box_node_id)
            self._update_internal_state_from_coordinator()
        else:
            _LOGGER.warning("Node %s (Fan Entity): Coordinator data missing at add time.", self._box_node_id)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports (0-100 range)."""
        return 100 # Standard percentage range

    def _calculate_expected_percentage(self, duco_state_code: str | None) -> int:
        """Estimate percentage based on sensor demand and preset levels (fallback)."""
        if not self.coordinator.data or not self.coordinator.data.nodes:
            return 0

        # Find maximum sensor demand across all nodes
        max_sensor_demand = 0
        for node_data in self.coordinator.data.nodes.values():
            sensor_value = node_data.get("info", {}).get(NODE_INFO_KEY_SENSOR_DEMAND)
            if sensor_value is not None:
                try:
                    max_sensor_demand = max(max_sensor_demand, int(float(sensor_value)))
                except (ValueError, TypeError):
                    pass # Ignore invalid sensor values

        # Get configured level for the current Duco state
        preset_config_level = 0
        config_key: str | None = None
        if duco_state_code == NODE_STATE_AUTO:
            config_key = KEY_PARAM_AUTOMIN
        elif duco_state_code in (NODE_STATE_MANUAL_LOW, NODE_STATE_TIMER_1):
            config_key = KEY_PARAM_MANUAL1
        elif duco_state_code in (NODE_STATE_MANUAL_MEDIUM, NODE_STATE_TIMER_2):
            config_key = KEY_PARAM_MANUAL2
        elif duco_state_code in (NODE_STATE_MANUAL_HIGH, NODE_STATE_TIMER_3):
            config_key = KEY_PARAM_MANUAL3
        # Ignore MANx states for fallback calculation for simplicity

        if config_key:
            # Access box node config data directly
            config_data = self.box_node_config_data.get(config_key, {})
            config_value = config_data.get(NODE_CONFIG_KEY_VALUE)
            try:
                preset_config_level = int(float(config_value)) if config_value is not None else 0
            except (ValueError, TypeError):
                preset_config_level = 0

        # Estimated percentage is the higher of sensor demand or preset config level
        estimated_pct = max(max_sensor_demand, preset_config_level)
        clamped_pct = max(0, min(100, estimated_pct)) # Clamp to 0-100 range

        _LOGGER.debug(
            "Node %s (Fan): Fallback pct calc: DucoState=%s, MaxSensor=%s, PresetLevel=%s -> Clamped=%s",
            self._box_node_id, duco_state_code, max_sensor_demand, preset_config_level, clamped_pct
        )
        return clamped_pct

    def _update_internal_state_from_coordinator(self) -> bool:
        """Update internal HA state attributes based on coordinator data.

        Calculates is_on, percentage, and preset_mode based on the Duco box node's
        state, overrule status, and target level from the coordinator data.

        Returns:
            True if any internal state attributes changed, False otherwise.
        """
        # Use property to get box node info data safely
        node_info = self.box_node_info_data
        if not node_info:
            _LOGGER.debug("Node %s (Fan Entity): No box node info found.", self._box_node_id)
            return False # No change if data is missing

        duco_api_state: str | None = node_info.get(NODE_INFO_KEY_STATE)
        # Overrule percentage (should be 0-100 or None after normalization)
        active_overrule_pct: float | None = node_info.get(NODE_INFO_KEY_OVERRULE_PCT)
        target_level: int | float | None = node_info.get(NODE_INFO_KEY_TARGET_LEVEL)

        # Determine HA state based on priority: Overrule > Duco State
        calc_preset: str | None = None
        calc_pct: int = 0
        calc_is_on: bool = False

        if active_overrule_pct is not None and active_overrule_pct > 0:
            # If overrule is active (> 0%), use manual speed preset
            calc_preset = PRESET_KEY_MANUAL_SPEED
            try:
                # Percentage is the overrule value, clamped
                calc_pct = max(0, min(100, int(round(active_overrule_pct))))
                calc_is_on = True # Overrule means on
            except (ValueError, TypeError):
                _LOGGER.warning("Invalid overrule pct format: %s", active_overrule_pct)
                calc_pct = 0
                calc_is_on = False
        elif duco_api_state is not None:
            # No active overrule, use Duco state
            calc_preset = DUCO_STATE_TO_PRESET_KEY.get(duco_api_state)
            if calc_preset is None:
                _LOGGER.warning("Unknown Duco state '%s', defaulting preset to Away.", duco_api_state)
                calc_preset = PRESET_KEY_AWAY

            # Determine percentage based on target level or fallback
            if target_level is not None:
                try:
                    calc_pct = max(0, min(100, int(float(target_level))))
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid target level '%s', using fallback calculation.", target_level)
                    calc_pct = self._calculate_expected_percentage(duco_api_state)
            else:
                _LOGGER.debug("Target level not available, using fallback calculation.")
                calc_pct = self._calculate_expected_percentage(duco_api_state)

            # Fan is considered 'on' unless the preset is Away (or state was unknown)
            calc_is_on = calc_preset != PRESET_KEY_AWAY
        else:
            # Both state and overrule are missing, assume Away/Off
            _LOGGER.debug("Node %s (Fan Entity): State and overrule are None, assuming Away.", self._box_node_id)
            calc_preset = PRESET_KEY_AWAY
            calc_pct = 0
            calc_is_on = False

        # Check if calculated state differs from current internal HA state
        changed = False
        if self._attr_is_on != calc_is_on:
            self._attr_is_on = calc_is_on
            changed = True
        if self._attr_preset_mode != calc_preset:
            self._attr_preset_mode = calc_preset
            changed = True
        if self._attr_percentage != calc_pct:
            self._attr_percentage = calc_pct
            changed = True

        if changed:
            _LOGGER.debug(
                "Node %s (Fan Entity): Internal state updated - On: %s, Pct: %s, Preset: %s",
                self._box_node_id, self._attr_is_on, self._attr_percentage, self._attr_preset_mode
            )
        return changed

    # === Service Call Handlers ===
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        _LOGGER.info(
            "Node %s (Fan): Turning on request (pct=%s, preset=%s)",
            self._box_node_id, percentage, preset_mode,
        )
        if preset_mode:
            # Setting a preset mode implicitly turns the fan on (unless it's 'away')
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            # Setting a percentage implicitly turns the fan on
            await self.async_set_percentage(percentage)
        elif not self.is_on:
            # If just asked to turn on without specifics, default to Auto preset
            _LOGGER.debug("Node %s (Fan): Turning on by setting preset Auto.", self._box_node_id)
            await self.async_set_preset_mode(PRESET_KEY_AUTO)
        else:
            _LOGGER.debug("Node %s (Fan): async_turn_on called but fan is already on.", self._box_node_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off by setting the preset mode to Away."""
        _LOGGER.info("Node %s (Fan): Turning off request (setting preset Away).", self._box_node_id)
        await self.async_set_preset_mode(PRESET_KEY_AWAY)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the fan to a specific preset mode."""
        _LOGGER.info(
            "Node %s (Fan): Setting preset mode to '%s'", self._box_node_id, preset_mode
        )
        if preset_mode == PRESET_KEY_MANUAL_SPEED:
            # This preset represents the state when percentage is set directly
            _LOGGER.warning("Cannot set preset mode to '%s'. Use set_percentage service.", preset_mode)
            raise HomeAssistantError("Cannot set preset mode to 'manual_speed'. Use set_percentage.")
        if preset_mode not in self.preset_modes:
            raise ValueError(f"The preset mode '{preset_mode}' is not a valid preset mode.")

        # Get the corresponding Duco state code
        duco_state_code = PRESET_KEY_TO_DUCO_STATE.get(preset_mode)
        if not duco_state_code:
            # Should not happen if preset_modes is correct
            raise ValueError(f"Invalid preset mode mapping for: {preset_mode}")

        _LOGGER.debug("Node %s (Fan): Setting Duco state to '%s'", self._box_node_id, duco_state_code)
        # Set the Duco state via the coordinator action
        await self.coordinator.async_node_set_operation_state(self._box_node_id, duco_state_code)

        # After setting a preset, ensure any manual overrule is cancelled
        # Check current overrule first to avoid unnecessary API call
        current_overrule = self.box_node_info_data.get(NODE_INFO_KEY_OVERRULE_PCT, 0.0) or 0.0
        if current_overrule > 0:
            _LOGGER.debug(
                "Node %s (Fan): Cancelling active overrule (%s%%) after setting preset '%s'.",
                self._box_node_id, current_overrule, preset_mode
            )
            await self.coordinator.async_node_set_overrule(self._box_node_id, V1_CANCEL_OVERRULE_VALUE)
        # Refresh is handled by the coordinator action method debouncer

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed percentage (activates manual overrule)."""
        _LOGGER.info("Node %s (Fan): Setting percentage to %d%%", self._box_node_id, percentage)

        # Validate percentage
        if not isinstance(percentage, int):
            raise TypeError("Percentage must be an integer.")
        if not 0 <= percentage <= 100:
            raise ValueError("Percentage must be between 0 and 100.")

        if percentage == 0:
            # Turning off via percentage is equivalent to setting Away preset
            await self.async_turn_off()
            return

        # Clamp percentage to 1-100 for the API overrule command
        api_pct_value = max(1, min(100, percentage))
        _LOGGER.debug("Node %s (Fan): Setting overrule to %d%%", self._box_node_id, api_pct_value)

        # Set the overrule percentage via the coordinator action
        await self.coordinator.async_node_set_overrule(self._box_node_id, api_pct_value)
        # Refresh is handled by the coordinator action method debouncer

    # === State Update Handler ===
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Calculate new internal HA state based on coordinator data
        # This returns True if is_on, percentage, or preset_mode changed
        state_changed = self._update_internal_state_from_coordinator()

        # Write HA state if calculated state changed and entity is added to HA
        if state_changed and self.hass is not None:
            self.async_write_ha_state()
        elif not state_changed:
            _LOGGER.debug("Node %s (Fan Entity): No state change detected.", self._box_node_id)