# === custom_components/duco_ventilation_sun_control/select.py ===
"""Platform setup for Duco select entities."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, cast

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Local integration imports
from .const import (
    ALL_CALIBRATION_COMMANDS,
    ALL_NODE_STATES,
    DEVICE_INFO_KEY_CALIB_STATE, # Used for box_calib_command state
    DOMAIN,
    IdentifiedEntity,
    KEY_MODULE_FAN, # Used in maps
    KEY_MODULE_NIGHTBOOST,
    KEY_MODULE_VENTCOOL,
    NODE_INFO_KEY_STATE, # Used for node_operation_state state
    SELECT_ENTITY_MAP,
    DucoCalibCommand, # Enum for calibration commands
)
from .coordinator import DucoDataUpdateCoordinator
from .entity import DucoBoxNodeEntity, DucoEntity, DucoNodeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Duco select entities based on identified entities."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    identified_entities: list[IdentifiedEntity] = []
    if coordinator.data and hasattr(coordinator.data, "entities"):
        identified_entities = coordinator.data.entities
    else:
        _LOGGER.warning("Coordinator data or entities list not available during select setup")
        return

    entities_to_add: list[SelectEntity] = []
    for identified_entity in identified_entities:
        if identified_entity.platform == Platform.SELECT:
            if isinstance(identified_entity.entity_description, SelectEntityDescription):
                description = cast(SelectEntityDescription, identified_entity.entity_description)
                node_id = identified_entity.node_id
                map_info = identified_entity.map_info

                # Create the appropriate select entity type
                if node_id is None: # Device-level select
                    entities_to_add.append(
                        DucoDeviceSelect(coordinator, description, map_info)
                    )
                elif identified_entity.is_box_node_entity: # Select for the Box Node
                    entities_to_add.append(
                        DucoBoxNodeSelect(coordinator, node_id, description, map_info)
                    )
                else: # Select for a standard Node
                    entities_to_add.append(
                        DucoNodeSelect(coordinator, node_id, description, map_info)
                    )
            else:
                _LOGGER.warning(
                    "Skipping select setup for key '%s': Found description of unexpected type %s",
                    identified_entity.description_key,
                    type(identified_entity.entity_description).__name__,
                )

    if entities_to_add:
        async_add_entities(entities_to_add)
        _LOGGER.info("Added %d Duco select entities", len(entities_to_add))
    else:
        _LOGGER.info("No Duco select entities were identified for setup")


# === Base Select Entity Class ===

class DucoSelectBase(SelectEntity):
    """Base class providing state update logic for Duco select entities."""

    entity_description: SelectEntityDescription
    _attr_current_option: str | None = None # Internal HA state attribute

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Call the internal state processing logic from the base DucoEntity class
        state_changed = self._handle_coordinator_update_internal() # type: ignore[attr-defined]

        if state_changed:
            # Get the processed state (string or None)
            new_state = self._previous_state # type: ignore[attr-defined]
            # Ensure the state is string or None
            self._attr_current_option = cast(Optional[str], new_state)

            # Write the state if it changed and we are added to HASS
            if self.hass is not None:
                self.async_write_ha_state()


# === Platform-Specific Entity Classes ===

class DucoDeviceSelect(DucoEntity[DucoDataUpdateCoordinator], DucoSelectBase):
    """Represents a Duco select entity linked to the main device."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        description: SelectEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the device select entity."""
        self._duco_platform = Platform.SELECT
        super().__init__(coordinator=coordinator, map_info=map_info)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_unique_id_base}_{description.key}"

        # Special case: Calibration command doesn't have a persistent state
        if description.key == "box_calib_command":
            self._attr_current_option = None # Always appear unset

    # Override state update for calibration command as it's action-only
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator updates (overridden for action-only selects)."""
        if self.entity_description.key == "box_calib_command":
            # This select is action-only, its state doesn't come from the coordinator.
            # We keep _attr_current_option as None.
            return
        # For other device selects, use the standard update logic
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        key = self.entity_description.key
        action_info = SELECT_ENTITY_MAP.get(key)
        if not action_info:
            _LOGGER.error("[%s] No action defined for device select key: %s", self.unique_id, key)
            raise HomeAssistantError(f"Action not defined for select '{key}'.")

        # Unpack map: (data_src, path, value_key, get_fmt, set_fmt)
        data_src, path_list, _vk, _get_fmt, set_fmt = action_info

        # Map option string to API value using set_formatter
        api_value: Any = option # Default if no formatter
        if set_fmt and callable(set_fmt):
            try: api_value = set_fmt(option)
            except Exception as e: raise HomeAssistantError(f"Could not map option '{option}': {e}") from e

        if api_value is None and option is not None:
            raise HomeAssistantError(f"Failed to map option '{option}' to API value.")

        _LOGGER.debug("[%s] Selecting option '%s', API value: %s", self.unique_id, option, api_value)

        # Execute action
        if key == "box_calib_command":
            if api_value not in ALL_CALIBRATION_COMMANDS:
                raise HomeAssistantError(f"Invalid calibration command: {api_value}")
            # Use the enum value for clarity if possible
            cmd_enum = next((cmd for cmd in DucoCalibCommand if cmd.value == api_value), None)
            await self.coordinator.async_box_set_calibration(cmd_enum or api_value)
        elif data_src == "general_config":
            if len(path_list) != 3:
                raise HomeAssistantError("Internal configuration error for select entity.")
            area, module, param = path_list
            if area == "box":
                await self.coordinator.async_box_set_config(module, param, api_value)
            elif area == "ip":
                await self.coordinator.async_ip_set_config(module, param, api_value)
            elif area == "eco":
                await self.coordinator.async_eco_set_config(module, param, api_value)
            else:
                raise HomeAssistantError(f"Unsupported configuration area '{area}'.")
        else:
            raise HomeAssistantError("Internal configuration error for select entity.")
        # Refresh handled by coordinator action helper


class DucoBoxNodeSelect(DucoBoxNodeEntity[DucoDataUpdateCoordinator], DucoSelectBase):
    """Represents a Duco select entity linked to the Box Node."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int, # Box node ID
        description: SelectEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the box-node select entity."""
        self._duco_platform = Platform.SELECT
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID uses base class implementation (main device base + key)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option for the box node select."""
        # Logic is the same as standard node select, uses _box_node_id
        await DucoNodeSelect._async_select_option_node(self, option, self._box_node_id)


