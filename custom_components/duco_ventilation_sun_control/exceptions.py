# === custom_components/duco_ventilation_sun_control/exceptions.py ===
"""Custom exception classes for the Duco Ventilation System integration."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


class DucoVentilationSystemError(HomeAssistantError):
    """Generic base exception for the Duco Ventilation System integration."""
    # Use this as a base for any integration-specific errors


# Example of a more specific internal error (currently unused):
# class DucoConfigurationError(DucoVentilationSystemError):
#     """Exception raised for configuration errors detected within the integration logic."""
#     pass

# Example:
# class DucoStateError(DucoVentilationSystemError):
#     """Exception raised for unexpected internal state issues."""
#     pass