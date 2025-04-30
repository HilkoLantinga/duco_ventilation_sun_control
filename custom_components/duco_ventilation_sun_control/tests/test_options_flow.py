# === tests/test_options_flow.py ===
"""Test the Duco Ventilation System options flow."""

from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.duco_ventilation_sun_control.const import (
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

# Import fixtures
from .conftest import MOCK_HOST_V1, setup_integration_v1


async def test_options_flow_init_show_form(
    hass: HomeAssistant, mock_config_entry_v1: ConfigEntry
) -> None:
    """Test that initializing the options flow shows the form with defaults."""
    # Add the entry to hass
    mock_config_entry_v1.add_to_hass(hass)

    # Initiate the options flow
    result = await hass.config_entries.options.async_init(mock_config_entry_v1.entry_id)

    # Check that the form is shown
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    # Check that the schema defaults match the constants
    schema = result["data_schema"].schema
    assert schema[CONF_SCAN_INTERVAL].default == DEFAULT_SCAN_INTERVAL_SECONDS
    assert schema[CONF_REQUEST_TIMEOUT].default == DEFAULT_REQUEST_TIMEOUT
    assert schema[CONF_REQUEST_RETRIES].default == DEFAULT_REQUEST_RETRIES
    assert schema[CONF_RETRY_DELAY].default == DEFAULT_RETRY_DELAY
    assert schema[CONF_COMMAND_QUEUE_DELAY].default == DEFAULT_COMMAND_QUEUE_DELAY


async def test_options_flow_init_show_form_existing_options(
    hass: HomeAssistant, mock_config_entry_v1: ConfigEntry
) -> None:
    """Test that initializing the options flow shows the form with existing option values."""
    # Set some existing options
    existing_options = {
        CONF_SCAN_INTERVAL: 120,
        CONF_REQUEST_TIMEOUT: 15,
        CONF_REQUEST_RETRIES: 5,
        CONF_RETRY_DELAY: 2.0,
        CONF_COMMAND_QUEUE_DELAY: 0.8,
    }
    hass.config_entries.async_update_entry(mock_config_entry_v1, options=existing_options)
    await hass.async_block_till_done()

    # Initiate the options flow
    result = await hass.config_entries.options.async_init(mock_config_entry_v1.entry_id)

    # Check that the form is shown with existing values as defaults
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert schema[CONF_SCAN_INTERVAL].default == 120
    assert schema[CONF_REQUEST_TIMEOUT].default == 15
    assert schema[CONF_REQUEST_RETRIES].default == 5
    assert schema[CONF_RETRY_DELAY].default == 2.0
    assert schema[CONF_COMMAND_QUEUE_DELAY].default == 0.8


async def test_options_flow_submit_success(
    hass: HomeAssistant, mock_config_entry_v1: ConfigEntry
) -> None:
    """Test successfully submitting new options."""
    # Add the entry to hass
    mock_config_entry_v1.add_to_hass(hass)

    # Define new options
    new_options = {
        CONF_SCAN_INTERVAL: 90,
        CONF_REQUEST_TIMEOUT: 20,
        CONF_REQUEST_RETRIES: 2,
        CONF_RETRY_DELAY: 1.5,
        CONF_COMMAND_QUEUE_DELAY: 0.6,
    }

    # Initiate the options flow
    result = await hass.config_entries.options.async_init(mock_config_entry_v1.entry_id)
    # Submit the new options
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=new_options
    )
    await hass.async_block_till_done()

    # Check that the flow finished and created an empty entry (which updates options)
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "" # Title is empty for options flow updates
    assert result2["data"] == new_options

    # Check that the config entry's options have been updated
    assert mock_config_entry_v1.options == new_options


# Note: Testing invalid input (e.g., non-numeric) is difficult here
# because the frontend selectors and voluptuous schema handle basic validation.
# Testing specific out-of-range values would require mocking the NumberSelector
# or directly testing the schema validation logic if it were more complex.
# For now, we assume the NumberSelector enforces min/max/step defined in options_flow.py.