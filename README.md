# === custom_components/duco_ventilation_sun_control/README.md ===
# Duco Ventilation System Integration for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][maintenance]

**Connect your Duco Ventilation System (DucoBox Silent Connect / DucoBox Focus) to Home Assistant.**

!!!Work in progress, please wait for a release. v1 support expected in a couple weeks, v2 following later. !!!

_Component built using the [Home Assistant Blueprint][blueprint]._

**This component will set up the following platforms:**

- Binary Sensor
- Button
- Fan
- Number
- Select
- Sensor
- Switch
- Text
- Time

## Installation

### Prerequisites

- A Duco Ventilation System (e.g., DucoBox Silent Connect, DucoBox Focus) connected to your local network.
- Know the IP address or hostname of your DucoBox unit.
- For Duco API V2 (newer units), you will need the API Key found in the unit's configuration interface.

### Installation Methods

1.  **HACS (Recommended):**
    * Ensure you have [HACS (Home Assistant Community Store)](https://hacs.xyz/) installed.
    * Add this repository as a custom repository in HACS (Settings -> HACS -> Integrations -> 3 dots -> Custom repositories). URL: `https://github.com/HilkoLantinga/duco_ventilation_sun_control`, Category: Integration.
    * Search for "Duco Ventilation System" in the HACS Integrations section and click Install.
    * Restart Home Assistant.
    * Proceed to [Configuration](#configuration).
    2.  **Manual Installation:**
    * Download the latest release `.zip` file from the [Releases page][releases].
    * Unpack the release zip file.
    * Copy the `custom_components/duco_ventilation_sun_control/` directory into your Home Assistant `custom_components` directory. Create the `custom_components` directory if it doesn't exist.
    * Restart Home Assistant.
    * Proceed to [Configuration](#configuration).

## Configuration

Configuration is handled entirely through the Home Assistant UI (Integrations page):

1.  Go to **Settings** -> **Devices & Services**.
2.  Click the **+ Add Integration** button.
3.  Search for "**Duco Ventilation System**" and select it.
4.  **Enter the Hostname or IP Address** of your DucoBox unit and click **Submit**.
5.  The integration will attempt to connect and determine the API version:
    * **API V1:** If successful, the integration will be added.
    * **API V2:** If an API V2 unit is detected, you will be prompted to **Enter the API Key**. Find this key in your Duco unit's settings and enter it. Click **Submit**.
6.  If the connection and authentication (if required) are successful, the integration will be set up, and devices/entities will be added.

**Zeroconf Discovery:** The integration supports automatic discovery via Zeroconf/Bonjour. If a Duco unit is found on your network, it should appear under "Discovered" on the Integrations page, allowing for one-click setup (you'll still need the API key for V2).

## Options

After setup, you can configure additional options:

1.  Go to **Settings** -> **Devices & Services**.
2.  Find the Duco Ventilation System integration card.
3.  Click **Configure**.
4.  Adjust the following settings:
    * **Polling Interval:** How often Home Assistant should request data from the DucoBox (seconds). Default: 60 seconds.
    * **Request Timeout:** How long to wait for a response from the DucoBox before timing out (seconds). Default: 10 seconds.
    * **Request Retries:** How many times to retry a failed request before giving up. Default: 3 retries (4 total attempts).
    * **Retry Delay:** Initial delay between retries (seconds). Uses exponential backoff. Default: 1.0 second.
    * **Command Queue Delay:** Minimum delay between sending commands to the DucoBox (seconds). Helps prevent overwhelming the device. Default: 0.5 seconds.

## Entities

This integration provides a wide range of entities representing the state and configuration of your DucoBox and connected nodes (sensors/valves). These include:

* **Fan:** Main ventilation fan control (speed, presets).
* **Sensors:** Temperature, Humidity, CO2 levels (if sensors are present), power consumption, device status, error codes, etc.
* **Binary Sensors:** Error status, calibration status, installer mode, link status, etc.
* **Switches:** Toggle configuration settings like DHCP, NightBoost active, VentCool days, installer mode, etc.
* **Numbers:** Adjust configuration setpoints (CO2, RH, manual levels), timeouts, Modbus settings, etc. Includes a slider for manual fan speed overrule.
* **Selects:** Choose options like NightBoost months, VentCool mode, calibration commands, node operating state (manual/auto/away).
* **Text:** View/Set text-based configuration like timezone or node location names. **Note:** Setting IP addresses via text entities is disabled for safety.
* **Time:** Configure start/stop times for features like NightBoost and VentCool.
* **Buttons:** Trigger actions like rebooting the box, clearing the network, resetting nodes, or syncing time.

Entities are linked to devices in the Home Assistant Device Registry:

* **Main Device:** Represents the DucoBox itself (e.g., `DucoBox (1) - PRSN123456`). Contains box-level entities.
* **Node Devices:** Represent connected sensors or valves (e.g., `UCCO2 (137) - PRSN123456`). Contain node-specific entities and are linked to the Main Device.

## Known Issues / Limitations

* Work in progress, please wait for a release. v1 support expected in a couple weeks, v2 following later. 
* Setting IP configuration parameters (Static IP, Netmask, Gateway) via Home Assistant is complex due to API differences and potential network disruption. Use the device's own interface for network setup.

## Troubleshooting

* **Cannot Connect:** Double-check the IP address/hostname. Ensure the DucoBox is powered on and connected to the same network as Home Assistant. Check firewall rules if applicable. Increase the Request Timeout option if your network is slow.
* **Invalid Auth:** For V2 API units, ensure the API Key is entered correctly. Regenerate the key on the Duco device if necessary.
* **Entities Unavailable:** Check the Home Assistant logs (`home-assistant.log`) for errors related to the `duco_ventilation_sun_control` domain or the `duco_api` library. Ensure the Polling Interval is appropriate. Check if the DucoBox itself is responsive.
* Enable debug logging for the integration to get more detailed information:
    ```yaml
    # configuration.yaml
    logger:
      default: info
      logs:
        custom_components.duco_ventilation_sun_control: debug
        duco_api: debug # Also log the underlying library
    ```

## Contributions are welcome!

If you want to contribute to this integration, please read the [Contribution Guidelines](DEVELOPMENT.md).

---

[blueprint]: https://github.com/custom-components/integration_blueprint
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/HilkoLantinga/duco_ventilation_sun_control.svg?style=for-the-badge
[commits]: https://github.com/HilkoLantinga/duco_ventilation_sun_control/commits/main
[license]: https://github.com/HilkoLantinga/duco_ventilation_sun_control/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/HilkoLantinga/duco_ventilation_sun_control.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40HilkoLantinga-blue.svg?style=for-the-badge
[maintenance]: https://github.com/HilkoLantinga
[releases-shield]: https://img.shields.io/github/v/release/HilkoLantinga/duco_ventilation_sun_control?display_name=tag&sort=semver&style=for-the-badge
[releases]: https://github.com/HilkoLantinga/duco_ventilation_sun_control/releases
