# === custom_components/duco_ventilation_sun_control/diagnostics.py ===
"""Diagnostics support for the Duco Ventilation System integration."""

from __future__ import annotations

import copy
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.redact import async_redact_data

# Local integration imports
from .api import DucoApiClient # Import the API client type hint
from .const import (
    DEVICE_INFO_KEY_IP,
    DEVICE_INFO_KEY_MAC,
    DEVICE_INFO_KEY_SERIAL,
    DOMAIN,
    NODE_INFO_KEY_DUCO_SERIAL,
    NODE_INFO_KEY_LOCATION,
    NODE_INFO_KEY_SERIAL,
)
from .coordinator import DucoCoordinatorData, DucoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Keys in config_entry.data and config_entry.options to redact
# Add username/password if they were ever used for other auth methods
REDACTED_CONFIG_KEYS = {
    CONF_API_KEY,
    CONF_HOST,
    # CONF_USERNAME,
    # CONF_PASSWORD,
}

# Keys within the coordinator data object that might contain PII
REDACTED_DATA_KEYS = {
    DEVICE_INFO_KEY_IP,
    DEVICE_INFO_KEY_MAC,
    DEVICE_INFO_KEY_SERIAL,
    NODE_INFO_KEY_DUCO_SERIAL,
    NODE_INFO_KEY_LOCATION,
    NODE_INFO_KEY_SERIAL,
    # Add other potential keys like RFHomeID if sensitive
    # DEVICE_INFO_KEY_RF_HOME_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics information for a Duco config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry for which to get diagnostics.

    Returns:
        A dictionary containing the diagnostics data, with sensitive info redacted.
    """
    # Get the coordinator instance associated with this config entry
    coordinator: DucoDataUpdateCoordinator | None = hass.data[DOMAIN].get(entry.entry_id)

    # Start with redacted config entry data
    diag_data: dict[str, Any] = {
        "config_entry_info": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(entry.data, REDACTED_CONFIG_KEYS),
            "options": async_redact_data(entry.options, REDACTED_CONFIG_KEYS),
            "disabled_by": entry.disabled_by,
            "source": entry.source,
            "unique_id": entry.unique_id, # Already redacted if derived from sensitive data
        }
    }

    # If coordinator isn't available yet or setup failed
    if not coordinator:
        diag_data["error"] = "Coordinator instance not found. Integration may not be running."
        return diag_data

    # Add details about the API client configuration
    api_client: DucoApiClient | None = getattr(coordinator, "api", None)
    if api_client:
        # Redact host from base URL if possible
        redacted_base_url = getattr(api_client, "_base_url", "unknown")
        host = getattr(api_client, "_host", None)
        if isinstance(redacted_base_url, str) and host:
            redacted_base_url = redacted_base_url.replace(host, "**REDACTED_HOST**")

        diag_data["api_client_config"] = {
            "api_version": getattr(api_client, "_api_version", "unknown"),
            "base_url": redacted_base_url,
            "timeout": getattr(api_client, "_timeout", "unknown"),
            "retries": getattr(api_client, "_retries", "unknown"),
            "retry_delay": getattr(api_client, "_retry_delay", "unknown"),
            "command_delay": getattr(api_client, "_command_delay", "unknown"),
            "has_api_key": getattr(api_client, "_api_key", None) is not None,
        }
    else:
        diag_data["api_client_config"] = {"error": "API Client instance not found on coordinator."}

    # Add coordinator status information
    diag_data["coordinator_status"] = {
        "last_update_success": coordinator.last_update_success,
        "update_interval": str(coordinator.update_interval),
        "listeners": len(getattr(coordinator, "_listeners", {})),
    }

    # Include the latest data fetched by the coordinator, redacted
    coordinator_data_output = {}
    if coordinator.data and isinstance(coordinator.data, DucoCoordinatorData):
        try:
            # Convert relevant parts of the dataclass to a dictionary for redaction
            # Avoid dumping the full entity list/descriptions, provide summary instead.
            data_dict = {
                "device_info": coordinator.data.device_info,
                "general_config": coordinator.data.general_config,
                "nodes": coordinator.data.nodes,
                "entities_summary": {
                    "count": len(coordinator.data.entities),
                    "platforms": sorted(list({str(e.platform) for e in coordinator.data.entities})),
                    "box_node_id": getattr(coordinator, "_box_node_id", "unknown"),
                },
            }
            # IMPORTANT: Deepcopy before redacting to avoid modifying live data
            data_dict_copy = copy.deepcopy(data_dict)
            # Redact sensitive fields within the copied data
            coordinator_data_output = async_redact_data(data_dict_copy, REDACTED_DATA_KEYS)
        except Exception as e:
            _LOGGER.error("Error preparing coordinator data for diagnostics: %s", e)
            coordinator_data_output = {"error": f"Failed to process coordinator data: {e}"}
    elif coordinator.data is not None:
        coordinator_data_output = {
            "error": f"Coordinator data is not the expected type: {type(coordinator.data)}"
        }
    else:
        coordinator_data_output = {"message": "Coordinator data is currently None (initial fetch may have failed)."}

    diag_data["coordinator_data"] = coordinator_data_output

    return diag_data