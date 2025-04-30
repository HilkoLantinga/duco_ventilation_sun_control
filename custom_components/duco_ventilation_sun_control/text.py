# === custom_components/duco_ventilation_sun_control/switch.py ===
"""Platform setup for Duco switch entities."""

from __future__ import annotations

import logging
from typing import Any, Optional, cast

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Local integration imports
from .const import (
    DEVICE_INFO_KEY_INSTALLER_STATE, # Used for installer_mode switch
    DOMAIN,
    IdentifiedEntity,
    NODE_INFO_KEY_LINK, # Used for node_link_mode switch
    NODE_INFO_KEY_SHOW, # Used for node_show switch
    SWITCH_ENTITY_MAP,
)
from .coordinator import DucoDataUpdateCoordinator
from .entity import DucoBoxNodeEntity, DucoEntity, DucoNodeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Duco switch entities based on identified entities."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    identified_entities: list[IdentifiedEntity] = []
    if coordinator.data and hasattr(coordinator.data, "entities"):
        identified_entities = coordinator.data.entities
    else:
        _LOGGER.warning("Coordinator data or entities list not available during switch setup")
        return

    entities_to_add: list[SwitchEntity] = []
    for identified_entity in identified_entities:
        if identified_entity.platform == Platform.SWITCH:
            if isinstance(identified_entity.entity_description, SwitchEntityDescription):
                description = cast(SwitchEntityDescription, identified_entity.entity_description)
                node_id = identified_entity.node_id
                map_info = identified_entity.map_info

                # Create the appropriate switch entity type
                if node_id is None: # Device-level switch
                    entities_to_add.append(
                        DucoDeviceSwitch(coordinator, description, map_info)
                    )
                elif identified_entity.is_box_node_entity: # Switch for the Box Node
                    entities_to_add.append(
                        DucoBoxNodeSwitch(coordinator, node_id, description, map_info)
                    )
                else: # Switch for a standard Node
                    entities_to_add.append(
                        DucoNodeSwitch(coordinator, node_id, description, map_info)
                    )
            else:
                _LOGGER.warning(
                    "Skipping switch setup for key '%s': Found description of unexpected type %s",
                    identified_entity.description_key,
                    type(identified_entity.entity_description).__name__,
                )

    if entities_to_add:
        async_add_entities(entities_to_add)
        _LOGGER.info("Added %d Duco switch entities", len(entities_to_add))
    else:
        _LOGGER.info("No Duco switch entities were identified for setup")


# === Base Switch Entity Class ===

class DucoSwitchBase(SwitchEntity):
    """Base class providing state update logic for Duco switches."""

    entity_description: SwitchEntityDescription
    _attr_is_on: bool | None = None # Internal HA state attribute

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Call the internal state processing logic from the base DucoEntity class
        state_changed = self._handle_coordinator_update_internal() # type: ignore[attr-defined]

        if state_changed:
            # Get the processed state (boolean or None)
            new_state = self._previous_state # type: ignore[attr-defined]
            self._attr_is_on = cast(Optional[bool], new_state)

            # Write the state if it changed and we are added to HASS
            if self.hass is not None:
                self.async_write_ha_state()


# === Platform-Specific Entity Classes ===

