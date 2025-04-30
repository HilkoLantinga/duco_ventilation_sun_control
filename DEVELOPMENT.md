# === custom_components/duco_ventilation_sun_control/DEVELOPMENT.md ===
# Development Guide: Duco Ventilation System Integration

This document provides guidance for developers looking to understand, modify, or contribute to the Duco Ventilation System integration for Home Assistant.

## Code Structure

The integration follows the standard Home Assistant custom component structure:

-   **`__init__.py`**: Main entry point. Handles setup/unload of the integration instance, initializes the API client and coordinator.
-   **`manifest.json`**: Integration metadata, dependencies, requirements, version, etc.
-   **`config_flow.py`**: Handles the UI configuration process (initial setup, Zeroconf).
-   **`options_flow.py`**: Handles the UI for configuring options after initial setup (polling interval, timeouts, etc.).
*   **`api.py`**: **(Placeholder)** Contains the skeleton for the external `duco-api` library. This handles all direct communication with the Duco device, including HTTP requests, authentication, retries, normalization, and error handling. *In a final distribution, this code would reside in a separate PyPI package.*
-   **`const.py`**: Defines constants, API keys (internal names), normalized data keys, entity description keys, default values, mappings (e.g., state codes to presets), and helper functions/formatters.
-   **`coordinator.py`**: Defines the `DucoDataUpdateCoordinator` which manages polling data via the API client, processes/stores the data, identifies entities, and notifies listeners. Contains action methods called by entities.
-   **`device.py`**: Helper functions (`async_create_device_info`, `async_create_node_device_info`) to create `DeviceInfo` objects for the HA Device Registry, implementing the agreed naming scheme and linking.
-   **`entity.py`**: Defines base classes (`DucoEntity`, `DucoNodeEntity`, `DucoBoxNodeEntity`) providing common logic for all Duco entities (coordinator linking, availability, state processing).
-   **`exceptions.py`**: Defines custom integration-specific exceptions (though most errors are expected from the API library or mapped to standard HA exceptions).
-   **`util.py`**: General utility functions (currently `get_nested_value`).
-   **Platform files (`sensor.py`, `fan.py`, `switch.py`, etc.)**: Implement the setup for each entity platform and define the platform-specific entity classes inheriting from the base classes in `entity.py`. They handle translating the coordinator's data into HA states and calling coordinator action methods.
-   **`diagnostics.py`**: Implements the diagnostics data generation, redacting sensitive info.
-   **`translations/`**: Contains translation files (`en.json`, `nl.json`, etc.) for UI elements, entity names/states, and error messages.
-   **`tests/`**: (Placeholder) Intended for unit and functional tests.

## External Library (`duco-api`)

A core principle of this integration (especially for Platinum quality) is the separation of API communication into an external library.

-   **Interface:** The integration *only* interacts with the methods and objects provided by the `DucoApiClient` class (defined conceptually in `api.py` for now). It *never* makes direct HTTP requests to the Duco device.
-   **Responsibilities:** The external library is responsible for:
    -   Handling HTTP requests (async).
    -   Managing authentication (API key for V2).
    *   Implementing retry logic (`tenacity`).
    -   Handling timeouts.
    -   Normalizing data from V1/V2 API responses into a consistent internal format (defined by the normalized keys in `const.py`).
    -   Raising specific exceptions (`ApiAuthError`, `ApiConnectionError`, `ApiError`, etc.) on failure.
    -   Supporting `aiohttp.ClientSession` injection.
    -   (Optional but recommended) Providing a basic CLI interface for standalone testing (e.g., via `python -m duco_api ...`).

## Development Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/ha-duco-rewrite.git
    cd ha-duco-rewrite
    ```
2.  **Set up a Home Assistant Development Environment:** Follow the official [Developer Setup guide](https://developers.home-assistant.io/docs/development_setup). Using Docker or Python venv is recommended.
3.  **Link the Custom Component:** Create a symbolic link from your Home Assistant configuration's `custom_components` directory to the `custom_components/duco_ventilation_sun_control` directory within your cloned repository.
    ```bash
    # Example assuming HA config is in ~/homeassistant/config
    # and repo cloned in ~/dev/ha-duco-rewrite
    ln -s ~/dev/ha-duco-rewrite/custom_components/duco_ventilation_sun_control ~/homeassistant/config/custom_components/duco_ventilation_sun_control
    ```
4.  **Install Development Dependencies:** If using a venv, activate it and install requirements (if any specific dev requirements are added later). For now, the main requirement (`duco-api`) is handled by HA loading the component.
5.  **Restart Home Assistant:** Allow HA to pick up the linked custom component.
6.  **Configure the Integration:** Add the Duco integration via the UI.

## Running Linters and Formatters

This project uses `ruff` for formatting and linting to ensure code quality and consistency with Home Assistant standards.

1.  **Install Ruff:** `pip install ruff`
2.  **Format Code:** `ruff format .`
3.  **Check Linting:** `ruff check .`
4.  **Auto-fix (where possible):** `ruff check . --fix`

Ensure code passes `ruff format` and `ruff check` before submitting contributions.

## Contribution Guidelines

1.  **Fork the Repository:** Create your own fork on GitHub.
2.  **Create a Branch:** Make your changes in a dedicated branch (e.g., `feature/add-eco-mode` or `fix/connection-retry-logic`).
3.  **Make Changes:** Implement your feature or fix. Ensure code is well-commented and follows HA development best practices.
4.  **Add Tests:** (Future Goal) Add relevant unit tests for new logic. Aim for high test coverage.
5.  **Lint and Format:** Run `ruff format .` and `ruff check . --fix`.
6.  **Update Documentation:** If your change affects users (new features, options, changed behavior), update `README.md`. Update this `DEVELOPMENT.md` if relevant.
7.  **Submit a Pull Request:** Create a PR from your branch to the main repository's `main` branch. Provide a clear description of your changes.

## Key Design Principles

-   **Coordinator Pattern:** Data fetching is centralized in the `DataUpdateCoordinator`. Entities subscribe to updates rather than polling individually.
-   **External API Library:** Strict separation of concerns. Integration code handles HA logic; library handles device communication.
-   **Constants:** Use constants defined in `const.py` extensively for keys, states, etc., to avoid magic strings/numbers.
-   **Error Handling:** Use specific exceptions and map them appropriately to user-facing HA errors or `UpdateFailed`/`ConfigEntryNotReady`.
-   **Strict Typing:** Use full Python type hints (`typing`) throughout the codebase.
-   **Asynchronous:** All I/O operations (API calls) must be `async`.