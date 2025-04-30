# === custom_components/duco_ventilation_sun_control/sensor.py ===
"""Platform setup for Duco sensor entities."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
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
    """Set up Duco sensor entities based on identified entities."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    identified_entities: list[IdentifiedEntity] = []
    if coordinator.data and hasattr(coordinator.data, "entities"):
        identified_entities = coordinator.data.entities
    else:
        _LOGGER.warning("Coordinator data or entities list not available during sensor setup")
        return

    entities_to_add: list[SensorEntity] = []
    for identified_entity in identified_entities:
        if identified_entity.platform == Platform.SENSOR:
            if isinstance(identified_entity.entity_description, SensorEntityDescription):
                description = cast(SensorEntityDescription, identified_entity.entity_description)
                node_id = identified_entity.node_id
                map_info = identified_entity.map_info

                # Create the appropriate sensor entity type
                if node_id is None: # Device-level sensor
                    entities_to_add.append(
                        DucoDeviceSensor(coordinator, description, map_info)
                    )
                elif identified_entity.is_box_node_entity: # Sensor for the Box Node
                    entities_to_add.append(
                        DucoBoxNodeSensor(coordinator, node_id, description, map_info)
                    )
                else: # Sensor for a standard Node
                    entities_to_add.append(
                        DucoNodeSensor(coordinator, node_id, description, map_info)
                    )
            else:
                _LOGGER.warning(
                    "Skipping sensor setup for key '%s': Found description of unexpected type %s",
                    identified_entity.description_key,
                    type(identified_entity.entity_description).__name__,
                )

    if entities_to_add:
        async_add_entities(entities_to_add)
        _LOGGER.info("Added %d Duco sensor entities", len(entities_to_add))
    else:
        _LOGGER.info("No Duco sensor entities were identified for setup")


# === Base Sensor Entity Class ===

class DucoSensorBase(SensorEntity):
    """Base class providing state update logic for Duco sensors."""

    entity_description: SensorEntityDescription
    _attr_native_value: StateType | datetime | None = None # Internal HA state attribute

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Call the internal state processing logic from the base DucoEntity class
        state_changed = self._handle_coordinator_update_internal() # type: ignore[attr-defined]

        if state_changed:
            # Get the processed state (string, float, datetime, or None)
            new_state = self._previous_state # type: ignore[attr-defined]
            self._attr_native_value = new_state # Type is handled by _get_processed_state

            # Write the state if it changed and we are added to HASS
            if self.hass is not None:
                self.async_write_ha_state()


# === Platform-Specific Entity Classes ===

class DucoDeviceSensor(DucoEntity[DucoDataUpdateCoordinator], DucoSensorBase):
    """Represents a Duco sensor entity linked to the main device."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        description: SensorEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the device sensor entity."""
        self._duco_platform = Platform.SENSOR
        super().__init__(coordinator=coordinator, map_info=map_info)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_unique_id_base}_{description.key}"


class DucoBoxNodeSensor(DucoBoxNodeEntity[DucoDataUpdateCoordinator], DucoSensorBase):
    """Represents a Duco sensor entity linked to the Box Node."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int, # Box node ID
        description: SensorEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the box-node sensor entity."""
        self._duco_platform = Platform.SENSOR
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID uses base class implementation (main device base + key)


class DucoNodeSensor(DucoNodeEntity[DucoDataUpdateCoordinator], DucoSensorBase):
    """Represents a Duco sensor entity linked to a standard Node."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int,
        description: SensorEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the standard node sensor entity."""
        self._duco_platform = Platform.SENSOR
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID uses the node-specific base + key
        self._attr_unique_id = f"{self.unique_id_base}_{description.key}"