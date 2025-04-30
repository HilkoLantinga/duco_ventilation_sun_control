# === custom_components/duco_ventilation_sun_control/options_flow.py ===
"""Options flow for Duco Ventilation System integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_COMMAND_QUEUE_DELAY,
    CONF_REQUEST_RETRIES,
    CONF_REQUEST_TIMEOUT,
    CONF_RETRY_DELAY,
    CONF_SCAN_INTERVAL,
    DEFAULT_COMMAND_QUEUE_DELAY,
    DEFAULT_REQUEST_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class DucoOptionsFlowHandler(OptionsFlow):
    """Handle configuration options for the Duco integration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        # We can store current options to pre-populate the form
        self.current_options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options for the Duco integration.

        Args:
            user_input: User input from the options form.

        Returns:
            A FlowResult indicating the outcome of the step.
        """
        if user_input is not None:
            _LOGGER.debug("Updating options: %s", user_input)
            # Validate input (basic type checks done by voluptuous)
            # Additional validation could be added here if needed

            # Update the options stored in the config entry
            # self.hass.config_entries.async_update_entry(
            #     self.config_entry, options=user_input
            # )
            # Instead of direct update, create_entry merges new options
            return self.async_create_entry(title="", data=user_input)

        # Define the schema for the options form, using current values as defaults
        schema = vol.Schema({
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=self.current_options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
                ),
            ): NumberSelector(NumberSelectorConfig(
                min=10, # Minimum reasonable polling interval
                max=3600, # Maximum 1 hour
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            )),
            vol.Required(
                CONF_REQUEST_TIMEOUT,
                default=self.current_options.get(
                    CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT
                ),
            ): NumberSelector(NumberSelectorConfig(
                min=5,
                max=60,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            )),
            vol.Required(
                CONF_REQUEST_RETRIES,
                default=self.current_options.get(
                    CONF_REQUEST_RETRIES, DEFAULT_REQUEST_RETRIES
                ),
            ): NumberSelector(NumberSelectorConfig(
                min=0, # 0 retries means 1 attempt total
                max=10,
                step=1,
                mode=NumberSelectorMode.BOX,
            )),
            vol.Required(
                CONF_RETRY_DELAY,
                default=self.current_options.get(
                    CONF_RETRY_DELAY, DEFAULT_RETRY_DELAY
                ),
            ): NumberSelector(NumberSelectorConfig(
                min=0.5,
                max=10.0,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            )),
            vol.Required(
                CONF_COMMAND_QUEUE_DELAY,
                default=self.current_options.get(
                    CONF_COMMAND_QUEUE_DELAY, DEFAULT_COMMAND_QUEUE_DELAY
                ),
            ): NumberSelector(NumberSelectorConfig(
                min=0.1,
                max=5.0,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            )),
        })

        # Show the options form to the user
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            # Add description placeholders if needed for context
            # description_placeholders={"device_name": self.config_entry.title},
        )