class DucoDeviceSwitch(DucoEntity[DucoDataUpdateCoordinator], DucoSwitchBase):
    """Represents a Duco switch entity linked to the main device."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        description: SwitchEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the device switch entity."""
        self._duco_platform = Platform.SWITCH
        super().__init__(coordinator=coordinator, map_info=map_info)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_unique_id_base}_{description.key}"

    async def _async_turn_on_off(self, turn_on: bool) -> None:
        """Send the command to turn the device switch on or off."""
        key = self.entity_description.key
        action_info = SWITCH_ENTITY_MAP.get(key)
        if not action_info:
            _LOGGER.error("[%s] No action defined for device switch key: %s", self.unique_id, key)
            raise HomeAssistantError(f"Action not defined for switch '{key}'.")

        # Map structure: (data_src, path, value_key, on_value, off_value, invert)
        data_src, path_list, _vk, on_value, off_value, invert = action_info

        # Determine API value based on action and inversion
        api_value = on_value if turn_on else off_value
        if invert:
            api_value = off_value if turn_on else on_value

        # Convert to int if possible (common for config values)
        try:
            api_value_final: Any = int(api_value) if api_value is not None else None
        except (ValueError, TypeError):
            api_value_final = api_value # Keep original type

        _LOGGER.debug("[%s] Turning %s, API value: %s", self.unique_id, "on" if turn_on else "off", api_value_final)

        # Execute action based on data source
        if data_src == "general_config":
            if len(path_list) != 3:
                raise HomeAssistantError("Internal configuration error for switch entity.")
            area, module, param = path_list
            if area == "box":
                await self.coordinator.async_box_set_config(module, param, api_value_final)
            elif area == "ip":
                await self.coordinator.async_ip_set_config(module, param, api_value_final)
            elif area == "eco":
                await self.coordinator.async_eco_set_config(module, param, api_value_final)
            else:
                raise HomeAssistantError(f"Unsupported configuration area '{area}'.")
        elif data_src == "device_info" and key == DEVICE_INFO_KEY_INSTALLER_STATE:
            # Special case for toggling installer mode action
            await self.coordinator.async_box_toggle_installer_mode(turn_on)
        else:
            raise HomeAssistantError("Internal configuration error for switch entity.")
        # Refresh handled by coordinator action helper

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_turn_on_off(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_turn_on_off(False)


class DucoBoxNodeSwitch(DucoBoxNodeEntity[DucoDataUpdateCoordinator], DucoSwitchBase):
    """Represents a Duco switch entity linked to the Box Node."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int, # Box node ID
        description: SwitchEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the box-node switch entity."""
        self._duco_platform = Platform.SWITCH
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID uses base class implementation (main device base + key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await DucoNodeSwitch._async_turn_on_off_node(self, True, self._box_node_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await DucoNodeSwitch._async_turn_on_off_node(self, False, self._box_node_id)


class DucoNodeSwitch(DucoNodeEntity[DucoDataUpdateCoordinator], DucoSwitchBase):
    """Represents a Duco switch entity linked to a standard Node."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int,
        description: SwitchEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the standard node switch entity."""
        self._duco_platform = Platform.SWITCH
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID uses the node-specific base + key
        self._attr_unique_id = f"{self.unique_id_base}_{description.key}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_turn_on_off_node(True, self.node_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_turn_on_off_node(False, self.node_id)

    # Define shared setter logic for node/box-node switches
    async def _async_turn_on_off_node(self, turn_on: bool, node_id: int) -> None:
        """Shared logic to set value for node-based switch entities."""
        key = self.entity_description.key
        action_info = SWITCH_ENTITY_MAP.get(key)
        if not action_info:
            _LOGGER.error("[%s] No action defined for node switch key: %s", self.unique_id, key)
            raise HomeAssistantError(f"Action not defined for switch '{key}'.")

        # Map structure: (data_src, path, value_key, on_value, off_value, invert)
        data_src, path_list, _vk, on_value, off_value, invert = action_info

        # Determine API value
        api_value = on_value if turn_on else off_value
        if invert:
            api_value = off_value if turn_on else on_value

        # Convert to int if possible
        try:
            api_value_final: Any = int(api_value) if api_value is not None else None
        except (ValueError, TypeError):
            api_value_final = api_value

        _LOGGER.debug("[%s] Turning %s, API value: %s", self.unique_id, "on" if turn_on else "off", api_value_final)

        # Execute based on data source ('config' or 'info' for special actions)
        if data_src == "config":
            if not path_list:
                raise HomeAssistantError("Internal configuration error.")
            param = path_list[0]
            # Assume V1 style module name (param=module), coordinator handles API diff
            await self.coordinator.async_node_set_config(node_id, param, api_value_final, module=param)
        elif data_src == "info":
            # Special actions mapped via 'info' source
            if key == NODE_INFO_KEY_SHOW:
                await self.coordinator.async_node_toggle_show(node_id, turn_on)
            elif key == NODE_INFO_KEY_LINK:
                await self.coordinator.async_node_set_link_mode(node_id, turn_on)
            else:
                raise HomeAssistantError(f"Unsupported action for switch '{key}'.")
        else:
            raise HomeAssistantError("Internal configuration error for switch entity.")
        # Refresh handled by coordinator action helper