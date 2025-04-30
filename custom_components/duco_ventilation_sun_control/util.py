# === custom_components/duco_ventilation_sun_control/util.py ===
"""Utility functions for the Duco Ventilation System integration."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def get_nested_value(
    data: dict[str, Any] | list[Any] | None,
    *keys: str | int,
    value_key: str | None = None,
    default: Any | None = None,
) -> Any:
    """Safely retrieve a potentially nested value from dicts and lists.

    Traverses the data structure using the provided keys. Supports mixed
    dictionary keys (str) and list indices (int). If a `value_key` is provided,
    and the final traversed element is a dictionary, it attempts to return the
    value associated with `value_key` within that dictionary.

    Args:
        data:       The dictionary or list to traverse.
        *keys:      A sequence of keys/indices representing the path to the desired value.
        value_key:  Optional final key to extract from the nested dictionary
                    found at the location specified by *keys.
                    If the element at *keys is not a dict, this is ignored.
        default:    The value to return if any key/index is not found, the data is
                    None, or an error occurs during traversal.

    Returns:
        The retrieved value, or the default value if not found or an error occurs.

    Example:
        data = {"a": {"b": [{"c": 10}, {"d": 20}]}}
        get_nested_value(data, "a", "b", 0, value_key="c") -> 10
        get_nested_value(data, "a", "b", 1) -> {"d": 20}
        get_nested_value(data, "a", "x") -> None (using default=None)
    """
    if data is None:
        return default

    current_level: Any = data
    try:
        # Traverse the structure using the provided path keys/indices.
        for key in keys:
            if isinstance(current_level, list):
                # Handle list indices. Check type and bounds.
                if not isinstance(key, int) or not (-(len(current_level)) <= key < len(current_level)):
                    _LOGGER.debug("Invalid list index '%s' for list: %s", key, current_level)
                    return default
                current_level = current_level[key]
            elif isinstance(current_level, dict):
                # Handle dictionary keys. Check existence.
                if key not in current_level:
                    # Allow integer keys if they exist as strings in the dict
                    str_key = str(key)
                    if isinstance(key, int) and str_key in current_level:
                        current_level = current_level[str_key]
                    else:
                        _LOGGER.debug("Key '%s' not found in dict: %s", key, list(current_level.keys()))
                        return default
                else:
                    current_level = current_level[key]
            else:
                # Cannot traverse further if not a list or dict.
                _LOGGER.debug("Cannot traverse further at key '%s'. Current level is not dict/list: %s", key, type(current_level))
                return default

        # After traversal, check if a specific value_key needs extraction.
        if value_key and isinstance(current_level, dict):
            # Return the value for value_key, or default if the key isn't present.
            return current_level.get(value_key, default)

        # Otherwise, return the element we landed on after traversing *keys.
        return current_level

    except (TypeError, IndexError) as e:
        # Handle expected errors during traversal gracefully.
        keys_repr = ".".join(map(str, keys))
        _LOGGER.debug("Traversal error at path '%s': %s", keys_repr, e)
        return default
    except Exception as e:
        # Log unexpected errors during traversal.
        keys_repr = ".".join(map(str, keys))
        _LOGGER.warning(
            "Unexpected error getting nested value at path %s: %s (%s). Data: %s",
            keys_repr, e, type(e).__name__, data, exc_info=True
        )
        return default