class DucoNodeSelect(DucoNodeEntity[DucoDataUpdateCoordinator], DucoSelectBase):
    """Represents a Duco select entity linked to a standard Node."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int,
        description: SelectEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the standard node select entity."""
        self._duco_platform = Platform.SELECT
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID uses the node-specific base + key
        self._attr_unique_id = f"{self.unique_id_base}_{description.key}"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option for the standard node select."""
        await self._async_select_option_node(option, self.node_id)

    # Define shared setter logic for node/box-node selects
    async def _async_select_option_node(self, option: str, node_id: int) -> None:
        """Shared logic to set value for node-based select entities."""
        key = self.entity_description.key
        action_info = SELECT_ENTITY_MAP.get(key)
        if not action_info:
            _LOGGER.error("[%s] No action defined for node select key: %s", self.unique_id, key)
            raise HomeAssistantError(f"Action not defined for select '{key}'.")

        # Unpack map: (data_src, path, value_key, get_fmt, set_fmt)
        data_src, _path, _vk, _get_fmt, set_fmt = action_info

        # Map option string to API value
        api_value: Any = option # Default if no formatter
        if set_fmt and callable(set_fmt):
            try: api_value = set_fmt(option)
            except Exception as e: raise HomeAssistantError(f"Could not map option '{option}': {e}") from e

        if api_value is None and option is not None:
            raise HomeAssistantError(f"Failed to map option '{option}' to API value.")

        _LOGGER.debug("[%s] Selecting option '%s', API value: %s", self.unique_id, option, api_value)

        # Execute based on data source ('info' for node state action)
        if data_src == "info" and key == NODE_INFO_KEY_STATE:
            if api_value not in ALL_NODE_STATES:
                raise HomeAssistantError(f"Invalid node operation state selected: {api_value}")
            await self.coordinator.async_node_set_operation_state(node_id, api_value)
        # Add elif for other node-specific 'config' selects if needed in future
        else:
            _LOGGER.error("[%s] Unsupported action/source '%s' for node select", self.unique_id, data_src)
            raise HomeAssistantError("Internal configuration error for select entity.")
        # Refresh handled by coordinator action helper