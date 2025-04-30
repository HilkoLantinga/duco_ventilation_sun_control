# === custom_components/duco_ventilation_sun_control/number.py ===
"""Platform setup for Duco number entities."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, cast

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG, PERCENTAGE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Local integration imports
from .const import (
    DOMAIN,
    IdentifiedEntity,
    NODE_INFO_KEY_ASSO_ID,
    NODE_INFO_KEY_OVERRULE_PCT,
    NODE_INFO_KEY_PARENT_ID,
    NUMBER_ENTITY_MAP,
    V1_CANCEL_OVERRULE_VALUE, # Used in set_value for overrule
)
from .coordinator import DucoDataUpdateCoordinator
from .entity import DucoBoxNodeEntity, DucoEntity, DucoNodeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Duco number entities based on identified entities."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    identified_entities: list[IdentifiedEntity] = []
    if coordinator.data and hasattr(coordinator.data, "entities"):
        identified_entities = coordinator.data.entities
    else:
        _LOGGER.warning("Coordinator data or entities list not available during number setup")
        return

    entities_to_add: list[NumberEntity] = []
    for identified_entity in identified_entities:
        if identified_entity.platform == Platform.NUMBER:
            if isinstance(identified_entity.entity_description, NumberEntityDescription):
                description = cast(NumberEntityDescription, identified_entity.entity_description)
                node_id = identified_entity.node_id
                map_info = identified_entity.map_info

                # Create the appropriate number entity type
                if node_id is None: # Device-level number
                    entities_to_add.append(
                        DucoDeviceNumber(coordinator, description, map_info)
                    )
                elif identified_entity.is_box_node_entity: # Number for the Box Node
                    entities_to_add.append(
                        DucoBoxNodeNumber(coordinator, node_id, description, map_info)
                    )
                else: # Number for a standard Node
                    entities_to_add.append(
                        DucoNodeNumber(coordinator, node_id, description, map_info)
                    )
            else:
                _LOGGER.warning(
                    "Skipping number setup for key '%s': Found description of unexpected type %s",
                    identified_entity.description_key,
                    type(identified_entity.entity_description).__name__,
                )

    if entities_to_add:
        async_add_entities(entities_to_add)
        _LOGGER.info("Added %d Duco number entities", len(entities_to_add))
    else:
        _LOGGER.info("No Duco number entities were identified for setup")


# === Base Number Entity Class ===

class DucoNumberBase(NumberEntity):
    """Base class providing state and range update logic for Duco numbers."""

    entity_description: NumberEntityDescription
    _attr_native_value: float | None = None # Internal HA state attribute

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update the entity's min/max/step range based on latest data *first*
        # This ensures any validation or display uses the current range
        self._update_range_from_data() # type: ignore[attr-defined]

        # Call the internal state processing logic from the base DucoEntity class
        state_changed = self._handle_coordinator_update_internal() # type: ignore[attr-defined]

        if state_changed:
            # Get the processed state (float or None)
            new_state = self._previous_state # type: ignore[attr-defined]
            # Ensure the state is float or None
            self._attr_native_value = self._parse_float(new_state, None)

            # Write the state if it changed and we are added to HASS
            if self.hass is not None:
                self.async_write_ha_state()

    @callback
    def _update_range_from_data(self) -> None:
        """Update the number entity's range attributes from coordinator data."""
        # Use the helper method from the base DucoEntity class
        min_val, max_val, step_val = self._update_config_range_from_data() # type: ignore[attr-defined]

        # Store the potentially updated range values
        # Base class ensures they are floats or None
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step_val

        # Log if range was updated (optional)
        # _LOGGER.debug("[%s] Updated range: Min=%s, Max=%s, Step=%s", self.unique_id, min_val, max_val, step_val)

    @staticmethod
    def _parse_float(value: Any, default: float | None) -> float | None:
        """Safely parse a value to float, returning default on failure."""
        if value is None: return default
        try: return float(value)
        except (ValueError, TypeError): return default


# === Platform-Specific Entity Classes ===

class DucoDeviceNumber(DucoEntity[DucoDataUpdateCoordinator], DucoNumberBase):
    """Represents a Duco number entity linked to the main device."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        description: NumberEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the device number entity."""
        self._duco_platform = Platform.NUMBER
        super().__init__(coordinator=coordinator, map_info=map_info)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_unique_id_base}_{description.key}"
        # Initialize range from description defaults
        self._attr_native_min_value = self._parse_float(getattr(description, "native_min_value", None), 0.0)
        self._attr_native_max_value = self._parse_float(getattr(description, "native_max_value", None), 100.0)
        self._attr_native_step = self._parse_float(getattr(description, "native_step", None), 1.0)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        key = self.entity_description.key
        action_info = NUMBER_ENTITY_MAP.get(key)
        if not action_info:
            _LOGGER.error("[%s] No action defined in NUMBER_ENTITY_MAP for device key: %s", self.unique_id, key)
            raise HomeAssistantError(f"Action not defined for number '{key}'.")

        # Unpack mapping: (data_source, path, value_key, get_fmt, set_fmt)
        data_src, path_list, _vk, _get_fmt, set_fmt = action_info

        # Format value for API if needed
        api_value: Any = value
        if set_fmt and callable(set_fmt):
            try: api_value = set_fmt(value)
            except Exception as e: raise HomeAssistantError(f"Could not format value {value}: {e}") from e
        # Convert to int if step suggests integer values
        elif self.native_step == 1.0:
            try: api_value = int(value)
            except (ValueError, TypeError): pass # Keep float if conversion fails

        _LOGGER.debug("[%s] Setting value to %s, API value: %s", self.unique_id, value, api_value)

        # Execute based on data source (should be 'general_config' for device numbers)
        if data_src == "general_config":
            if len(path_list) != 3:
                _LOGGER.error("[%s] Invalid path list for general_config number: %s", self.unique_id, path_list)
                raise HomeAssistantError("Internal configuration error for number entity.")
            area, module, param = path_list
            if area == "box":
                await self.coordinator.async_box_set_config(module, param, api_value)
            elif area == "eco":
                await self.coordinator.async_eco_set_config(module, param, api_value)
            elif area == "ip":
                 await self.coordinator.async_ip_set_config(module, param, api_value)
            else:
                _LOGGER.error("[%s] Unsupported area '%s' for number: %s", self.unique_id, area, key)
                raise HomeAssistantError(f"Unsupported configuration area '{area}'.")
        else:
            _LOGGER.error("[%s] Unsupported data source '%s' for device number", self.unique_id, data_src)
            raise HomeAssistantError("Internal configuration error for number entity.")
        # Refresh handled by coordinator action helper


