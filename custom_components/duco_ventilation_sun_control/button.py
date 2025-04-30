# === custom_components/duco_ventilation_sun_control/button.py ===
"""Platform setup for Duco button entities."""

from __future__ import annotations

import logging
from typing import Any, Optional, cast

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Local integration imports
from .const import BUTTON_ACTION_MAP, DOMAIN, IdentifiedEntity
from .coordinator import DucoDataUpdateCoordinator
from .entity import DucoBoxNodeEntity, DucoEntity, DucoNodeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Duco button entities based on identified entities."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    identified_entities: list[IdentifiedEntity] = []
    if coordinator.data and hasattr(coordinator.data, "entities"):
        identified_entities = coordinator.data.entities
    else:
        _LOGGER.warning("Coordinator data or entities list not available during button setup")
        return

    entities_to_add: list[ButtonEntity] = []
    for identified_entity in identified_entities:
        if identified_entity.platform == Platform.BUTTON:
            if isinstance(identified_entity.entity_description, ButtonEntityDescription):
                description = cast(ButtonEntityDescription, identified_entity.entity_description)
                node_id = identified_entity.node_id
                map_info = identified_entity.map_info # Although not used for state, pass for consistency

                # Create the appropriate button entity type
                if node_id is None: # Device-level button
                    entities_to_add.append(
                        DucoDeviceButton(coordinator, description, map_info)
                    )
                # Box node currently has no specific buttons defined, but handle if needed
                elif identified_entity.is_box_node_entity:
                    _LOGGER.warning("Box node button identified but not expected: %s", description.key)
                    # entities_to_add.append(
                    #     DucoBoxNodeButton(coordinator, node_id, description, map_info)
                    # )
                else: # Button for a standard Node
                    entities_to_add.append(
                        DucoNodeButton(coordinator, node_id, description, map_info)
                    )
            else:
                _LOGGER.warning(
                    "Skipping button setup for key '%s': Found description of unexpected type %s",
                    identified_entity.description_key,
                    type(identified_entity.entity_description).__name__,
                )

    if entities_to_add:
        async_add_entities(entities_to_add)
        _LOGGER.info("Added %d Duco button entities", len(entities_to_add))
    else:
        _LOGGER.info("No Duco button entities were identified for setup")


# === Platform-Specific Entity Classes ===

class DucoDeviceButton(DucoEntity[DucoDataUpdateCoordinator], ButtonEntity):
    """Represents a Duco button entity linked to the main device."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        description: ButtonEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the device button entity."""
        self._duco_platform = Platform.BUTTON
        super().__init__(coordinator=coordinator, map_info=map_info)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_unique_id_base}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press event."""
        key = self.entity_description.key
        action_info = BUTTON_ACTION_MAP.get(key)
        if not action_info:
            _LOGGER.error("[%s] No action defined in BUTTON_ACTION_MAP for key: %s", self.unique_id, key)
            raise HomeAssistantError(f"Action for button '{key}' is not defined.")

        action_method_name, action_param = action_info
        action_method = getattr(self.coordinator, action_method_name, None)

        if not action_method or not callable(action_method):
            _LOGGER.error(
                "[%s] Action method '%s' not found or not callable on coordinator for button: %s",
                self.unique_id, action_method_name, key
            )
            raise HomeAssistantError(f"Coordinator method '{action_method_name}' not found.")

        _LOGGER.info(
            "[%s] Executing device action: %s (Param: %s)",
            self.unique_id, action_method_name, action_param
        )
        try:
            # Call the coordinator method, passing parameter if defined
            if action_param is not None:
                await action_method(action_param)
            else:
                await action_method()
            # Refresh handled by coordinator action method's debouncer
        except HomeAssistantError: # Catch errors raised by the coordinator action helper
            raise # Re-raise HA errors directly
        except Exception as e:
            _LOGGER.exception(
                "[%s] Unexpected error executing coordinator action '%s'",
                self.unique_id, action_method_name
            )
            raise HomeAssistantError(f"Error pressing button '{key}': {e}") from e


class DucoNodeButton(DucoNodeEntity[DucoDataUpdateCoordinator], ButtonEntity):
    """Represents a Duco button entity linked to a standard Node."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: DucoDataUpdateCoordinator,
        node_id: int,
        description: ButtonEntityDescription,
        map_info: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the standard node button entity."""
        self._duco_platform = Platform.BUTTON
        super().__init__(coordinator=coordinator, node_id=node_id, map_info=map_info)
        self.entity_description = description
        # Unique ID uses the node-specific base + key
        self._attr_unique_id = f"{self.unique_id_base}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press event for a standard node."""
        key = self.entity_description.key
        action_info = BUTTON_ACTION_MAP.get(key)
        if not action_info:
            _LOGGER.error("[%s] No action defined in BUTTON_ACTION_MAP for key: %s", self.unique_id, key)
            raise HomeAssistantError(f"Action for button '{key}' is not defined.")

        action_method_name, action_param = action_info
        action_method = getattr(self.coordinator, action_method_name, None)

        if not action_method or not callable(action_method):
            _LOGGER.error(
                "[%s] Action method '%s' not found or not callable on coordinator for button: %s",
                self.unique_id, action_method_name, key
            )
            raise HomeAssistantError(f"Coordinator method '{action_method_name}' not found.")

        _LOGGER.info(
            "[%s] Executing node action for node %d: %s (Param: %s)",
            self.unique_id, self.node_id, action_method_name, action_param
        )
        try:
            # Pass node_id as first argument to coordinator node actions
            if action_param is not None:
                await action_method(self.node_id, action_param)
            else:
                await action_method(self.node_id)
            # Refresh handled by coordinator action method's debouncer
        except HomeAssistantError:
            raise # Re-raise HA errors directly
        except Exception as e:
            _LOGGER.exception(
                "[%s] Unexpected error executing coordinator node action '%s'",
                self.unique_id, action_method_name
            )
            raise HomeAssistantError(f"Error pressing node button '{key}': {e}") from e

# Note: DucoBoxNodeButton is omitted as no specific box-node buttons are currently defined.
# If added later, it would inherit from DucoBoxNodeEntity and ButtonEntity, similar to DucoNodeButton.