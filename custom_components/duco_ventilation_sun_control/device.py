# === custom_components/duco_ventilation_sun_control/device.py ===
"""Helper functions for creating Home Assistant Device Registry entries for Duco."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo, format_mac

# Local integration imports for constants
from .const import (
    DEVICE_INFO_KEY_API_VERSION,
    DEVICE_INFO_KEY_MAC,
    DEVICE_INFO_KEY_MODEL,
    DEVICE_INFO_KEY_SERIAL,
    DEVICE_INFO_KEY_SW_VERSION,
    DOMAIN,
    NODE_INFO_KEY_DEVICE_TYPE,
    NODE_INFO_KEY_SERIAL, # Node serial for HW version
    NODE_INFO_KEY_SW_VERSION, # Node SW version
)

if TYPE_CHECKING:
    # Only import for type hints
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


def async_create_device_info(
    entry: ConfigEntry, device_data: dict[str, Any], box_node_id: int | str | None = "?"
) -> DeviceInfo:
    """Create DeviceInfo dictionary for the main Duco Ventilation Unit device.

    Args:
        entry: The config entry associated with the device.
        device_data: The normalized device information dictionary from the coordinator.
        box_node_id: The identified node ID of the main box controller.

    Returns:
        A DeviceInfo dictionary for registration.
    """
    # Determine Unique ID: Prefer Serial, fallback to MAC, then entry_id
    serial = device_data.get(DEVICE_INFO_KEY_SERIAL)
    mac = device_data.get(DEVICE_INFO_KEY_MAC)
    unique_id: str
    if serial:
        unique_id = str(serial)
    elif mac:
        # Use formatted MAC as unique ID if serial is missing
        unique_id = format_mac(mac)
    else:
        # Fallback, should ideally not happen if validation requires serial/mac
        unique_id = entry.entry_id
        _LOGGER.warning(
            "Using entry_id as unique ID for main device %s, serial/MAC missing.",
            entry.entry_id
        )

    identifiers = {(DOMAIN, unique_id)}
    connections = set()
    if mac:
        connections.add(("mac", format_mac(mac)))

    # Construct name based on agreed pattern: DucoBox (NodeID) - Serial/UniqueID
    # Use the determined unique_id (serial or MAC) in the name for consistency
    name = f"DucoBox ({box_node_id or '?'}) - {unique_id}"

    # Model and Software Version
    model = device_data.get(DEVICE_INFO_KEY_MODEL, "Duco Ventilation Unit")
    api_version = device_data.get(DEVICE_INFO_KEY_API_VERSION)
    if api_version:
        model = f"{model} (API {api_version})" # Append API version to model
    sw_version = device_data.get(DEVICE_INFO_KEY_SW_VERSION)

    # Configuration URL
    host = entry.data.get("host") # CONF_HOST is defined in const but often passed directly
    config_url = f"http://{host}" if host else None # Assumes HTTP, adjust if needed

    device_info = DeviceInfo(
        identifiers=identifiers,
        name=name,
        manufacturer="Duco",
        model=model,
        sw_version=sw_version,
        configuration_url=config_url,
    )
    # Add connections if available
    if connections:
        device_info["connections"] = connections

    return device_info


def async_create_node_device_info(
    main_device_unique_id: str, # Pass the main device's unique ID (serial/mac)
    node_id: int,
    node_info: dict[str, Any],
) -> DeviceInfo:
    """Create DeviceInfo dictionary for a specific Duco Node device.

    Args:
        main_device_unique_id: The unique ID (serial/MAC) of the parent DucoBox.
        node_id: The ID number of this node.
        node_info: The normalized info dictionary for this node from the coordinator.

    Returns:
        A DeviceInfo dictionary for registration.
    """
    # Node Unique ID: MainDeviceUniqueID_node_NodeID
    node_unique_id = f"{main_device_unique_id}_node_{node_id}"
    identifiers = {(DOMAIN, node_unique_id)}

    # Construct name: Type (ID) - MainDeviceSerial/UniqueID
    node_type = node_info.get(NODE_INFO_KEY_DEVICE_TYPE, "Node") # Default to "Node"
    name = f"{node_type} ({node_id}) - {main_device_unique_id}"

    # Model, SW Version, HW Version (using node serial)
    model = str(node_type) # Use type code as model
    sw_version = node_info.get(NODE_INFO_KEY_SW_VERSION)
    # Use the node's specific serial number as hardware version if available
    hw_version = node_info.get(NODE_INFO_KEY_SERIAL)

    device_info = DeviceInfo(
        identifiers=identifiers,
        name=name,
        manufacturer="Duco", # Assume same manufacturer
        model=model,
        sw_version=sw_version,
        hw_version=hw_version,
        # Link node device to the main DucoBox device
        via_device=(DOMAIN, main_device_unique_id),
    )

    return device_info