class DucoBoxNodeNumber(DucoBoxNodeEntity[DucoDataUpdateCoordinator], DucoNumberBase):
    """Represents a Duco number entity linked to the Box Node."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int, # Box node ID
        description: NumberEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the box-node number entity."""
        self._duco_platform = Platform.NUMBER
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID uses base class implementation (main device base + key)
        # Initialize range from description defaults
        self._attr_native_min_value = self._parse_float(getattr(description, "native_min_value", None), 0.0)
        self._attr_native_max_value = self._parse_float(getattr(description, "native_max_value", None), 100.0)
        self._attr_native_step = self._parse_float(getattr(description, "native_step", None), 1.0)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value for the box node number."""
        # Logic is the same as standard node number, just uses _box_node_id
        await DucoNodeNumber._async_set_native_value_node(self, value, self._box_node_id)


class DucoNodeNumber(DucoNodeEntity[DucoDataUpdateCoordinator], DucoNumberBase):
    """Represents a Duco number entity linked to a standard Node."""

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int,
        description: NumberEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the standard node number entity."""
        self._duco_platform = Platform.NUMBER
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID uses the node-specific base + key
        self._attr_unique_id = f"{self.unique_id_base}_{description.key}"
        # Initialize range from description defaults
        self._attr_native_min_value = self._parse_float(getattr(description, "native_min_value", None), 0.0)
        self._attr_native_max_value = self._parse_float(getattr(description, "native_max_value", None), 100.0)
        self._attr_native_step = self._parse_float(getattr(description, "native_step", None), 1.0)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value for the standard node number."""
        await self._async_set_native_value_node(value, self.node_id)

    # Define shared setter logic for node/box-node numbers
    async def _async_set_native_value_node(self, value: float, node_id: int) -> None:
        """Shared logic to set value for node-based number entities."""
        key = self.entity_description.key
        action_info = NUMBER_ENTITY_MAP.get(key)
        if not action_info:
            _LOGGER.error("[%s] No action defined for node number key: %s", self.unique_id, key)
            raise HomeAssistantError(f"Action not defined for number '{key}'.")

        # Unpack mapping
        data_src, path_list, _vk, _get_fmt, set_fmt = action_info

        # Format value for API
        api_value: Any = value
        if set_fmt and callable(set_fmt):
            try: api_value = set_fmt(value)
            except Exception as e: raise HomeAssistantError(f"Could not format value {value}: {e}") from e
        elif self.native_step == 1.0:
            try: api_value = int(value)
            except (ValueError, TypeError): pass

        _LOGGER.debug("[%s] Setting value to %s, API value: %s", self.unique_id, value, api_value)

        # Execute based on data source ('config' or 'info' for special actions)
        if data_src == "config":
            if not path_list:
                _LOGGER.error("[%s] Invalid path list for node config number: %s", self.unique_id, path_list)
                raise HomeAssistantError("Internal configuration error.")
            param = path_list[0]
            # Assume V1 style module name (param=module) for now, coordinator handles API diff
            await self.coordinator.async_node_set_config(node_id, param, api_value, module=param)
        elif data_src == "info":
            # Handle special actions mapped via 'info' source
            if key == NODE_INFO_KEY_OVERRULE_PCT:
                api_value_overrule = V1_CANCEL_OVERRULE_VALUE if int(value) == 0 else max(1, min(100, int(value)))
                await self.coordinator.async_node_set_overrule(node_id, api_value_overrule)
            elif key == NODE_INFO_KEY_ASSO_ID:
                await self.coordinator.async_node_set_association(node_id, int(value))
            elif key == NODE_INFO_KEY_PARENT_ID:
                await self.coordinator.async_node_set_parent(node_id, int(value))
            else:
                _LOGGER.error("[%s] Unsupported 'info' action for node number: %s", self.unique_id, key)
                raise HomeAssistantError(f"Unsupported action for number '{key}'.")
        else:
            _LOGGER.error("[%s] Unsupported data source '%s' for node number", self.unique_id, data_src)
            raise HomeAssistantError("Internal configuration error.")
        # Refresh handled by coordinator action helper