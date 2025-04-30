# === custom_components/duco_ventilation_sun_control/binary_sensor.py ===
"""Platform setup for Duco binary sensor entities."""

from __future__ import annotations

import logging
from typing import Any, Optional, cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

# Local integration imports
from .const import DOMAIN, IdentifiedEntity
from .coordinator import DucoDataUpdateCoordinator
from .entity import DucoBoxNodeEntity, DucoEntity, DucoNodeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Duco binary sensor entities based on identified entities."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Check if coordinator data and entities list are available
    identified_entities: list[IdentifiedEntity] = []
    if coordinator.data and hasattr(coordinator.data, "entities"):
        identified_entities = coordinator.data.entities
    else:
        _LOGGER.warning("Coordinator data or entities list not available during binary_sensor setup")
        # Optionally, you could raise ConfigEntryNotReady here if sensors are essential
        return

    entities_to_add: list[BinarySensorEntity] = []
    for identified_entity in identified_entities:
        if identified_entity.platform == Platform.BINARY_SENSOR:
            # Ensure the description is specifically a BinarySensorEntityDescription.
            if isinstance(identified_entity.entity_description, BinarySensorEntityDescription):
                description = cast(BinarySensorEntityDescription, identified_entity.entity_description)
                node_id = identified_entity.node_id
                map_info = identified_entity.map_info

                # Create the appropriate binary sensor entity type
                if node_id is None: # Device-level sensor
                    entities_to_add.append(
                        DucoDeviceBinarySensor(coordinator, description, map_info)
                    )
                elif identified_entity.is_box_node_entity: # Sensor for the Box Node
                    entities_to_add.append(
                        DucoBoxNodeBinarySensor(coordinator, node_id, description, map_info)
                    )
                else: # Sensor for a standard Node
                    entities_to_add.append(
                        DucoNodeBinarySensor(coordinator, node_id, description, map_info)
                    )
            else:
                _LOGGER.warning(
                    "Skipping binary_sensor setup for key '%s': Found description of unexpected type %s",
                    identified_entity.description_key,
                    type(identified_entity.entity_description).__name__,
                )

    if entities_to_add:
        async_add_entities(entities_to_add)
        _LOGGER.info("Added %d Duco binary sensor entities", len(entities_to_add))
    else:
        _LOGGER.info("No Duco binary sensor entities were identified for setup")


# === Platform-Specific Entity Classes ===

class DucoBinarySensorEntity(BinarySensorEntity):
    """Base class for Duco Binary Sensor entities state handling."""
    # Common state update logic for all Duco binary sensors

    _attr_is_on: bool | None = None # Internal HA state attribute

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Call the internal state processing logic from the base DucoEntity class
        # This updates self._previous_state based on new coordinator data
        state_changed = self._handle_coordinator_update_internal() # type: ignore[attr-defined]

        if state_changed:
            # Get the processed state (which should be bool or None)
            new_state = self._previous_state # type: ignore[attr-defined]
            self._attr_is_on = cast(Optional[bool], new_state)

            # Write the state if it changed and we are added to HASS
            if self.hass is not None:
                self.async_write_ha_state()


class DucoDeviceBinarySensor(DucoEntity[DucoDataUpdateCoordinator], DucoBinarySensorEntity):
    """Represents a Duco binary sensor entity linked to the main device."""

    entity_description: BinarySensorEntityDescription # Type hint

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the device binary sensor entity."""
        self._duco_platform = Platform.BINARY_SENSOR # Identify platform
        super().__init__(coordinator=coordinator, map_info=map_info)
        self.entity_description = description
        # Construct unique ID relative to the config entry base
        self._attr_unique_id = f"{self._entry_unique_id_base}_{description.key}"


class DucoBoxNodeBinarySensor(DucoBoxNodeEntity[DucoDataUpdateCoordinator], DucoBinarySensorEntity):
    """Represents a Duco binary sensor entity linked to the Box Node."""

    entity_description: BinarySensorEntityDescription # Type hint

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int, # Box node ID
        description: BinarySensorEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the box-node binary sensor entity."""
        self._duco_platform = Platform.BINARY_SENSOR # Identify platform
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID is derived from DucoBoxNodeEntity base


class DucoNodeBinarySensor(DucoNodeEntity[DucoDataUpdateCoordinator], DucoBinarySensorEntity):
    """Represents a Duco binary sensor entity linked to a standard Node."""

    entity_description: BinarySensorEntityDescription # Type hint

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int,
        description: BinarySensorEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the standard node binary sensor entity."""
        self._duco_platform = Platform.BINARY_SENSOR # Identify platform
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID uses the node-specific base + key
        self._attr_unique_id = f"{self.unique_id_base}_{description.key}"