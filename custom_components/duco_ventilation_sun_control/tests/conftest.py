# === tests/conftest.py ===
"""Common fixtures and patches for Duco tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# Import constants from the integration
from custom_components.duco_ventilation_sun_control.const import (
    API_V1,
    API_V2,
    CONF_API_VERSION,
    DOMAIN,
    # Add keys used in mock data structures if not already present
    DEVICE_INFO_KEY_API_VERSION,
    DEVICE_INFO_KEY_CALIB_STATE,
    DEVICE_INFO_KEY_CALIB_VALID,
    DEVICE_INFO_KEY_DEVICE_TIME,
    DEVICE_INFO_KEY_INSTALLER_STATE,
    DEVICE_INFO_KEY_IP,
    DEVICE_INFO_KEY_MAC,
    DEVICE_INFO_KEY_MODEL,
    DEVICE_INFO_KEY_POWER_AVG,
    DEVICE_INFO_KEY_POWER_MAX, # V1 doesn't seem to have this in boxinfo, V2 does
    DEVICE_INFO_KEY_POWER_NOW,
    DEVICE_INFO_KEY_PRESSURE_OUT, # V1 doesn't seem to have this in boxinfo, V2 does
    DEVICE_INFO_KEY_PRESSURE_TOTAL,
    DEVICE_INFO_KEY_RF_HOME_ID,
    DEVICE_INFO_KEY_SERIAL,
    DEVICE_INFO_KEY_SW_VERSION,
    DEVICE_INFO_KEY_UPTIME,
    DEVICE_INFO_KEY_WEATHER_PRESENT,
    # Node Info Keys
    NODE_INFO_KEY_ACTUAL_LEVEL,
    NODE_INFO_KEY_ASSO_ID,
    NODE_INFO_KEY_CO2,
    NODE_INFO_KEY_COMM_ERROR_CODE,
    NODE_INFO_KEY_COUNTDOWN,
    NODE_INFO_KEY_DEVICE_TYPE,
    NODE_INFO_KEY_DUCO_SERIAL,
    NODE_INFO_KEY_ENDTIME,
    NODE_INFO_KEY_ERROR_CODE,
    NODE_INFO_KEY_ERROR_STATUS,
    NODE_INFO_KEY_ID,
    NODE_INFO_KEY_LINK,
    NODE_INFO_KEY_LOCATION,
    NODE_INFO_KEY_MODE,
    NODE_INFO_KEY_OVERRULE_PCT,
    NODE_INFO_KEY_PARENT_ID,
    NODE_INFO_KEY_RH,
    NODE_INFO_KEY_RSSI,
    NODE_INFO_KEY_SENSOR_DEMAND,
    NODE_INFO_KEY_SERIAL,
    NODE_INFO_KEY_SHOW,
    NODE_INFO_KEY_STATE,
    NODE_INFO_KEY_SUB_TYPE,
    NODE_INFO_KEY_SW_VERSION,
    NODE_INFO_KEY_TARGET_LEVEL,
    NODE_INFO_KEY_TEMP,
)

# Import API client exceptions for mocking
from custom_components.duco_ventilation_sun_control.api import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    DucoApiClient,
)

# --- V1 Mock Data (Based on User Provided Data) ---
MOCK_HOST_V1 = "192.168.1.97"
MOCK_SERIAL_V1 = "PRSN22442632" # Full serial for matching
MOCK_SERIAL_V1_REDACTED = "PRSN2244..." # Redacted for display/logs if needed
MOCK_MAC_V1 = "00:08:5f:35:aa:9f" # Full MAC for matching
MOCK_MAC_V1_FORMATTED = "00:08:5F:35:AA:9F" # Formatted version

MOCK_USER_INPUT_V1 = {CONF_HOST: MOCK_HOST_V1}
MOCK_CONFIG_DATA_V1 = {
    CONF_HOST: MOCK_HOST_V1,
    CONF_API_VERSION: API_V1,
    CONF_API_KEY: None,
}

# Raw V1 API Responses
MOCK_RAW_BOARD_INFO_V1 = {
    "serial": MOCK_SERIAL_V1,
    "uptime": 308989,
    "swversion": "16036.14.1.0",
    "apiversion": "1.0.0.0",
    "mac": MOCK_MAC_V1,
    "ip": MOCK_HOST_V1
}
MOCK_RAW_BOXINFO_V1 = {
    "General": {"Time": 1744986821, "RFHomeID": "0x000B1643", "InstallerState": "OPERATIONAL"},
    "Calibration": {"CalibIsValid": True, "CalibState": "IDLE", "CalibError": "0x0000", "KvalueOut": 253680},
    "Performance": {"PressureTotal": 275, "PressureOut": 275, "PowerNow": 30, "PowerAvg": 13, "PowerMax": 30},
    "WeatherStation": {"Present": False}
}
MOCK_RAW_NODELIST_V1 = {"nodelist": ["1", "137", "138"]}
MOCK_RAW_NODEINFO_V1_BOX = {"node": 1, "devtype": "BOX", "subtype": 1, "netw": "VIRT", "addr": 1, "sub": 1, "prnt": 0, "asso": 0, "location": "", "state": "AUTO", "cntdwn": 0, "endtime": 0, "mode": "AUTO", "trgt": 100, "actl": 80, "ovrl": 255, "snsr": 0, "cerr": 0, "swversion": "16056.10.4.0", "serialnb": "PS2212002617", "ducoserial": "n/a", "temp": 20.5, "co2": 1256, "rh": 55, "error": "W.00.00.00", "show": 0, "link": 0}
MOCK_RAW_NODEINFO_V1_CO2 = {"node": 137, "devtype": "UCCO2", "subtype": 0, "netw": "VIRT", "addr": 1, "sub": 1, "prnt": 1, "asso": 1, "location": "", "state": "-", "cntdwn": 0, "endtime": 0, "mode": "-", "ovrl": 255, "snsr": 100, "cerr": 0, "swversion": "n/a", "serialnb": "n/a", "ducoserial": "n/a", "temp": 0, "co2": 0, "rh": 0, "error": "W.00.00.00", "show": 0, "link": 0}
MOCK_RAW_NODEINFO_V1_RH = {"node": 138, "devtype": "UCRH", "subtype": 0, "netw": "VIRT", "addr": 1, "sub": 1, "prnt": 1, "asso": 1, "location": "", "state": "-", "cntdwn": 0, "endtime": 0, "mode": "-", "ovrl": 255, "snsr": 10, "cerr": 0, "swversion": "n/a", "serialnb": "n/a", "ducoserial": "n/a", "temp": 0, "co2": 0, "rh": 0, "error": "W.00.00.00", "show": 0, "link": 0}
MOCK_RAW_NODECONFIG_V1_BOX = {"node": 1, "AutoMin": {"Val": 10, "Min": 10, "Inc": 5, "Max": 100}, "AutoMax": {"Val": 100, "Min": 10, "Inc": 5, "Max": 100}, "Capacity": {"Val": 140, "Min": 0, "Inc": 5, "Max": 750}, "Manual1": {"Val": 15, "Min": 0, "Inc": 5, "Max": 50}, "Manual2": {"Val": 50, "Min": 15, "Inc": 5, "Max": 100}, "Manual3": {"Val": 100, "Min": 50, "Inc": 5, "Max": 100}, "ManualTimeout": {"Val": 20, "Min": 5, "Inc": 5, "Max": 9995}, "Location": ""}
MOCK_RAW_NODECONFIG_V1_CO2 = {"node": 137, "CO2Setpoint": {"Val": 800, "Min": 0, "Inc": 10, "Max": 2000}, "Manual1": {"Val": 15, "Min": 0, "Inc": 5, "Max": 50}, "Manual2": {"Val": 50, "Min": 15, "Inc": 5, "Max": 100}, "Manual3": {"Val": 100, "Min": 50, "Inc": 5, "Max": 100}, "ManualTimeout": {"Val": 20, "Min": 5, "Inc": 5, "Max": 9995}, "TempDependent": {"Val": 1, "Min": 0, "Inc": 1, "Max": 1}, "SensorVisuLevel": {"Val": 0, "Min": 0, "Inc": 5, "Max": 100}, "Location": ""}
MOCK_RAW_NODECONFIG_V1_RH = {"node": 138, "RHSetpoint": {"Val": 60, "Min": 0, "Inc": 5, "Max": 90}, "RHDelta": {"Val": 1, "Min": 0, "Inc": 1, "Max": 1}, "Manual1": {"Val": 15, "Min": 0, "Inc": 5, "Max": 50}, "Manual2": {"Val": 50, "Min": 15, "Inc": 5, "Max": 100}, "Manual3": {"Val": 100, "Min": 50, "Inc": 5, "Max": 100}, "ManualTimeout": {"Val": 20, "Min": 5, "Inc": 5, "Max": 9995}, "SensorVisuLevel": {"Val": 0, "Min": 0, "Inc": 5, "Max": 100}, "Location": ""}
MOCK_RAW_BOXCONFIG_V1 = {"Time": {"TimeZone": {"Val": 1, "Min": -11, "Inc": 1, "Max": 12}, "AutoDaylightSavingTime": {"Val": 1, "Min": 0, "Inc": 1, "Max": 1}}, "Fan": {"MaxHighLevel": {"Val": 80, "Min": 0, "Inc": 1, "Max": 255}, "CalibOnMan2": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}, "GroundBound": {"Val": 1, "Min": 0, "Inc": 1, "Max": 1}, "HeadCount": {"Val": 4, "Min": 1, "Inc": 1, "Max": 4}, "PwmInverted": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}}, "VentCtrl": {"BalanceThresh": {"Val": 10, "Min": 0, "Inc": 1, "Max": 100}, "TempDependent": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}, "TempCtrlLow": {"Val": 160, "Min": 100, "Inc": 1, "Max": 240}, "TempCtrlHigh": {"Val": 240, "Min": 160, "Inc": 1, "Max": 350}}, "VentCool": {"ActiveMonday": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}, "ActiveTuesday": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}, "ActiveWednesday": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}, "ActiveThursday": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}, "ActiveFriday": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}, "ActiveSaturday": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}, "ActiveSunday": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}, "StartTime": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1439}, "StopTime": {"Val": 360, "Min": 0, "Inc": 1, "Max": 1439}, "Mode": {"Val": 0, "Min": 0, "Inc": 1, "Max": 2}, "MaxWindSpeed": {"Val": 110, "Min": 0, "Inc": 1, "Max": 200}}, "NightBoost": {"Active": {"Val": 0, "Min": 0, "Inc": 1, "Max": 1}, "StartTemp": {"Val": 23, "Min": 0, "Inc": 1, "Max": 60}, "StartMonth": {"Val": 5, "Min": 1, "Inc": 1, "Max": 12}, "StopMonth": {"Val": 9, "Min": 1, "Inc": 1, "Max": 12}, "StartTime": {"Val": 1320, "Min": 0, "Inc": 1, "Max": 1439}, "StopTime": {"Val": 480, "Min": 0, "Inc": 1, "Max": 1439}}, "Modbus": {"Address": {"Val": 1, "Min": 1, "Inc": 1, "Max": 254}, "Offset": {"Val": 1, "Min": 0, "Inc": 1, "Max": 1}, "Speed": {"Val": 1, "Min": 0, "Inc": 1, "Max": 6}, "Parity": {"Val": 0, "Min": 0, "Inc": 1, "Max": 2}, "Stopbit": {"Val": 1, "Min": 1, "Inc": 1, "Max": 2}}}
# Note: boxconfigget also included Ethernet module, ipconfigget is separate
MOCK_RAW_IPCONFIG_V1 = {"Ethernet": {"StaticIp": {"Val_A": 192, "Val_B": 168, "Val_C": 100, "Val_D": 150, "Min": 0, "Inc": 1, "Max": 255}, "NetwMask": {"Val_A": 255, "Val_B": 255, "Val_C": 255, "Val_D": 0, "Min": 0, "Inc": 1, "Max": 255}, "Gateway": {"Val_A": 192, "Val_B": 168, "Val_C": 100, "Val_D": 0, "Min": 0, "Inc": 1, "Max": 255}, "MqttBroker": {"Val_A": 192, "Val_B": 168, "Val_C": 1, "Val_D": 30, "Min": 0, "Inc": 1, "Max": 255}}}
MOCK_RAW_ECOCONFIG_V1 = {} # Empty as per user data

# Normalized V1 Device Info (Derived from raw data)
MOCK_NORMALIZED_DEVICE_INFO_V1 = {
    DEVICE_INFO_KEY_SERIAL: MOCK_SERIAL_V1,
    DEVICE_INFO_KEY_UPTIME: MOCK_RAW_BOARD_INFO_V1["uptime"],
    DEVICE_INFO_KEY_SW_VERSION: MOCK_RAW_BOARD_INFO_V1["swversion"],
    DEVICE_INFO_KEY_API_VERSION: MOCK_RAW_BOARD_INFO_V1["apiversion"],
    DEVICE_INFO_KEY_MAC: MOCK_MAC_V1_FORMATTED, # Use formatted MAC
    DEVICE_INFO_KEY_IP: MOCK_HOST_V1,
    DEVICE_INFO_KEY_DEVICE_TIME: MOCK_RAW_BOXINFO_V1["General"]["Time"],
    DEVICE_INFO_KEY_RF_HOME_ID: MOCK_RAW_BOXINFO_V1["General"]["RFHomeID"],
    DEVICE_INFO_KEY_INSTALLER_STATE: MOCK_RAW_BOXINFO_V1["General"]["InstallerState"],
    DEVICE_INFO_KEY_CALIB_VALID: MOCK_RAW_BOXINFO_V1["Calibration"]["CalibIsValid"],
    DEVICE_INFO_KEY_CALIB_STATE: MOCK_RAW_BOXINFO_V1["Calibration"]["CalibState"],
    DEVICE_INFO_KEY_PRESSURE_TOTAL: MOCK_RAW_BOXINFO_V1["Performance"]["PressureTotal"],
    DEVICE_INFO_KEY_POWER_NOW: MOCK_RAW_BOXINFO_V1["Performance"]["PowerNow"],
    DEVICE_INFO_KEY_POWER_AVG: MOCK_RAW_BOXINFO_V1["Performance"]["PowerAvg"],
    DEVICE_INFO_KEY_WEATHER_PRESENT: MOCK_RAW_BOXINFO_V1["WeatherStation"]["Present"],
    DEVICE_INFO_KEY_MODEL: "DucoBox (V1 API)", # Added by normalization
    # V1 does not provide PressureOut or PowerMax in boxinfo
    DEVICE_INFO_KEY_PRESSURE_OUT: None,
    DEVICE_INFO_KEY_POWER_MAX: None,
}


# --- V2 Mock Data (Placeholders - REPLACE with real V2 data if available) ---
MOCK_HOST_V2 = "2.2.2.2"
MOCK_API_KEY_V2 = "test-api-key-v2"
MOCK_SERIAL_V2 = "V2SERIAL123"
MOCK_MAC_V2 = "AA:BB:CC:DD:EE:FF"

MOCK_USER_INPUT_V2 = {CONF_HOST: MOCK_HOST_V2}
MOCK_USER_INPUT_V2_WITH_KEY = {
    CONF_HOST: MOCK_HOST_V2,
    CONF_API_KEY: MOCK_API_KEY_V2,
}
MOCK_CONFIG_DATA_V2 = {
    CONF_HOST: MOCK_HOST_V2,
    CONF_API_VERSION: API_V2,
    CONF_API_KEY: MOCK_API_KEY_V2,
}
# Placeholder V2 device info - Needs real data structure
MOCK_NORMALIZED_DEVICE_INFO_V2 = {
    DEVICE_INFO_KEY_SERIAL: MOCK_SERIAL_V2,
    DEVICE_INFO_KEY_MAC: MOCK_MAC_V2,
    DEVICE_INFO_KEY_API_VERSION: "2.y.z",
    DEVICE_INFO_KEY_SW_VERSION: "2.3.4",
    DEVICE_INFO_KEY_MODEL: "DucoBox Focus (V2 API)", # Example model
    # ... add other relevant V2 fields based on real data
}


# --- Fixtures ---

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None, None, None]:
    """Enable custom integrations defined in the test environment."""
    yield


@pytest.fixture
def mock_duco_api_client() -> Generator[MagicMock, None, None]:
    """Fixture to mock the DucoApiClient external library."""
    mock_client = MagicMock(spec=DucoApiClient)
    # Configure common methods to be awaitable AsyncMocks
    mock_client.test_connection = AsyncMock()
    mock_client.get_device_info = AsyncMock()
    mock_client.get_node_list = AsyncMock()
    mock_client.get_node_info = AsyncMock()
    mock_client.get_node_config = AsyncMock()
    mock_client.get_general_config = AsyncMock()
    mock_client.set_node_config_value = AsyncMock(return_value=True)
    mock_client.set_general_config_value = AsyncMock(return_value=True)
    mock_client.perform_node_action = AsyncMock(return_value=True)
    mock_client.perform_device_action = AsyncMock(return_value=True)

    # Patch the location where the integration imports the client
    # Ensure all import paths used by the integration are patched
    with patch(
        "custom_components.duco_ventilation_sun_control.config_flow.DucoApiClient",
        new=mock_client,
    ), patch(
        "custom_components.duco_ventilation_sun_control.DucoApiClient",
        new=mock_client,
    ), patch(
        "custom_components.duco_ventilation_sun_control.coordinator.DucoApiClient",
        new=mock_client,
    ):
        yield mock_client


@pytest.fixture
def mock_config_entry_v1(hass: HomeAssistant) -> ConfigEntry:
    """Fixture for a V1 config entry."""
    entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title=f"DucoBox (1) - {MOCK_SERIAL_V1}", # Use agreed naming
        data=MOCK_CONFIG_DATA_V1,
        options={},
        source="user",
        entry_id="test-entry-id-v1",
        unique_id=MOCK_SERIAL_V1, # Use serial as unique ID
    )
    # entry.add_to_hass(hass) # Let tests add the entry if needed
    return entry

@pytest.fixture
def mock_config_entry_v2(hass: HomeAssistant) -> ConfigEntry:
    """Fixture for a V2 config entry."""
    entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title=f"DucoBox (?) - {MOCK_SERIAL_V2}", # Use agreed naming, Box ID unknown initially
        data=MOCK_CONFIG_DATA_V2,
        options={},
        source="user",
        entry_id="test-entry-id-v2",
        unique_id=MOCK_SERIAL_V2, # Use serial as unique ID
    )
    # entry.add_to_hass(hass) # Let tests add the entry if needed
    return entry

# Fixture to provide a basic successful V1 API setup
@pytest.fixture
async def setup_integration_v1(
    hass: HomeAssistant, mock_config_entry_v1: ConfigEntry, mock_duco_api_client: MagicMock
) -> ConfigEntry:
    """Set up the Duco integration with a V1 config entry and realistic mocked API."""
    # Add entry to HASS before setup
    mock_config_entry_v1.add_to_hass(hass)

    # Configure API mock for successful setup using REAL V1 data
    # test_connection internally calls get_device_info
    mock_duco_api_client.get_device_info.return_value = MOCK_NORMALIZED_DEVICE_INFO_V1
    mock_duco_api_client.get_node_list.return_value = [1, 137, 138] # From MOCK_RAW_NODELIST_V1

    # Mock get_general_config per area
    async def mock_get_gen_config(area):
        if area == "box": return MOCK_RAW_BOXCONFIG_V1 # Return raw box config
        if area == "ip": return MOCK_RAW_IPCONFIG_V1 # Return raw IP config
        if area == "eco": return MOCK_RAW_ECOCONFIG_V1 # Return raw eco config (empty)
        return {}
    mock_duco_api_client.get_general_config.side_effect = mock_get_gen_config

    # Mock get_node_info per node_id
    async def mock_get_node_info(node_id):
        if node_id == 1: return MOCK_RAW_NODEINFO_V1_BOX
        if node_id == 137: return MOCK_RAW_NODEINFO_V1_CO2
        if node_id == 138: return MOCK_RAW_NODEINFO_V1_RH
        return {} # Default empty for unexpected IDs
    mock_duco_api_client.get_node_info.side_effect = mock_get_node_info

    # Mock get_node_config per node_id
    async def mock_get_node_config(node_id):
        if node_id == 1: return MOCK_RAW_NODECONFIG_V1_BOX
        if node_id == 137: return MOCK_RAW_NODECONFIG_V1_CO2
        if node_id == 138: return MOCK_RAW_NODECONFIG_V1_RH
        return {}
    mock_duco_api_client.get_node_config.side_effect = mock_get_node_config

    # Patch device info creation helpers
    with patch("custom_components.duco_ventilation_sun_control.coordinator.async_create_device_info", return_value={"identifiers": {(DOMAIN, MOCK_SERIAL_V1)}}), \
        patch("custom_components.duco_ventilation_sun_control.coordinator.async_create_node_device_info"):

        # Setup the integration
        await hass.config_entries.async_setup(mock_config_entry_v1.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry_v1

# Fixture for V2 setup (using PLACEHOLDER data for now)
@pytest.fixture
async def setup_integration_v2(
    hass: HomeAssistant, mock_config_entry_v2: ConfigEntry, mock_duco_api_client: MagicMock
) -> ConfigEntry:
    """Set up the Duco integration with a V2 config entry and mocked API."""
    # Add entry to HASS before setup
    mock_config_entry_v2.add_to_hass(hass)

    # Configure API mock for successful setup (using PLACEHOLDER V2 data)
    mock_duco_api_client.get_device_info.return_value = MOCK_NORMALIZED_DEVICE_INFO_V2
    mock_duco_api_client.get_node_list.return_value = [1, 140] # Example V2 nodes
    mock_duco_api_client.get_general_config.return_value = {"Network": {"Ethernet": {"DHCP": {"Val": 1}}}} # Minimal V2 config
    mock_duco_api_client.get_node_info.return_value = {"info": {"devtype": "V2NODE"}} # Minimal V2 node info
    mock_duco_api_client.get_node_config.return_value = {"config": {}} # Minimal V2 node config

    # Patch device info creation helpers
    with patch("custom_components.duco_ventilation_sun_control.coordinator.async_create_device_info", return_value={"identifiers": {(DOMAIN, MOCK_SERIAL_V2)}}), \
        patch("custom_components.duco_ventilation_sun_control.coordinator.async_create_node_device_info"):

        # Setup the integration
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry_v2