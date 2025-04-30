# === custom_components/duco_ventilation_sun_control/entity.py ===
"""Provides the base entity classes for the Duco integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, time
from typing import Any, Generic, Optional, TypeVar, cast

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# Local integration imports
from .const import (
    AnyEntityDescription, AnyMapInfoType, DOMAIN, NODE_CONFIG_KEY_MAX,
    NODE_CONFIG_KEY_MIN, NODE_CONFIG_KEY_STEP, NODE_CONFIG_KEY_VALUE,
    PLATFORM_MAPS, reconstruct_ip_from_dict,
)
from .coordinator import DucoCoordinatorData, DucoDataUpdateCoordinator
from .device import async_create_node_device_info
from .util import get_nested_value

_LOGGER = logging.getLogger(__name__)

# Type variable for Coordinator specific to this integration
CoordinatorT = TypeVar("CoordinatorT", bound=DucoDataUpdateCoordinator)
# Sentinel object to indicate state hasn't been initialized yet
INITIAL_STATE_SENTINEL = object()


class DucoEntity(CoordinatorEntity[CoordinatorT], Generic[CoordinatorT]):
    """Base class for Duco entities linked to the main device (DucoBox).

    Handles common coordinator linking, availability checks, and provides
    base methods for state processing.
    """

    _attr_has_entity_name = True
    # Subclasses define their specific HA EntityDescription type
    entity_description: AnyEntityDescription
    # Internal state tracking, initialized to sentinel
    _previous_state: Any = INITIAL_STATE_SENTINEL
    # Platform identifier (e.g., Platform.SENSOR), must be set by subclasses
    _duco_platform: Platform | str = "unknown"

    def __init__(
        self,
        coordinator: CoordinatorT,
        map_info: AnyMapInfoType | None,
    ) -> None:
        """Initialize the base Duco entity.

        Args:
            coordinator: The data update coordinator instance.
            map_info: The mapping tuple from const.PLATFORM_MAPS for this entity.
        """
        super().__init__(coordinator)
        self._entry_id = coordinator.config_entry.entry_id
        # Base unique ID prefix for all entities belonging to this config entry
        self._entry_unique_id_base = f"duco_{coordinator.config_entry.entry_id}"
        # Link this entity to the main device entry in the device registry
        self._attr_device_info = coordinator.main_device_info
        # Store the mapping info tuple which tells how to get data/actions
        self.map_info = map_info
        # Unique ID is typically set in subclass __init__ using _entry_unique_id_base

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant.

        Called when the entity is about to be added. Fetches initial state
        if coordinator data is already available.
        """
        await super().async_added_to_hass()
        # Attempt to set initial state only if coordinator has data
        if self.coordinator.data:
            # Use internal method to process state without forcing HA write yet
            self._handle_coordinator_update_internal()
            _LOGGER.debug("[%s] Processed initial state from coordinator data.", self.unique_id)
        else:
            _LOGGER.debug("[%s] Coordinator data not available at add time.", self.unique_id)

    @property
    def available(self) -> bool:
        """Return True if coordinator is available and has successfully fetched data."""
        # Checks inherited coordinator availability and ensures data is present
        return (
            super().available
            and self.coordinator.last_update_success
            and self.coordinator.data is not None
        )

    def _get_data_map(self) -> dict[str, AnyMapInfoType] | None:
        """Get the platform-specific map dictionary (e.g., SENSOR_MAP) from const."""
        platform_map = PLATFORM_MAPS.get(self._duco_platform)
        if platform_map is None:
            unique_id_log = getattr(self, "unique_id", self.entity_description.key)
            _LOGGER.warning("Could not find platform map for %s entity %s.", self._duco_platform, unique_id_log)
        return platform_map

    def _get_raw_value(self) -> Any:
        """Retrieve the raw or formatted value from coordinator data using map_info.

        This base implementation fetches data for **device-level** entities
        (those linked directly to the DucoBox device). Node entities override this.

        Returns:
            The raw or formatted value based on map_info, or None if not found/error.
        """
        key = self.entity_description.key # Hierarchical key, e.g., "device.info.serial"
        unique_id = getattr(self, "unique_id", key)
        map_info = self.map_info
        coordinator_data = self.coordinator.data

        if not map_info: _LOGGER.debug("[%s] No map info.", unique_id); return None
        if not coordinator_data: _LOGGER.debug("[%s] No coordinator data.", unique_id); return None

        # Map structure: (data_source, path, value_key, get_formatter, ...)
        data_source_key: str = map_info[0]
        path: list[str | int] = map_info[1]
        value_key: str | None = map_info[2] if len(map_info) > 2 else None
        get_formatter: Callable | None = (map_info[3] if len(map_info) > 3 and callable(map_info[3]) else None)

        # Determine the source dictionary within coordinator_data
        source_data: dict[str, Any] | None = None
        if data_source_key == "device_info": source_data = coordinator_data.device_info
        elif data_source_key == "general_config": source_data = coordinator_data.general_config
        # Actions don't have a data source for state reading
        elif data_source_key == "action": return None
        else: _LOGGER.warning("[%s] Unsupported device data source key '%s'", unique_id, data_source_key); return None

        if source_data is None: _LOGGER.debug("[%s] Source data '%s' not found.", unique_id, data_source_key); return None

        # Retrieve the value using the path and potential value_key
        try:
            # Special handling for IP reconstruction formatter
            if get_formatter and get_formatter.__name__ == 'reconstruct_ip_from_dict':
                parent_dict = get_nested_value(source_data, *path)
                raw_value = get_formatter(parent_dict, value_key) # value_key is base_key here
            else:
                raw_value = get_nested_value(source_data, *path, value_key=value_key)

            # Apply other GET formatters if defined and value exists
            if get_formatter and get_formatter.__name__ != 'reconstruct_ip_from_dict' and raw_value is not None:
                try: return get_formatter(raw_value)
                except Exception as e: _LOGGER.error("[%s] Error applying GET formatter %s: %s", unique_id, get_formatter.__name__, e); return None
            else:
                return raw_value # Return raw or IP-reconstructed value

        except Exception as e:
            _LOGGER.debug("[%s] Error getting nested value for key %s: %s", unique_id, key, e)
            return None

    def _get_processed_state(self) -> Any:
        """Retrieve, format, and type-convert the state for the entity platform.

        This method uses the raw value obtained from `_get_raw_value` (which
        might be overridden by subclasses for node entities) and applies the
        final type conversions necessary for the specific HA entity platform.

        Returns:
            The processed state suitable for the entity's platform, or None.
        """
        key = self.entity_description.key
        unique_id = getattr(self, "unique_id", key)
        platform = self._duco_platform

        # Buttons do not have a state to process
        if platform == Platform.BUTTON: return None

        # Get the raw/formatted value from the appropriate source (device or node)
        value = self._get_raw_value()
        _LOGGER.debug("[%s] Platform %s processing value: %s (%s)", unique_id, platform, value, type(value).__name__)

        if value is None:
            # Handle specific None cases if needed by platform type
            if platform == Platform.NUMBER and isinstance(self.entity_description, NumberEntityDescription) and self.entity_description.mode == NumberMode.SLIDER:
                return 0.0 # Sliders often default to 0 if state is unknown
            return None # Default to None for most platforms if value is missing

        # Apply final type conversion based on the platform
        try:
            if platform == Platform.SENSOR:
                desc = cast(SensorEntityDescription, self.entity_description)
                if desc.device_class == SensorDeviceClass.TIMESTAMP: return value if isinstance(value, datetime) else None
                elif desc.native_unit_of_measurement is not None or desc.state_class == SensorStateClass.MEASUREMENT: return float(value)
                else: return str(value)
            elif platform == Platform.BINARY_SENSOR:
                # Logic to determine True/False is handled within the BinarySensorMapInfoType tuple
                # The _get_processed_state just needs to ensure the output of that logic is bool.
                # The actual comparison logic happens in platform file's _handle_coordinator_update
                # This base method just returns the raw value for binary sensor base class to work on.
                # Let's refine this: The formatters should ideally return bool directly if possible.
                # Reverting to simpler approach: Let platform class handle boolean conversion.
                return value # Platform _handle_update will cast/compare this
            elif platform == Platform.SWITCH:
                # Similar to binary sensor, let platform class handle boolean conversion/comparison
                return value
            elif platform == Platform.SELECT:
                desc = cast(SelectEntityDescription, self.entity_description)
                options = getattr(desc, "options", [])
                str_value = str(value) # Ensure comparison as string
                return str_value if str_value in options else None # Return option if valid, else None
            elif platform == Platform.NUMBER: return float(value)
            elif platform == Platform.TEXT: return str(value)
            elif platform == Platform.TIME: return value if isinstance(value, time) else None
            else: _LOGGER.warning("[%s] Unhandled platform '%s' for state processing.", unique_id, platform); return None
        except (ValueError, TypeError, Exception) as e:
            _LOGGER.error("[%s] Error processing state for key %s (value: %s, type: %s): %s", unique_id, key, value, type(value).__name__, e, exc_info=True)
            return None # Return None on processing error

    def _update_config_range_from_data(self) -> tuple[float | None, float | None, float | None]:
        """Fetch and process Min/Max/Step configuration for number entities.

        This base implementation fetches for device-level entities. Node entities override.
        Returns tuple (min, max, step) using defaults if data is unavailable/invalid.
        """
        key = self.entity_description.key
        map_info = self.map_info
        coordinator_data = self.coordinator.data
        desc = cast(NumberEntityDescription, self.entity_description)
        defaults = (getattr(desc, "native_min_value", None), getattr(desc, "native_max_value", None), getattr(desc, "native_step", None))

        if not coordinator_data or not map_info or len(map_info) < 2: return defaults

        data_source_key: str = map_info[0]
        path: list[str | int] = map_info[1]
        get_formatter: Callable | None = (map_info[3] if len(map_info) > 3 and callable(map_info[3]) else None)

        try:
            # Fetch the dictionary containing Min/Max/Step keys using internal helper
            param_data_dict = self._get_raw_value_param_dict(data_source_key, path)
            if not isinstance(param_data_dict, dict): return defaults

            # Extract, parse, and format range values
            min_v = self._parse_float(param_data_dict.get(NODE_CONFIG_KEY_MIN), defaults[0])
            max_v = self._parse_float(param_data_dict.get(NODE_CONFIG_KEY_MAX), defaults[1])
            step_v = self._parse_float(param_data_dict.get(NODE_CONFIG_KEY_STEP), defaults[2])

            if get_formatter: # Apply formatter if needed (e.g., temp ranges)
                min_v = self._apply_formatter(get_formatter, min_v, key, "min")
                max_v = self._apply_formatter(get_formatter, max_v, key, "max")

            if step_v is not None and step_v <= 0: step_v = defaults[2] # Ensure step is positive
            if min_v is not None and max_v is not None and min_v > max_v: min_v, max_v = max_v, min_v # Swap if min > max

            return min_v, max_v, step_v
        except Exception as e: _LOGGER.debug("[%s] Error updating config range: %s", key, e); return defaults

    def _get_raw_value_param_dict(self, data_source_key: str, path: list[str | int]) -> dict | None:
        """Helper to get the dict containing min/max/step. Base for device entities."""
        key = self.entity_description.key; unique_id = getattr(self, "unique_id", key)
        coordinator_data = self.coordinator.data
        if not coordinator_data: return None

        source_data: dict | None = None
        if data_source_key == "general_config": source_data = coordinator_data.general_config
        # Node entities will override this method to check node_data['config']
        else: _LOGGER.warning("[%s] Invalid data source '%s' for range update in device entity.", unique_id, data_source_key); return None

        if source_data is None: return None
        try: param_dict = get_nested_value(source_data, *path); return param_dict if isinstance(param_dict, dict) else None
        except Exception: return None

    @staticmethod
    def _parse_float(value: Any, default: float | None) -> float | None:
        """Safely parse a value to float, returning default on failure."""
        if value is None: return default
        try: return float(value)
        except (ValueError, TypeError): return default
    @staticmethod
    def _apply_formatter(formatter: Callable, value: Any, key: str, context: str) -> Any:
        """Safely apply a formatter function."""
        if value is None: return None
        try: return formatter(value)
        except Exception as e: _LOGGER.debug("[%s] Error formatting range %s %s: %s", key, context, value, e); return value

    @callback
    def _handle_coordinator_update_internal(self) -> bool:
        """Internal state update logic. To be called by platform _handle_coordinator_update."""
        unique_id = getattr(self, "unique_id", "unknown")
        if not self.coordinator.data: return False # No data, no change

        # Update range first for number entities
        if isinstance(self, NumberEntity): self._update_config_range_from_data() # type: ignore[attr-defined] # Method defined in base

        new_state = self._get_processed_state()
        state_changed = new_state != self._previous_state
        if state_changed: self._previous_state = new_state
        _LOGGER.debug("[%s] Internal state update. Changed: %s. New State: %s", unique_id, state_changed, new_state)
        return state_changed

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updates from the coordinator.

        This method should be called by the platform entity's implementation.
        It processes the state and writes it to HA if it changed.
        """
        if self._handle_coordinator_update_internal():
            self.async_write_ha_state()


# === Node-Specific Base Classes ===

class DucoNodeEntity(DucoEntity[CoordinatorT]):
    """Base class for Duco entities linked to a specific Node device."""

    def __init__(
        self,
        coordinator: CoordinatorT,
        node_id: int,
        map_info: AnyMapInfoType | None,
    ) -> None:
        """Initialize the base node entity."""
        self.node_id = node_id
        # Call DucoEntity init first to set up coordinator linking etc.
        super().__init__(coordinator, map_info)

        # Generate node-specific base unique ID
        main_device_unique_id = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        self._node_unique_id_base = f"{main_device_unique_id}_node_{node_id}"

        # Create and set the DeviceInfo for this node, linking via main device
        # Ensure node_info_data is accessed safely in case node data is missing initially
        node_info_data = self.node_info_data
        self._attr_device_info = async_create_node_device_info(
            main_device_unique_id, self.node_id, node_info_data
        )
        # Node entities usually set their full unique ID in their own __init__

    @property
    def unique_id_base(self) -> str:
        """Return the base unique ID for this node."""
        return self._node_unique_id_base

    @property
    def node_data(self) -> dict[str, Any]:
        """Return the raw data dictionary for this specific node from coordinator."""
        data = self.coordinator.data
        return data.nodes.get(str(self.node_id), {}) if data and data.nodes else {}

    @property
    def node_info_data(self) -> dict[str, Any]:
        """Return the 'info' part of the data for this node."""
        return self.node_data.get("info", {})

    @property
    def node_config_data(self) -> dict[str, Any]:
        """Return the 'config' part of the data for this node."""
        return self.node_data.get("config", {})

    @property
    def available(self) -> bool:
        """Return node availability based on coordinator and node data presence."""
        # Check base availability AND if this specific node_id exists in the data
        return (
            super().available
            and self.coordinator.data is not None
            and str(self.node_id) in self.coordinator.data.nodes
            # Optionally, add check if node_data itself is not empty?
            # and bool(self.node_data.get("info") or self.node_data.get("config"))
        )

    # Override _get_raw_value to fetch from node-specific data
    def _get_raw_value(self) -> Any:
        """Retrieve the raw value from coordinator data for this specific node."""
        key = self.entity_description.key # Hierarchical key, e.g., "node.info.co2"
        unique_id = getattr(self, "unique_id", f"node_{self.node_id}_{key}")
        map_info = self.map_info
        node_data = self.node_data # Use property to safely get node data

        if not map_info: _LOGGER.debug("[%s] No map info.", unique_id); return None
        if not node_data: _LOGGER.debug("[%s] No data for node %d.", unique_id, self.node_id); return None

        data_source_key: str = map_info[0] # Should be 'info' or 'config' for node entities
        path: list[str | int] = map_info[1]
        value_key: str | None = map_info[2] if len(map_info) > 2 else None
        get_formatter: Callable | None = (map_info[3] if len(map_info) > 3 and callable(map_info[3]) else None)

        source_data: dict[str, Any] | None = None
        if data_source_key == "info": source_data = self.node_info_data
        elif data_source_key == "config": source_data = self.node_config_data
        else: _LOGGER.warning("[%s] Unsupported node data source key '%s'", unique_id, data_source_key); return None

        if not source_data: _LOGGER.debug("[%s] Node source data '%s' not found.", unique_id, data_source_key); return None

        # Retrieve the value using the path and potential value_key
        try:
            # IP reconstructor unlikely needed for nodes, but check included for consistency
            if get_formatter and get_formatter.__name__ == 'reconstruct_ip_from_dict':
                parent_dict = get_nested_value(source_data, *path)
                raw_value = get_formatter(parent_dict, value_key)
            else:
                raw_value = get_nested_value(source_data, *path, value_key=value_key)

            # Apply other GET formatters
            if get_formatter and get_formatter.__name__ != 'reconstruct_ip_from_dict' and raw_value is not None:
                try: return get_formatter(raw_value)
                except Exception as e: _LOGGER.error("[%s] Error applying node GET formatter %s: %s", unique_id, get_formatter.__name__, e); return None
            else: return raw_value

        except Exception as e: _LOGGER.debug("[%s] Error getting nested node value for key %s: %s", unique_id, key, e); return None

    # Override helper for range update to use node data
    def _get_raw_value_param_dict(self, data_source_key: str, path: list[str | int]) -> dict | None:
        """Helper to get the dict containing min/max/step from node config data."""
        if data_source_key != "config": _LOGGER.warning("[%s] Invalid source '%s' for node range update.", self.unique_id, data_source_key); return None
        source_data = self.node_config_data
        if not source_data: return None
        try: param_dict = get_nested_value(source_data, *path); return param_dict if isinstance(param_dict, dict) else None
        except Exception: return None


class DucoBoxNodeEntity(DucoNodeEntity[CoordinatorT]):
    """Base class for Duco entities related specifically to the Box Node.

    Inherits from DucoNodeEntity to access box node's info/config data,
    but overrides the DeviceInfo to link entities to the main DucoBox device
    in the HA device registry, rather than creating a separate "Node 1" device.
    It also adjusts the unique ID base.
    """
    def __init__(
        self,
        coordinator: CoordinatorT,
        node_id: int, # This MUST be the Box Node ID identified by the coordinator
        map_info: AnyMapInfoType | None,
    ) -> None:
        """Initialize the box-node entity."""
        # Initialize as a node entity first to get node data access properties
        super().__init__(coordinator, node_id, map_info)
        # CRITICAL: Override device info to link to the main device entry
        self._attr_device_info = coordinator.main_device_info
        # Set unique ID based on the *main device's* base ID and the entity key
        # Note: The platform entity's __init__ will set the full unique ID
        # This base ensures entities related to the box node are grouped under the main device.