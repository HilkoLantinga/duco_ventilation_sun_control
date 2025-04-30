# === custom_components/duco_ventilation_sun_control/time.py ===
"""Platform setup for Duco time entities."""

from __future__ import annotations

import logging
from datetime import time
from typing import Any, Callable, Optional, cast

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Local integration imports
from .const import (
    DOMAIN,
    IdentifiedEntity,
    KEY_MODULE_NIGHTBOOST, # Used in map
    KEY_MODULE_VENTCOOL, # Used in map
    TIME_ENTITY_MAP,
)
from .coordinator import DucoDataUpdateCoordinator
from .entity import DucoEntity # Time entities are device-level only

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Duco time entities based on identified entities."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    identified_entities: list[IdentifiedEntity] = []
    if coordinator.data and hasattr(coordinator.data, "entities"):
        identified_entities = coordinator.data.entities
    else:
        _LOGGER.warning("Coordinator data or entities list not available during time setup")
        return

    entities_to_add: list[TimeEntity] = []
    for identified_entity in identified_entities:
        if identified_entity.platform == Platform.TIME:
            if isinstance(identified_entity.entity_description, TimeEntityDescription):
                description = cast(TimeEntityDescription, identified_entity.entity_description)
                node_id = identified_entity.node_id
                map_info = identified_entity.map_info

                # Time entities are expected only at the device level
                if node_id is None:
                    entities_to_add.append(
                        DucoDeviceTime(coordinator, description, map_info)
                    )
                else:
                    _LOGGER.warning(
                        "Skipping time setup for key '%s': Found unexpected node_id %s",
                        identified_entity.description_key, node_id
                    )
            else:
                _LOGGER.warning(
                    "Skipping time setup for key '%s': Found description of unexpected type %s",
                    identified_entity.description_key,
                    type(identified_entity.entity_description).__name__,
                )

    if entities_to_add:
        async_add_entities(entities_to_add)
        _LOGGER.info("Added %d Duco time entities", len(entities_to_add))
    else:
        _LOGGER.info("No Duco time entities were identified for setup")


# === Base Time Entity Class ===

class DucoTimeBase(TimeEntity):
    """Base class providing state update logic for Duco time entities."""

    entity_description: TimeEntityDescription
    _attr_native_value: time | None = None # Internal HA state attribute

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Call the internal state processing logic from the base DucoEntity class
        state_changed = self._handle_coordinator_update_internal() # type: ignore[attr-defined]

        if state_changed:
            # Get the processed state (time object or None)
            new_state = self._previous_state # type: ignore[attr-defined]
            # Ensure the state is time or None
            self._attr_native_value = cast(Optional[time], new_state)

            # Write the state if it changed and we are added to HASS
            if self.hass is not None:
                self.async_write_ha_state()


# === Platform-Specific Entity Class ===

class DucoDeviceTime(DucoEntity[DucoDataUpdateCoordinator], DucoTimeBase):
    """Represents a Duco time entity linked to the main device."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        description: TimeEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the device time entity."""
        self._duco_platform = Platform.TIME
        super().__init__(coordinator=coordinator, map_info=map_info)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_unique_id_base}_{description.key}"

    async def async_set_value(self, value: time) -> None:
        """Update the current time value."""
        key = self.entity_description.key
        action_info = TIME_ENTITY_MAP.get(key)
        if not action_info:
            _LOGGER.error("[%s] No action defined for device time key: %s", self.unique_id, key)
            raise HomeAssistantError(f"Action not defined for time '{key}'.")

        # Map structure: (data_src, path, value_key, get_fmt, set_fmt)
        data_src, path_list, _vk, _get_fmt, set_fmt = action_info

        # Map time object to API value (likely total minutes) using set_formatter
        api_value: Any = None
        if set_fmt and callable(set_fmt):
            try: api_value = set_fmt(value)
            except Exception as e: raise HomeAssistantError(f"Could not map time {value}: {e}") from e
        else:
            # Should not happen if map is defined correctly
            raise HomeAssistantError(f"Missing required mapping logic for time '{key}'.")

        if api_value is None: # Should not happen if set_fmt is valid
            raise HomeAssistantError(f"Failed to map time '{value}' to API value.")

        _LOGGER.debug("[%s] Setting time to %s, API value: %s", self.unique_id, value, api_value)

        # Execute based on data source (expect 'general_config')
        if data_src == "general_config":
            if len(path_list) != 3:
                raise HomeAssistantError("Internal configuration error for time entity.")
            area, module, param = path_list
            # Time settings expected in 'box' area
            if area == "box":
                await self.coordinator.async_box_set_config(module, param, api_value)
            else:
                raise HomeAssistantError(f"Unsupported configuration area '{area}' for time entity.")
        else:
            raise HomeAssistantError("Internal configuration error for time entity.")
        # Refresh handled by coordinator action helper