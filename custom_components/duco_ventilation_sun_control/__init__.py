# === custom_components/duco_ventilation_sun_control/__init__.py ===
"""The Duco Ventilation System integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

# External library for Duco API communication (placeholder)
# In a real scenario, this would be: from duco_api import DucoApiClient, ApiAuthError, ...
from .api import (  # noqa: F401 # pylint: disable=unused-import Used for type hinting
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    DucoApiClient,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

# Local integration imports
from .const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_COMMAND_QUEUE_DELAY,
    CONF_REQUEST_RETRIES,
    CONF_REQUEST_TIMEOUT,
    CONF_RETRY_DELAY,
    DEFAULT_COMMAND_QUEUE_DELAY,
    DEFAULT_REQUEST_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    PLATFORMS,
    TRANS_ERROR_CANNOT_CONNECT,
    TRANS_ERROR_INVALID_AUTH,
    TRANS_ERROR_UNKNOWN,
)
from .coordinator import DucoDataUpdateCoordinator

if TYPE_CHECKING:
    # This avoids a circular import and allows type hinting
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Duco Ventilation System component."""
    # This integration does not support configuration via configuration.yaml.
    # Setup is handled entirely through the config flow and async_setup_entry.
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug("Initialized Duco domain in hass.data.")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Duco Ventilation System from a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry representing the Duco device connection.

    Returns:
        True if the setup was successful.

    Raises:
        ConfigEntryAuthFailed:  If authentication fails (e.g., invalid API key).
        ConfigEntryNotReady:    If the coordinator fails its initial refresh due
                                to connection issues or other API errors.
    """
    _LOGGER.info("Setting up Duco integration entry: %s", entry.entry_id)

    # Extract configuration from the entry's data and options
    host = entry.data[CONF_HOST]
    api_version = entry.data[CONF_API_VERSION]
    api_key = entry.data.get(CONF_API_KEY)  # May be None for V1

    # Get options with defaults
    scan_interval_seconds = entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
    )
    request_timeout = entry.options.get(
        CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT
    )
    request_retries = entry.options.get(
        CONF_REQUEST_RETRIES, DEFAULT_REQUEST_RETRIES
    )
    retry_delay = entry.options.get(CONF_RETRY_DELAY, DEFAULT_RETRY_DELAY)
    command_queue_delay = entry.options.get(
        CONF_COMMAND_QUEUE_DELAY, DEFAULT_COMMAND_QUEUE_DELAY
    )

    _LOGGER.debug(
        "Entry %s - Host: %s, API Ver: %s, Scan Interval: %ds, Timeout: %ds, "
        "Retries: %d, Retry Delay: %.1fs, Cmd Queue Delay: %.1fs",
        entry.entry_id,
        host,
        api_version,
        scan_interval_seconds,
        request_timeout,
        request_retries,
        retry_delay,
        command_queue_delay,
    )

    # Get the shared aiohttp ClientSession from Home Assistant
    session = aiohttp_client.async_get_clientsession(hass)

    # Instantiate the external API client library
    # Pass necessary configuration and options to the client library
    api_client = DucoApiClient(
        host=host,
        api_version=api_version,
        session=session,
        api_key=api_key,
        timeout=request_timeout,
        retries=request_retries,
        retry_delay=retry_delay,
        command_delay=command_queue_delay,
    )

    # Create the data update coordinator
    coordinator = DucoDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,  # Pass entry for access within coordinator
        api_client=api_client,
        scan_interval_seconds=scan_interval_seconds,
    )

    # Perform the initial data refresh.
    # This ensures the device is reachable and authenticated before setting up platforms.
    try:
        _LOGGER.debug("Performing initial data refresh for entry %s...", entry.entry_id)
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.debug("Initial data refresh successful for entry %s.", entry.entry_id)
    except ApiAuthError as err:
        # Map authentication errors from the library to ConfigEntryAuthFailed.
        _LOGGER.error(
            "Authentication failed for %s: %s", host, err, exc_info=True
        )
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key=TRANS_ERROR_INVALID_AUTH
        ) from err
    except ApiConnectionError as err:
        # Map connection errors from the library to ConfigEntryNotReady.
        _LOGGER.error("Connection error for %s: %s", host, err, exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key=TRANS_ERROR_CANNOT_CONNECT
        ) from err
    except (ApiError, Exception) as err:
        # Map other API errors or unexpected exceptions to ConfigEntryNotReady.
        _LOGGER.exception(
            "Unexpected error during initial refresh for %s", host
        )
        # Use a generic translatable message or fallback to error string
        # Note: ConfigEntryNotReady expects str, not HomeAssistantError.
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key=TRANS_ERROR_UNKNOWN,
            translation_placeholders={"error_details": str(err)},
        ) from err

    # Check if coordinator has data after refresh (should not be None if no exception)
    if coordinator.data is None:
        _LOGGER.error(
            "Coordinator data is None after successful initial refresh for %s",
            entry.entry_id,
        )
        raise ConfigEntryNotReady(
            f"Coordinator data missing after initial refresh for {entry.title}"
        )

    # Store the coordinator instance in hass.data, keyed by entry_id.
    # Platforms will retrieve it from here.
    hass.data[DOMAIN][entry.entry_id] = coordinator
    _LOGGER.debug(
        "Stored coordinator for entry %s in hass.data.", entry.entry_id
    )

    # Forward the setup to all defined platforms (sensor, fan, switch, etc.).
    # This will call the async_setup_entry function in each platform's .py file.
    _LOGGER.debug("Forwarding setup to platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up a listener for options updates.
    # This allows the integration to react to changes made via the Options Flow UI.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Successfully set up Duco integration for %s", entry.title)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Duco config entry.

    Called when the integration is removed or disabled. It unloads associated
    platforms and cleans up resources stored in hass.data.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry to unload.

    Returns:
        True if the unload was successful.
    """
    _LOGGER.info("Unloading Duco integration entry: %s", entry.entry_id)

    # Unload platforms associated with this config entry.
    # This calls the async_unload_entry function in each platform's .py file.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove the coordinator from hass.data if unload was successful.
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator:
            _LOGGER.debug(
                "Removed coordinator from hass.data for entry %s.", entry.entry_id
            )
            # Potentially add coordinator cleanup if needed (e.g., cancelling tasks)
        else:
            _LOGGER.warning(
                "Coordinator not found in hass.data during unload for entry %s.",
                entry.entry_id,
            )

        # If this was the last Duco entry, remove the domain from hass.data.
        if DOMAIN in hass.data and not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
            _LOGGER.debug("Removed DOMAIN '%s' from hass.data.", DOMAIN)

        _LOGGER.info(
            "Successfully unloaded Duco integration for %s.", entry.title
        )
    else:
        _LOGGER.error(
            "Failed to unload one or more Duco platforms for %s.", entry.title
        )

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update via the UI.

    This listener triggers a reload of the config entry, which will then call
    async_unload_entry followed by async_setup_entry, applying the new options.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry that was updated.
    """
    _LOGGER.info("Reloading Duco entry %s due to options update.", entry.entry_id)
    # The standard way to handle option updates is to reload the entry.
    await hass.config_entries.async_reload(entry.entry_id)
    _LOGGER.debug("Duco entry %s reloaded.", entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry from older versions if necessary."""
    _LOGGER.debug(
        "Checking migration for Duco config entry version %s (Current: %s)",
        config_entry.version,
        config_entry.VERSION, # Access VERSION defined in ConfigFlow
    )
    # Example migration logic (uncomment and adapt if needed):
    # if config_entry.version == 1:
    #     _LOGGER.info("Migrating config entry from version 1 to 2")
    #     new_data = {**config_entry.data, "new_option": "default_value"}
    #     config_entry.version = 2
    #     hass.config_entries.async_update_entry(config_entry, data=new_data)
    #     _LOGGER.info("Migration to version 2 successful")

    # Return True to indicate migration was successful or not needed.
    # Return False if migration fails and setup should be aborted.
    return True