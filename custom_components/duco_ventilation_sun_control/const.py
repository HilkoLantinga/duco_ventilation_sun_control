# === custom_components/duco_ventilation_sun_control/const.py ===
"""Constants for the Duco Ventilation System integration.

This file defines constants used throughout the integration. This includes:
- Core integration identifiers (domain, platforms).
- Configuration keys used in config/options flows.
- API version identifiers and default timing values.
- Device type codes and shared action names.
- Raw keys received from the Duco API (V1/V2).
- Normalized internal keys used consistently within the integration code.
- Enums, lists, and mappings derived from constants (e.g., fan states, presets).
- Dataclasses for structured data (Coordinator data, Identified entities).
- Helper functions for data transformation/formatting.
- EntityDescription tuples defining all potential entities.
- Mapping dictionaries linking entity keys to data sources and logic.
- Translation keys for UI text and error messages.
"""
# flake8: noqa E501 # Allow long lines for entity descriptions and maps
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Final, Literal, TypeAlias, Union, cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.button import ButtonEntityDescription
from homeassistant.components.fan import FanEntityFeature
from homeassistant.components.number import NumberEntityDescription, NumberMode
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.text import TextEntityDescription, TextMode
from homeassistant.components.time import TimeEntityDescription
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    ENTITY_CATEGORY_CONFIG,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    Platform,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

# ==============================================================================
# SECTION 1: CORE CONSTANTS & SIMPLE DEFINITIONS
# ==============================================================================

# === Core Integration Constants ===
DOMAIN: Final = "duco_ventilation_sun_control"
"""The domain of this integration."""

PLATFORMS: Final[list[Platform]] = [
    Platform.BINARY_SENSOR, Platform.BUTTON, Platform.FAN, Platform.NUMBER,
    Platform.SELECT, Platform.SENSOR, Platform.SWITCH, Platform.TEXT, Platform.TIME,
]
"""Platforms supported by this integration."""

CONF_HOST: Final = "host"
"""Configuration key for the device hostname or IP address."""
CONF_API_VERSION: Final = "api_version"
"""Configuration key for the detected/forced API version."""
CONF_API_KEY: Final = "api_key"
"""Configuration key for the V2 API key."""

# API Version identifiers
API_V1: Final = "v1"
"""Identifier for Duco API version 1."""
API_V2: Final = "v2"
"""Identifier for Duco API version 2."""

# === Configuration Options ===
CONF_SCAN_INTERVAL: Final = "scan_interval"
"""Options flow key for polling interval."""
CONF_REQUEST_TIMEOUT: Final = "request_timeout"
"""Options flow key for API request timeout."""
CONF_REQUEST_RETRIES: Final = "request_retries"
"""Options flow key for number of API request retries."""
CONF_RETRY_DELAY: Final = "retry_delay"
"""Options flow key for delay between API request retries."""
CONF_COMMAND_QUEUE_DELAY: Final = "command_queue_delay"
"""Options flow key for delay between sending commands."""

# === Timing and Defaults ===
DEFAULT_SCAN_INTERVAL_SECONDS: Final = 60
"""Default polling interval in seconds."""
DEFAULT_REQUEST_TIMEOUT: Final = 10
"""Default API request timeout in seconds."""
DEFAULT_REQUEST_RETRIES: Final = 3
"""Default number of API request retries."""
DEFAULT_RETRY_DELAY: Final = 1.0
"""Default delay between API request retries in seconds."""
DEFAULT_COMMAND_QUEUE_DELAY: Final = 0.5
"""Default delay between consecutive commands in seconds."""
POST_ACTION_REFRESH_DELAY: Final = 1.5
"""Delay before forcing coordinator refresh after an action (seconds)."""

# === Device Types ===
# Strings returned by the API identifying the type of a node
DEVICE_TYPE_BOX: Final = "BOX"
DEVICE_TYPE_UCCO2: Final = "UCCO2"
DEVICE_TYPE_UCRH: Final = "UCRH"
DEVICE_TYPE_VALVE: Final = "VALVE" # Assumed type for zone valves
DEVICE_TYPE_SENSOR_CONTROL: Final = "SENSCNTRL" # Assumed type for control sensors

# === Action Names (Shared between API versions) ===
# Internal names used to trigger actions via coordinator methods
ACTION_CLEAR_NETWORK: Final = "ClearNetwork"
ACTION_LOAD_DEFAULTS_NODE: Final = "LoadDefaultsNode"
ACTION_REBOOT_DEVICE: Final = "RebootDevice"
ACTION_RESET_NODE: Final = "ResetNode"
ACTION_SET_ASSOCIATION: Final = "SetAssociation"
ACTION_SET_CALIBRATION: Final = "SetCalibration"
ACTION_SET_INSTALLER_MODE: Final = "SetInstallerMode"
ACTION_SET_LINK_MODE: Final = "SetLinkMode"
ACTION_SET_OPER_STATE: Final = "SetOperState"
ACTION_SET_OVERRULE: Final = "SetOverrule"
ACTION_SET_PARENT: Final = "SetParent"
ACTION_SET_SHOW: Final = "SetShow"
ACTION_SET_TIME: Final = "SetTime"

# === Special Values ===
V1_CANCEL_OVERRULE_VALUE: Final = 255
"""API value used in V1 to cancel a manual overrule."""
NODE_NO_ERROR_CODE: Final = "W.00.00.00"
"""API value indicating no error state for a node."""

# ==============================================================================
# SECTION 2: API DATA KEYS (As received from the device)
# ==============================================================================
# These constants represent the literal keys found in the JSON responses from
# the Duco V1 and V2 APIs BEFORE normalization. They are primarily used
# internally by the normalization logic (in api.py) and path definitions
# in the mapping dictionaries below.

# Shared Keys / Top Level
KEY_NODE: Final = "node"; KEY_VAL: Final = "Val"; KEY_MIN: Final = "Min"; KEY_MAX: Final = "Max"
KEY_STEP: Final = "Inc"; KEY_VALUE_A: Final = "Val_A"; KEY_VALUE_B: Final = "Val_B"; KEY_VALUE_C: Final = "Val_C"; KEY_VALUE_D: Final = "Val_D"
# V1 Specific
KEY_NODELIST_V1: Final = "nodelist"; KEY_ACTION_SUCCESS_V1: Final = "SUCCESS"; KEY_ACTION_FAILED_V1: Final = "FAILED"
# V2 Specific
KEY_NODES_V2: Final = "Nodes"; KEY_NODE_ID_V2: Final = "Node"; KEY_ACTION_RESULT_V2: Final = "ActionResult"
KEY_V2_HEATRECOVERY: Final = "HeatRecovery"; KEY_V2_TIME_FILTER_REMAIN: Final = "TimeFilterRemain"; KEY_V2_VENTILATION: Final = "Ventilation"; KEY_V2_FLOWLVLTGT: Final = "FlowLvlTgt"; KEY_V2_TIMESTATEREMAIN: Final = "TimeStateRemain"; KEY_V2_TIMESTATEEND: Final = "TimeStateEnd"; KEY_V2_SENSOR: Final = "Sensor"; KEY_V2_IAQCO2: Final = "IaqCo2"; KEY_V2_IAQRH: Final = "IaqRh"
# Device Info Keys (Raw API)
KEY_API_VERSION: Final = "apiversion"; KEY_AUTO_DST: Final = "AutoDaylightSavingTime"; KEY_CALIBRATION: Final = "Calibration"
KEY_CALIB_IS_VALID: Final = "IsValid"; KEY_CALIB_STATE: Final = "CalibState"; KEY_GENERAL: Final = "General"
KEY_INSTALLER_STATE: Final = "InstallerState"; KEY_IP_ADDRESS: Final = "ip"; KEY_MAC: Final = "mac"
KEY_PERFORMANCE: Final = "Performance"; KEY_POWER_AVG: Final = "PowerAvg"; KEY_POWER_MAX: Final = "PowerMax"
KEY_POWER_NOW: Final = "PowerNow"; KEY_PRESSURE_OUT: Final = "PressureOut"; KEY_PRESSURE_TOTAL: Final = "PressureTotal"
KEY_RFHOMEID: Final = "RFHomeID"; KEY_SERIAL: Final = "serial"; KEY_SW_VERSION: Final = "swversion"
KEY_TIME: Final = "Time"; KEY_UPTIME: Final = "uptime"; KEY_WEATHER_PRESENT: Final = "Present"
KEY_WEATHER_STATION: Final = "WeatherStation"
KEY_ENERGYINFO: Final = "EnergyInfo"; KEY_TEMPODA: Final = "TempODA"; KEY_TEMPSUP: Final = "TempSUP"; KEY_TEMPETA: Final = "TempETA"; KEY_TEMPEHA: Final = "TempEHA"; KEY_FILTER_REMAIN: Final = "FilterRemainingTime"
KEY_ENERGYFAN: Final = "EnergyFan"; KEY_SUPPLY_FAN_SPEED: Final = "SupplyFanSpeed"; KEY_EXHAUST_FAN_SPEED: Final = "ExhaustFanSpeed"; KEY_SUPPLY_FAN_PWM: Final = "SupplyFanPwmPercentage"; KEY_EXHAUST_FAN_PWM: Final = "ExhaustFanPwmPercentage"
# Node Info Keys (Raw API)
KEY_ACTL: Final = "actl"; KEY_ASSO: Final = "asso"; KEY_CERR: Final = "cerr"; KEY_CNTDWN: Final = "cntdwn"
KEY_CO2: Final = "co2"; KEY_DEVTYPE: Final = "devtype"; KEY_DUCO_SERIAL: Final = "ducoserial"
KEY_ENDTIME: Final = "endtime"; KEY_ERROR: Final = "error"; KEY_LINK: Final = "link"; KEY_LOCATION: Final = "location"
KEY_LOCATION_V1_CONFIG: Final = "Location"; KEY_MODE: Final = "mode"; KEY_OVRL: Final = "ovrl"; KEY_PRNT: Final = "prnt"
KEY_RH: Final = "rh"; KEY_RSSI: Final = "rssi_n2m"; KEY_RSSI_N2H: Final = "rssi_n2h"; KEY_HOP_VIA: Final = "hop_via"; KEY_SERIAL_NB: Final = "serialnb"; KEY_SHOW: Final = "show"
KEY_SNSR: Final = "snsr"; KEY_STATE: Final = "state"; KEY_SUBTYPE: Final = "subtype"
KEY_SW_VERSION_NODE: Final = "swversion"; KEY_TEMP: Final = "temp"; KEY_TRGT: Final = "trgt"
# Node Config Parameter Keys (Raw API Param Names)
KEY_PARAM_AUTOMAX: Final = "AutoMax"; KEY_PARAM_AUTOMIN: Final = "AutoMin"; KEY_PARAM_CAPACITY: Final = "Capacity"
KEY_PARAM_CO2SETPOINT: Final = "CO2Setpoint"; KEY_PARAM_MANUAL1: Final = "Manual1"; KEY_PARAM_MANUAL2: Final = "Manual2"
KEY_PARAM_MANUAL3: Final = "Manual3"; KEY_PARAM_MANUALTIMEOUT: Final = "ManualTimeout"; KEY_PARAM_RHDELTA: Final = "RHDelta"
KEY_PARAM_RHSETPOINT: Final = "RHSetpoint"; KEY_PARAM_SENSORVISULEVEL: Final = "SensorVisuLevel"; KEY_PARAM_TEMPDEPENDENT: Final = "TempDependent"
# General Config Parameter Keys (Raw API Param Names)
KEY_PARAM_AUTO_DST: Final = KEY_AUTO_DST; KEY_PARAM_BALANCETHRESH: Final = "BalanceThresh"; KEY_PARAM_CALIBONMAN2: Final = "CalibOnMan2"
KEY_PARAM_DHCP: Final = "DHCP"; KEY_PARAM_GATEWAY: Final = "Gateway"; KEY_PARAM_GROUNDBOUND: Final = "GroundBound"
KEY_PARAM_HEADCOUNT: Final = "HeadCount"; KEY_PARAM_HOSTNAME: Final = "HostNameNumber"; KEY_PARAM_MAXHIGHLEVEL: Final = "MaxHighLevel"
KEY_PARAM_MB_ADDRESS: Final = "Address"; KEY_PARAM_MB_OFFSET: Final = "Offset"; KEY_PARAM_MB_PARITY: Final = "Parity"
KEY_PARAM_MB_SPEED: Final = "Speed"; KEY_PARAM_MB_STOPBIT: Final = "Stopbit"; KEY_PARAM_MQTT_BROKERIP: Final = "MqttBroker"
KEY_PARAM_NB_ACTIVE: Final = "Active"; KEY_PARAM_NB_STARTMONTH: Final = "StartMonth"; KEY_PARAM_NB_STARTTEMP: Final = "StartTemp"
KEY_PARAM_NB_STARTTIME: Final = "StartTime"; KEY_PARAM_NB_STOPMONTH: Final = "StopMonth"; KEY_PARAM_NB_STOPTIME: Final = "StopTime"
KEY_PARAM_NETMASK: Final = "Netmask"; KEY_PARAM_PWMINVERTED: Final = "PwmInverted"; KEY_PARAM_STATICIP: Final = "StaticIp"
KEY_PARAM_TEMPCTRLHIGH: Final = "TempCtrlHigh"; KEY_PARAM_TEMPCTRLLOW: Final = "TempCtrlLow"; KEY_PARAM_TIMEZONE: Final = "TimeZone"
KEY_PARAM_VC_ACTIVE_FRI: Final = "ActiveFriday"; KEY_PARAM_VC_ACTIVE_MON: Final = "ActiveMonday"; KEY_PARAM_VC_ACTIVE_SAT: Final = "ActiveSaturday"
KEY_PARAM_VC_ACTIVE_SUN: Final = "ActiveSunday"; KEY_PARAM_VC_ACTIVE_THU: Final = "ActiveThursday"; KEY_PARAM_VC_ACTIVE_TUE: Final = "ActiveTuesday"
KEY_PARAM_VC_ACTIVE_WED: Final = "ActiveWednesday"; KEY_PARAM_VC_MAXWIND: Final = "MaxWindSpeed"; KEY_PARAM_VC_MODE: Final = "Mode"
KEY_PARAM_VC_STARTTIME: Final = "StartTime"; KEY_PARAM_VC_STOPTIME: Final = "StopTime"; KEY_PARAM_VENTCTRL_TEMPDEP: Final = "TempDependent"
# V2 API Module Names
V2_MODULE_ETHERNET: Final = "Ethernet"; V2_MODULE_FAN: Final = "Fan"; V2_MODULE_IDENTIFICATION: Final = "Identification"
V2_MODULE_MODBUS: Final = "Modbus"; V2_MODULE_MQTT: Final = "MQTT"; V2_MODULE_NETWORK: Final = "Network"
V2_MODULE_NIGHTBOOST: Final = "NightBoost"; V2_MODULE_NODECONFIG_LOCATION: Final = V2_MODULE_IDENTIFICATION
V2_MODULE_NODECONFIG_NODE: Final = "Node"; V2_MODULE_NODECONFIG_RH: Final = "SensorRH"
V2_MODULE_NODECONFIG_SENSOR_CO2: Final = "SensorCO2"; V2_MODULE_NODECONFIG_SENSOR_RH: Final = V2_MODULE_NODECONFIG_RH
V2_MODULE_NODECONFIG_TEMP: Final = "SensorTEMP"; V2_MODULE_NODECONFIG_VENT_AUTO: Final = "VentilationAUTO"
V2_MODULE_NODECONFIG_VENT_MANUAL: Final = "VentilationMANUAL"; V2_MODULE_TIMING: Final = "Timing"
V2_MODULE_VENTCOOL: Final = "VentilationCooling"; V2_MODULE_VENTCTRL: Final = "VentilationControl"
# Map V2 Module Name -> V1 Area
V2_MODULE_MAP_TO_V1_AREA: Final[dict[str, str]] = { V2_MODULE_FAN: "box", V2_MODULE_MODBUS: "box", V2_MODULE_MQTT: "ip", V2_MODULE_NETWORK: "ip", V2_MODULE_NIGHTBOOST: "box", V2_MODULE_TIMING: "box", V2_MODULE_VENTCOOL: "box", V2_MODULE_VENTCTRL: "box"}

# ==============================================================================
# SECTION 3: NORMALIZED DATA KEYS (Used internally within the integration)
# ==============================================================================
# These keys represent the standardized way the integration accesses data
# after it has been normalized from either V1 or V2 API responses.

# Device Info Normalized Keys
DEVICE_INFO_KEY_API_VERSION: Final = "api_version"; DEVICE_INFO_KEY_CALIB_STATE: Final = "calibration_state"; DEVICE_INFO_KEY_CALIB_VALID: Final = "calibration_valid"; DEVICE_INFO_KEY_DEVICE_TIME: Final = "device_time"; DEVICE_INFO_KEY_INSTALLER_STATE: Final = "installer_state"; DEVICE_INFO_KEY_IP: Final = "ip_address"; DEVICE_INFO_KEY_MAC: Final = "mac"; DEVICE_INFO_KEY_MODEL: Final = "model"; DEVICE_INFO_KEY_POWER_AVG: Final = "power_avg"; DEVICE_INFO_KEY_POWER_MAX: Final = "power_max"; DEVICE_INFO_KEY_POWER_NOW: Final = "power_now"; DEVICE_INFO_KEY_PRESSURE_OUT: Final = "pressure_out"; DEVICE_INFO_KEY_PRESSURE_TOTAL: Final = "pressure_total"; DEVICE_INFO_KEY_RF_HOME_ID: Final = "rf_home_id"; DEVICE_INFO_KEY_SERIAL: Final = "serial"; DEVICE_INFO_KEY_SW_VERSION: Final = "sw_version"; DEVICE_INFO_KEY_UPTIME: Final = "uptime"; DEVICE_INFO_KEY_WEATHER_PRESENT: Final = "weather_present"; DEVICE_INFO_KEY_FILTER_REMAINING_TIME: Final = "filter_remaining_time"; DEVICE_INFO_KEY_TEMP_ODA: Final = "temp_oda"; DEVICE_INFO_KEY_TEMP_SUP: Final = "temp_sup"; DEVICE_INFO_KEY_TEMP_ETA: Final = "temp_eta"; DEVICE_INFO_KEY_TEMP_EHA: Final = "temp_eha"; DEVICE_INFO_KEY_SUPPLY_FAN_SPEED: Final = "supply_fan_speed"; DEVICE_INFO_KEY_EXHAUST_FAN_SPEED: Final = "exhaust_fan_speed"; DEVICE_INFO_KEY_SUPPLY_FAN_PWM: Final = "supply_fan_pwm"; DEVICE_INFO_KEY_EXHAUST_FAN_PWM: Final = "exhaust_fan_pwm"
# Node Info Normalized Keys
NODE_INFO_KEY_ACTUAL_LEVEL: Final = "actual_level"; NODE_INFO_KEY_ASSO_ID: Final = "asso_id"; NODE_INFO_KEY_CO2: Final = "co2"; NODE_INFO_KEY_COMM_ERROR_CODE: Final = "comm_error_code"; NODE_INFO_KEY_COUNTDOWN: Final = "countdown"; NODE_INFO_KEY_DEVICE_TYPE: Final = "device_type"; NODE_INFO_KEY_DUCO_SERIAL: Final = "duco_serial"; NODE_INFO_KEY_ENDTIME: Final = "end_time"; NODE_INFO_KEY_ERROR_CODE: Final = "error_code"; NODE_INFO_KEY_ERROR_STATUS: Final = "error_status"; NODE_INFO_KEY_ID: Final = "node_id"; NODE_INFO_KEY_LINK: Final = "link_status"; NODE_INFO_KEY_LOCATION: Final = "location"; NODE_INFO_KEY_MODE: Final = "mode"; NODE_INFO_KEY_OVERRULE_PCT: Final = "overrule_percentage"; NODE_INFO_KEY_PARENT_ID: Final = "parent_id"; NODE_INFO_KEY_RH: Final = "humidity"; NODE_INFO_KEY_RSSI: Final = "rssi"; NODE_INFO_KEY_SENSOR_DEMAND: Final = "sensor_demand"; NODE_INFO_KEY_SERIAL: Final = "serial"; NODE_INFO_KEY_SHOW: Final = "show_status"; NODE_INFO_KEY_STATE: Final = "state"; NODE_INFO_KEY_SUB_TYPE: Final = "sub_type"; NODE_INFO_KEY_SW_VERSION: Final = "sw_version"; NODE_INFO_KEY_TARGET_LEVEL: Final = "target_level"; NODE_INFO_KEY_TEMP: Final = "temperature"; NODE_INFO_KEY_HOP_VIA: Final = "hop_via"; NODE_INFO_KEY_RSSI_N2H: Final = "rssi_n2h"; NODE_INFO_KEY_IAQ_CO2: Final = "iaq_co2"; NODE_INFO_KEY_IAQ_RH: Final = "iaq_rh"
# Node Config Normalized Keys
NODE_CONFIG_KEY_PARAM_NAME: Final = "param_name"; NODE_CONFIG_KEY_VALUE: Final = "value"; NODE_CONFIG_KEY_MIN: Final = "min"; NODE_CONFIG_KEY_MAX: Final = "max"; NODE_CONFIG_KEY_STEP: Final = "step"; NODE_CONFIG_KEY_UNIT: Final = "unit"

# ==============================================================================
# SECTION 4: ENUMS, LISTS & MAPPINGS (Derived from constants)
# ==============================================================================

# Node Operational States
class DucoNodeState(str, Enum): AUTO = KEY_STATE_AUTO = "AUTO"; AWAY = KEY_STATE_AWAY = "EMPT"; MANUAL_LOW = KEY_STATE_MANUAL_LOW = "MAN1"; MANUAL_MEDIUM = KEY_STATE_MANUAL_MEDIUM = "MAN2"; MANUAL_HIGH = KEY_STATE_MANUAL_HIGH = "MAN3"; TIMER_1 = KEY_STATE_TIMER_1 = "CNT1"; TIMER_2 = KEY_STATE_TIMER_2 = "CNT2"; TIMER_3 = KEY_STATE_TIMER_3 = "CNT3"; MAN1x2 = KEY_STATE_MAN1x2 = "MAN1x2"; MAN1x3 = KEY_STATE_MAN1x3 = "MAN1x3"; MAN2x2 = KEY_STATE_MAN2x2 = "MAN2x2"; MAN2x3 = KEY_STATE_MAN2x3 = "MAN2x3"; MAN3x2 = KEY_STATE_MAN3x2 = "MAN3x2"; MAN3x3 = KEY_STATE_MAN3x3 = "MAN3x3"
ALL_NODE_STATES: Final[list[str]] = sorted([state.value for state in DucoNodeState])
# Calibration Commands
class DucoCalibCommand(str, Enum): START = KEY_CMD_STARTCALIB = "StartCalib"; STOP = KEY_CMD_STOPCALIB = "StopCalib"; CONFIG_MAX = KEY_CMD_CONFIGMAX = "ConfigMax"; VERIFY_LOW = KEY_CMD_VERIFYLOW = "VerifyLow"; VERIFY_HIGH = KEY_CMD_VERIFYHIGH = "VerifyHigh"
ALL_CALIBRATION_COMMANDS: Final[list[str]] = sorted([cmd.value for cmd in DucoCalibCommand])
# Fan Preset Modes - Updated
PRESET_KEY_AUTO: Final = "auto"; PRESET_KEY_AWAY: Final = "away"; PRESET_KEY_LOW_TEMPORARY: Final = "low_temporary"; PRESET_KEY_LOW_PERMANENT: Final = "low_permanent"; PRESET_KEY_MEDIUM_TEMPORARY: Final = "medium_temporary"; PRESET_KEY_MEDIUM_PERMANENT: Final = "medium_permanent"; PRESET_KEY_HIGH_TEMPORARY: Final = "high_temporary"; PRESET_KEY_HIGH_PERMANENT: Final = "high_permanent"; PRESET_KEY_MANUAL_OVERRIDE: Final = "manual_override"
HA_FAN_PRESET_MODE_KEYS: Final[list[str]] = sorted([PRESET_KEY_AUTO, PRESET_KEY_AWAY, PRESET_KEY_LOW_TEMPORARY, PRESET_KEY_LOW_PERMANENT, PRESET_KEY_MEDIUM_TEMPORARY, PRESET_KEY_MEDIUM_PERMANENT, PRESET_KEY_HIGH_TEMPORARY, PRESET_KEY_HIGH_PERMANENT, PRESET_KEY_MANUAL_OVERRIDE])
# Mapping Duco State -> HA Preset - Updated
DUCO_STATE_TO_PRESET_KEY: Final[dict[str, str]] = { DucoNodeState.AUTO: PRESET_KEY_AUTO, DucoNodeState.AWAY: PRESET_KEY_AWAY, DucoNodeState.MANUAL_LOW: PRESET_KEY_LOW_TEMPORARY, DucoNodeState.MAN1x2: PRESET_KEY_LOW_TEMPORARY, DucoNodeState.MAN1x3: PRESET_KEY_LOW_TEMPORARY, DucoNodeState.TIMER_1: PRESET_KEY_LOW_PERMANENT, DucoNodeState.MANUAL_MEDIUM: PRESET_KEY_MEDIUM_TEMPORARY, DucoNodeState.MAN2x2: PRESET_KEY_MEDIUM_TEMPORARY, DucoNodeState.MAN2x3: PRESET_KEY_MEDIUM_TEMPORARY, DucoNodeState.TIMER_2: PRESET_KEY_MEDIUM_PERMANENT, DucoNodeState.MANUAL_HIGH: PRESET_KEY_HIGH_TEMPORARY, DucoNodeState.MAN3x2: PRESET_KEY_HIGH_TEMPORARY, DucoNodeState.MAN3x3: PRESET_KEY_HIGH_TEMPORARY, DucoNodeState.TIMER_3: PRESET_KEY_HIGH_PERMANENT }
# Mapping HA Preset -> Duco State - Updated
PRESET_KEY_TO_DUCO_STATE: Final[dict[str, str]] = { PRESET_KEY_AUTO: DucoNodeState.AUTO, PRESET_KEY_AWAY: DucoNodeState.AWAY, PRESET_KEY_LOW_TEMPORARY: DucoNodeState.MANUAL_LOW, PRESET_KEY_LOW_PERMANENT: DucoNodeState.TIMER_1, PRESET_KEY_MEDIUM_TEMPORARY: DucoNodeState.MANUAL_MEDIUM, PRESET_KEY_MEDIUM_PERMANENT: DucoNodeState.TIMER_2, PRESET_KEY_HIGH_TEMPORARY: DucoNodeState.MANUAL_HIGH, PRESET_KEY_HIGH_PERMANENT: DucoNodeState.TIMER_3 }
# Month mapping
MONTH_MAP: Final[dict[int, str]] = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
MONTH_MAP_INV: Final[dict[str, int]] = {v: k for k, v in MONTH_MAP.items()}; MONTH_OPTIONS_NAMES: Final[list[str]] = list(MONTH_MAP.values())
# VentCool mode mapping
VENTCOOL_MODE_MAP: Final[dict[int, str]] = {0: "Not Activated", 1: "Time Controlled", 2: "Automatic"}
VENTCOOL_MODE_MAP_INV: Final[dict[str, int]] = {v: k for k, v in VENTCOOL_MODE_MAP.items()}; VENTCOOL_OPTIONS_NAMES: Final[list[str]] = list(VENTCOOL_MODE_MAP.values())

# ==============================================================================
# SECTION 5: DATA TYPE DEFINITIONS
# ==============================================================================
AnyEntityDescription: TypeAlias = Union[BinarySensorEntityDescription, ButtonEntityDescription, NumberEntityDescription, SelectEntityDescription, SensorEntityDescription, SwitchEntityDescription, TextEntityDescription, TimeEntityDescription, EntityDescription]
SensorMapInfoType: TypeAlias = tuple[str, list[str | int], str | None, Callable[[Any], Any] | None]
BinarySensorMapInfoType: TypeAlias = tuple[str, list[str | int], Any, bool]
ButtonActionMapInfoType: TypeAlias = tuple[str, Any | None]
NumberMapInfoType: TypeAlias = tuple[str, list[str | int], str | None, Callable[[Any], Any] | None, Callable[[Any], Any] | None]
SelectMapInfoType: TypeAlias = tuple[str, list[str | int], str | None, Callable[[Any], Any] | None, Callable[[Any], Any] | None]
SwitchMapInfoType: TypeAlias = tuple[str, list[str | int], str | None, Any, Any, bool]
TextMapInfoType: TypeAlias = tuple[str, list[str | int], str | None, Callable[[Any, str | None], Any] | None]
TimeMapInfoType: TypeAlias = tuple[str, list[str | int], str | None, Callable[[Any], Any] | None, Callable[[Any], Any] | None]
AnyMapInfoType: TypeAlias = Union[SensorMapInfoType, BinarySensorMapInfoType, ButtonActionMapInfoType, NumberMapInfoType, SelectMapInfoType, SwitchMapInfoType, TextMapInfoType, TimeMapInfoType]
@dataclass(frozen=True)
class IdentifiedEntity: platform: Platform | str; node_id: int | None; description_key: str; entity_description: AnyEntityDescription; is_box_node_entity: bool = False; map_info: AnyMapInfoType | None = field(default=None, repr=False)
@dataclass()
class DucoCoordinatorData: device_info: dict[str, Any] = field(default_factory=dict); general_config: dict[str, dict[str, Any]] = field(default_factory=dict); nodes: dict[str, dict[str, Any]] = field(default_factory=dict); entities: list[IdentifiedEntity] = field(default_factory=list)

# ==============================================================================
# SECTION 6: HELPER FUNCTIONS / VALUE FORMATTERS
# ==============================================================================
_LOGGER = logging.getLogger(__name__)
def _map_overrule_value(value: Any) -> StateType | None:
    """Convert raw overrule value (0-100 or 255 for off) to percentage (0-100)."""
    if value == V1_CANCEL_OVERRULE_VALUE or value is None: return 0.0
    if isinstance(value, (int, float)):
        try: pct = float(value); return max(0.0, min(100.0, round(pct))) if 1 <= pct <= 100 else 0.0
        except (ValueError, TypeError): pass
    _LOGGER.debug("Unexpected overrule value type: %s (%s)", value, type(value)); return None
def _calculate_uptime_dt(value: Any) -> datetime | None:
    """Calculate startup datetime from uptime in seconds."""
    if isinstance(value, (int, float)) and value >= 0:
        try: return dt_util.utcnow() - timedelta(seconds=float(value))
        except (OverflowError, TypeError, ValueError): _LOGGER.debug("Uptime calculation error for value: '%s'", value)
    return None
def _calculate_utc_datetime(value: Any) -> datetime | None:
    """Convert a POSIX timestamp (seconds since epoch) to a timezone-aware UTC datetime."""
    if isinstance(value, (int, float)) and value > 0:
        try: return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, OverflowError, ValueError, TypeError) as e: _LOGGER.warning("Timestamp conversion error for value '%s': %s", value, e)
    return None
def _map_to_string_upper(value: Any) -> str | None:
    """Convert value to uppercase string, or return None."""
    return str(value).upper() if value is not None else None
def reconstruct_ip_from_dict(data: dict[str, Any] | None, base_key: str | None) -> str | None:
    """Reconstruct an IP address from V1 API parts like {'StaticIpA': {'Val': 192}, ...}."""
    if not isinstance(data, dict) or not base_key: return None
    parts: list[str] = []; suffixes = ["A", "B", "C", "D"]
    for part_suffix in suffixes:
        param_name = f"{base_key}{part_suffix}"; part_data = data.get(param_name)
        if not isinstance(part_data, dict): _LOGGER.debug("Missing IP part dict for key '%s'", param_name); return None
        part_val = part_data.get(KEY_VAL)
        if part_val is None: _LOGGER.debug("Missing IP part value for key '%s'", param_name); return None
        try: int_part = int(part_val); assert 0 <= int_part <= 255; parts.append(str(int_part))
        except (ValueError, TypeError, AssertionError): _LOGGER.warning("Invalid IP part value type/range for key '%s': %s", param_name, part_val); return None
    return ".".join(parts) if len(parts) == 4 else None
def _map_temp_times_10_get(value: Any) -> float | None:
    """Convert temperature value stored as DegC * 10 to float DegC."""
    if isinstance(value, (int, float)):
        try: return float(value) / 10.0
        except (ValueError, TypeError): pass
    _LOGGER.debug("Could not map temp*10 GET value: %s", value); return None
def _map_temp_times_10_set(value: Any) -> int | None:
    """Convert float DegC temperature to value stored as DegC * 10 (integer)."""
    if isinstance(value, (int, float)):
        try: return int(round(float(value) * 10))
        except (ValueError, TypeError): pass
    _LOGGER.debug("Could not map temp*10 SET value: %s", value); return None
def _map_minutes_to_time(value: Any) -> time | None:
    """Convert total minutes from midnight (0-1439) to a Python time object."""
    if isinstance(value, (int, float)) and 0 <= value <= 1439:
        try: minutes_total = int(value); hours, mins = divmod(minutes_total, 60); return time(hour=hours, minute=mins)
        except (ValueError, TypeError): pass
    _LOGGER.debug("Could not map minutes to time: %s", value); return None
def _map_time_to_minutes(value: Any) -> int | None:
    """Convert a Python time object to total minutes from midnight."""
    if isinstance(value, time): return value.hour * 60 + value.minute
    _LOGGER.debug("Could not map time to minutes: %s (%s)", value, type(value)); return None

# ==============================================================================
# SECTION 7: ENTITY DESCRIPTION TUPLES (Using Hierarchical Keys)
# ==============================================================================
# Defines all potential entities using the hierarchical key naming scheme.

# SENSOR
SENSOR_DESC_BOX: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="device.info.api_version", translation_key="box_api_version", icon="mdi:api", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="device.info.power.avg", translation_key="box_average_power", device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=UnitOfPower.WATT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=True),
    SensorEntityDescription(key="device.info.calibration.state", translation_key="box_calibration_state", icon="mdi:tune-variant", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="device.info.power.now", translation_key="box_current_power", device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=UnitOfPower.WATT, entity_registry_enabled_default=True),
    SensorEntityDescription(key="device.info.installer_state", translation_key="box_installer_state", icon="mdi:account-wrench-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="device.info.ip_address", translation_key="box_ip_address", icon="mdi:ip-network-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="device.info.mac", translation_key="box_mac_address", icon="mdi:network-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="device.info.serial", translation_key="box_serial", icon="mdi:pound", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="device.info.sw_version", translation_key="box_sw_version", icon="mdi:information-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="device.info.device_time", translation_key="box_time", device_class=SensorDeviceClass.TIMESTAMP, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),
    SensorEntityDescription(key="device.info.pressure.total", translation_key="box_total_pressure", device_class=SensorDeviceClass.PRESSURE, state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=UnitOfPressure.PA, icon="mdi:gauge", entity_registry_enabled_default=True),
    SensorEntityDescription(key="device.info.uptime", translation_key="box_uptime", device_class=SensorDeviceClass.TIMESTAMP, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),
    # V1 WTW / V2 Sensors
    SensorEntityDescription(key="device.info.filter.remaining_time", translation_key="box_filter_remaining_time", icon="mdi:filter-variant", native_unit_of_measurement=UnitOfTime.DAYS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True),
    SensorEntityDescription(key="device.info.temp.oda", translation_key="box_temp_oda", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True),
    SensorEntityDescription(key="device.info.temp.sup", translation_key="box_temp_sup", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True),
    SensorEntityDescription(key="device.info.temp.eta", translation_key="box_temp_eta", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True),
    SensorEntityDescription(key="device.info.temp.eha", translation_key="box_temp_eha", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True),
    SensorEntityDescription(key="device.info.fan.supply_speed", translation_key="box_supply_fan_speed", icon="mdi:fan-plus", native_unit_of_measurement=REVOLUTIONS_PER_MINUTE, state_class=SensorStateClass.MEASUREMENT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),
    SensorEntityDescription(key="device.info.fan.exhaust_speed", translation_key="box_exhaust_fan_speed", icon="mdi:fan-minus", native_unit_of_measurement=REVOLUTIONS_PER_MINUTE, state_class=SensorStateClass.MEASUREMENT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),
    SensorEntityDescription(key="device.info.fan.supply_pwm", translation_key="box_supply_fan_pwm", icon="mdi:fan-plus", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),
    SensorEntityDescription(key="device.info.fan.exhaust_pwm", translation_key="box_exhaust_fan_pwm", icon="mdi:fan-minus", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),
)
SENSOR_DESC_NODE: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="node.info.actual_level", translation_key="node_actual_speed", icon="mdi:speedometer", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True),
    SensorEntityDescription(key="node.info.co2", translation_key="node_co2", device_class=SensorDeviceClass.CO2, state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION),
    SensorEntityDescription(key="node.info.comm_error_code", translation_key="node_comm_error", icon="mdi:network-off-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="node.info.countdown", translation_key="node_countdown", icon="mdi:timer-outline", native_unit_of_measurement=UnitOfTime.SECONDS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True), # Countdown sensor
    SensorEntityDescription(key="node.info.device_type", translation_key="node_device_type", icon="mdi:chip", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="node.info.end_time", translation_key="node_end_time", device_class=SensorDeviceClass.TIMESTAMP, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),
    SensorEntityDescription(key="node.info.error_code", translation_key="node_error", icon="mdi:alert-circle-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="node.info.humidity", translation_key="node_humidity", device_class=SensorDeviceClass.HUMIDITY, state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=PERCENTAGE),
    SensorEntityDescription(key="node.info.mode", translation_key="node_mode", icon="mdi:cog-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="node.info.rssi", translation_key="node_rssi", device_class=SensorDeviceClass.SIGNAL_STRENGTH, state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),
    SensorEntityDescription(key="node.info.sensor_demand", translation_key="node_sensor_demand", icon="mdi:gauge-low", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True),
    SensorEntityDescription(key="node.info.serial", translation_key="node_serial", icon="mdi:pound", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="node.info.state", translation_key="node_state", icon="mdi:state-machine", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="node.info.sw_version", translation_key="node_sw_version", icon="mdi:information-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),
    SensorEntityDescription(key="node.info.target_level", translation_key="node_target_speed", icon="mdi:bullseye-arrow", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True),
    SensorEntityDescription(key="node.info.temperature", translation_key="node_temperature", device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=UnitOfTemperature.CELSIUS),
    SensorEntityDescription(key="node.info.hop_via", translation_key="node_hop_via", icon="mdi:network-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),
    SensorEntityDescription(key="node.info.rssi_n2h", translation_key="node_rssi_n2h", device_class=SensorDeviceClass.SIGNAL_STRENGTH, state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),
    SensorEntityDescription(key="node.info.iaq_co2", translation_key="node_iaq_co2", icon="mdi:quality-high", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True),
    SensorEntityDescription(key="node.info.iaq_rh", translation_key="node_iaq_rh", icon="mdi:quality-high", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=True),
)

# BINARY SENSOR
BIN_SENSOR_DESC_BOX: tuple[BinarySensorEntityDescription, ...] = ( BinarySensorEntityDescription(key="device.info.calibration.running", translation_key="calibration_running", device_class=BinarySensorDeviceClass.RUNNING, entity_category=ENTITY_CATEGORY_DIAGNOSTIC), BinarySensorEntityDescription(key="device.info.installer_mode.active", translation_key="installer_mode", device_class=BinarySensorDeviceClass.RUNNING, entity_category=ENTITY_CATEGORY_DIAGNOSTIC), BinarySensorEntityDescription(key="device.info.weather.present", translation_key="weather_station_present", device_class=BinarySensorDeviceClass.CONNECTIVITY, entity_category=ENTITY_CATEGORY_DIAGNOSTIC), BinarySensorEntityDescription(key="device.info.calibration.valid", translation_key="calibration_valid", icon="mdi:check-decagram-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC),)
BIN_SENSOR_DESC_NODE: tuple[BinarySensorEntityDescription, ...] = ( BinarySensorEntityDescription(key="node.info.error.status", translation_key="error", device_class=BinarySensorDeviceClass.PROBLEM, entity_category=ENTITY_CATEGORY_DIAGNOSTIC), BinarySensorEntityDescription(key="node.info.link.status", translation_key="link_status", device_class=BinarySensorDeviceClass.CONNECTIVITY, entity_category=ENTITY_CATEGORY_DIAGNOSTIC), BinarySensorEntityDescription(key="node.info.show.status", translation_key="show_status", icon="mdi:eye", entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),)

# BUTTON
BUTTON_DESC_BOX: tuple[ButtonEntityDescription, ...] = ( ButtonEntityDescription(key=ACTION_CLEAR_NETWORK, translation_key="box_clear_network", icon="mdi:network-off-outline", entity_category=ENTITY_CATEGORY_CONFIG), ButtonEntityDescription(key=ACTION_REBOOT_DEVICE, translation_key="box_reboot", icon="mdi:restart", entity_category=ENTITY_CATEGORY_CONFIG), ButtonEntityDescription(key=ACTION_SET_TIME, translation_key="box_sync_time", icon="mdi:clock-sync-outline", entity_category=ENTITY_CATEGORY_CONFIG), ButtonEntityDescription(key="action.calibration.start", translation_key="start_calibration", icon="mdi:play-circle-outline", entity_category=ENTITY_CATEGORY_CONFIG), ButtonEntityDescription(key="action.calibration.stop", translation_key="stop_calibration", icon="mdi:stop-circle-outline", entity_category=ENTITY_CATEGORY_CONFIG),)
BUTTON_DESC_NODE: tuple[ButtonEntityDescription, ...] = ( ButtonEntityDescription(key="action.overrule.clear", translation_key="node_clear_overrule", icon="mdi:cancel", entity_category=ENTITY_CATEGORY_CONFIG), ButtonEntityDescription(key=ACTION_LOAD_DEFAULTS_NODE, translation_key="node_load_defaults", icon="mdi:cog-counterclockwise", entity_category=ENTITY_CATEGORY_CONFIG), ButtonEntityDescription(key=ACTION_RESET_NODE, translation_key="node_reset", icon="mdi:restart-alert", entity_category=ENTITY_CATEGORY_CONFIG),)

# NUMBER
NUMBER_DESC_BOX: tuple[NumberEntityDescription, ...] = ( NumberEntityDescription(key="config.box.fan.headcount", translation_key="box_config_head_count", icon="mdi:account-group", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=1, native_max_value=4, native_step=1, entity_registry_enabled_default=False), NumberEntityDescription(key="config.ip.ethernet.hostname", translation_key="box_config_hostname_number", icon="mdi:pound", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=1, native_max_value=255, native_step=1, entity_registry_enabled_default=False), NumberEntityDescription(key="config.box.fan.maxhighlevel", translation_key="box_config_max_high", icon="mdi:arrow-up-bold-outline", native_unit_of_measurement=PERCENTAGE, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=50, native_max_value=100, native_step=1), NumberEntityDescription(key="config.box.modbus.address", translation_key="box_config_mb_address", icon="mdi:numeric", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=1, native_max_value=254, native_step=1, entity_registry_enabled_default=False), NumberEntityDescription(key="config.box.modbus.offset", translation_key="box_config_mb_offset", icon="mdi:numeric", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=1, native_step=1, entity_registry_enabled_default=False), NumberEntityDescription(key="config.box.modbus.parity", translation_key="box_config_mb_parity", icon="mdi:numeric", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=2, native_step=1, entity_registry_enabled_default=False), NumberEntityDescription(key="config.box.modbus.speed", translation_key="box_config_mb_speed", icon="mdi:speedometer", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=6, native_step=1, entity_registry_enabled_default=False), NumberEntityDescription(key="config.box.modbus.stopbit", translation_key="box_config_mb_stopbit", icon="mdi:numeric", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=1, native_max_value=2, native_step=1, entity_registry_enabled_default=False), NumberEntityDescription(key="config.box.nightboost.starttemp", translation_key="box_config_nb_starttemp", icon="mdi:thermometer-chevron-up", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=15, native_max_value=30, native_step=1), NumberEntityDescription(key="config.box.ventcool.maxwindspeed", translation_key="box_config_vc_maxwind", icon="mdi:weather-windy", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR, native_min_value=0, native_max_value=200, native_step=1), NumberEntityDescription(key="config.box.ventctrl.balancethresh", translation_key="box_config_ventctrl_balancethresh", icon="mdi:scale-balance", native_unit_of_measurement=PERCENTAGE, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=100, native_step=1), NumberEntityDescription(key="config.box.ventctrl.tempctrlhigh", translation_key="box_config_ventctrl_tempctrlhigh", icon="mdi:thermometer-high", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=16.0, native_max_value=35.0, native_step=0.1), NumberEntityDescription(key="config.box.ventctrl.tempctrllow", translation_key="box_config_ventctrl_tempctrllow", icon="mdi:thermometer-low", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=10.0, native_max_value=24.0, native_step=0.1),)
NUMBER_DESC_NODE: tuple[NumberEntityDescription, ...] = ( NumberEntityDescription(key="node.info.asso_id", translation_key="node_association", icon="mdi:link-variant", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=255, native_step=1), NumberEntityDescription(key="config.automax", translation_key="node_config_automax", icon="mdi:arrow-up-bold-outline", native_unit_of_measurement=PERCENTAGE, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=100, native_step=1), NumberEntityDescription(key="config.automin", translation_key="node_config_automin", icon="mdi:arrow-down-bold-outline", native_unit_of_measurement=PERCENTAGE, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=100, native_step=1), NumberEntityDescription(key="config.capacity", translation_key="node_config_capacity", icon="mdi:fan", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=500, native_step=10), NumberEntityDescription(key="config.co2.setpoint", translation_key="node_config_co2_setpoint", device_class=SensorDeviceClass.CO2, native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=400, native_max_value=2000, native_step=50), NumberEntityDescription(key="config.manual.level1", translation_key="node_config_man1", icon="mdi:fan-speed-1", native_unit_of_measurement=PERCENTAGE, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=100, native_step=1), NumberEntityDescription(key="config.manual.level2", translation_key="node_config_man2", icon="mdi:fan-speed-2", native_unit_of_measurement=PERCENTAGE, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=100, native_step=1), NumberEntityDescription(key="config.manual.level3", translation_key="node_config_man3", icon="mdi:fan-speed-3", native_unit_of_measurement=PERCENTAGE, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=100, native_step=1), NumberEntityDescription(key="config.manual.timeout", translation_key="node_config_man_timeout", icon="mdi:timer-cog-outline", native_unit_of_measurement=UnitOfTime.MINUTES, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=180, native_step=1), NumberEntityDescription(key="config.rh.setpoint", translation_key="node_config_rh_setpoint", device_class=SensorDeviceClass.HUMIDITY, native_unit_of_measurement=PERCENTAGE, mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=30, native_max_value=90, native_step=1), NumberEntityDescription(key="config.sensorvisulevel", translation_key="node_config_visu_level", icon="mdi:gauge", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=100, native_step=1), NumberEntityDescription(key="node.info.overrule_percentage", translation_key="node_overrule_level", icon="mdi:tune-vertical", native_unit_of_measurement=PERCENTAGE, mode=NumberMode.SLIDER, native_min_value=0, native_max_value=100, native_step=1), NumberEntityDescription(key="node.info.parent_id", translation_key="node_parent", icon="mdi:network-outline", mode=NumberMode.BOX, entity_category=ENTITY_CATEGORY_CONFIG, native_min_value=0, native_max_value=255, native_step=1),)

# SELECT
SELECT_DESC_BOX: tuple[SelectEntityDescription, ...] = ( SelectEntityDescription(key="action.calibration_command", translation_key="box_calib_command", options=ALL_CALIBRATION_COMMANDS, entity_category=ENTITY_CATEGORY_CONFIG, icon="mdi:tune-variant"), SelectEntityDescription(key="config.box.nightboost.startmonth", translation_key="box_config_nb_startmonth", options=MONTH_OPTIONS_NAMES, entity_category=ENTITY_CATEGORY_CONFIG, icon="mdi:calendar-month"), SelectEntityDescription(key="config.box.nightboost.stopmonth", translation_key="box_config_nb_stopmonth", options=MONTH_OPTIONS_NAMES, entity_category=ENTITY_CATEGORY_CONFIG, icon="mdi:calendar-month"), SelectEntityDescription(key="config.box.ventcool.mode", translation_key="box_config_vc_mode", options=VENTCOOL_OPTIONS_NAMES, entity_category=ENTITY_CATEGORY_CONFIG, icon="mdi:cog"),)
SELECT_DESC_NODE: tuple[SelectEntityDescription, ...] = ( SelectEntityDescription(key="node.info.state", translation_key="node_operation_state", options=ALL_NODE_STATES, entity_category=ENTITY_CATEGORY_CONFIG, icon="mdi:state-machine"), SelectEntityDescription(key="action.zone.set_state", translation_key="node_zone_state", options=ALL_NODE_STATES, entity_category=ENTITY_CATEGORY_CONFIG, icon="mdi:valve"),) # Zone select

# SWITCH
SWITCH_DESC_BOX: tuple[SwitchEntityDescription, ...] = ( SwitchEntityDescription(key="config.box.time.autodst", translation_key="box_config_auto_dst", icon="mdi:clock-check-outline", entity_category=ENTITY_CATEGORY_CONFIG, entity_registry_enabled_default=False), SwitchEntityDescription(key="config.box.fan.calibonman2", translation_key="box_config_calib_man2", icon="mdi:tune-variant", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.ip.ethernet.dhcp", translation_key="box_config_dhcp", icon="mdi:ip-network-outline", entity_category=ENTITY_CATEGORY_CONFIG, entity_registry_enabled_default=False), SwitchEntityDescription(key="config.box.fan.groundbound", translation_key="box_config_ground_bound", icon="mdi:earth-box", entity_category=ENTITY_CATEGORY_CONFIG, entity_registry_enabled_default=False), SwitchEntityDescription(key="config.box.nightboost.active", translation_key="box_config_nb_active", icon="mdi:weather-night", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.box.fan.pwminverted", translation_key="box_config_pwm_inverted", icon="mdi:swap-horizontal-variant", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.box.ventcool.active.friday", translation_key="box_config_vc_fri", icon="mdi:calendar-week", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.box.ventcool.active.monday", translation_key="box_config_vc_mon", icon="mdi:calendar-week", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.box.ventcool.active.saturday", translation_key="box_config_vc_sat", icon="mdi:calendar-week", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.box.ventcool.active.sunday", translation_key="box_config_vc_sun", icon="mdi:calendar-week", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.box.ventcool.active.thursday", translation_key="box_config_vc_thu", icon="mdi:calendar-week", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.box.ventcool.active.tuesday", translation_key="box_config_vc_tue", icon="mdi:calendar-week", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.box.ventcool.active.wednesday", translation_key="box_config_vc_wed", icon="mdi:calendar-week", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.box.ventctrl.tempdependent", translation_key="box_config_ventctrl_tempdep", icon="mdi:thermometer-auto", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="action.installer_mode.toggle", translation_key="box_installer_mode", icon="mdi:account-wrench", entity_category=ENTITY_CATEGORY_CONFIG),)
SWITCH_DESC_NODE: tuple[SwitchEntityDescription, ...] = ( SwitchEntityDescription(key="config.rh.delta", translation_key="node_config_rh_delta", icon="mdi:delta", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="config.temp.dependent", translation_key="node_config_temp_dep", icon="mdi:thermometer-auto", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="action.link_mode.toggle", translation_key="node_link_mode", icon="mdi:link-variant-plus", entity_category=ENTITY_CATEGORY_CONFIG), SwitchEntityDescription(key="action.show.toggle", translation_key="node_show", icon="mdi:eye", entity_category=ENTITY_CATEGORY_CONFIG, entity_registry_enabled_default=False),)

# TEXT
TEXT_DESC_BOX: tuple[TextEntityDescription, ...] = ( TextEntityDescription(key="config.box.time.timezone", translation_key="box_config_timezone", mode=TextMode.TEXT, entity_category=ENTITY_CATEGORY_CONFIG, icon="mdi:map-clock", entity_registry_enabled_default=False), TextEntityDescription(key="device.info.ip_address.gateway", translation_key="box_config_gateway", mode=TextMode.TEXT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False), TextEntityDescription(key="device.info.mqtt.brokerip", translation_key="box_config_mqtt_broker", mode=TextMode.TEXT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False), TextEntityDescription(key="device.info.ip_address.netmask", translation_key="box_config_netmask", mode=TextMode.TEXT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False), TextEntityDescription(key="device.info.ip_address.static", translation_key="box_config_static_ip", mode=TextMode.TEXT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC, entity_registry_enabled_default=False),)
TEXT_DESC_NODE: tuple[TextEntityDescription, ...] = ( TextEntityDescription(key="config.location", translation_key="node_config_location", mode=TextMode.TEXT, entity_category=ENTITY_CATEGORY_CONFIG, icon="mdi:map-marker", native_max=32),)

# TIME
TIME_DESC_BOX: tuple[TimeEntityDescription, ...] = ( TimeEntityDescription(key="config.box.nightboost.starttime", translation_key="box_config_nb_starttime", icon="mdi:clock-start", entity_category=ENTITY_CATEGORY_CONFIG), TimeEntityDescription(key="config.box.nightboost.stoptime", translation_key="box_config_nb_stoptime", icon="mdi:clock-end", entity_category=ENTITY_CATEGORY_CONFIG), TimeEntityDescription(key="config.box.ventcool.starttime", translation_key="box_config_vc_starttime", icon="mdi:clock-start", entity_category=ENTITY_CATEGORY_CONFIG), TimeEntityDescription(key="config.box.ventcool.stoptime", translation_key="box_config_vc_stoptime", icon="mdi:clock-end", entity_category=ENTITY_CATEGORY_CONFIG),)

# ==============================================================================
# SECTION 8: ENTITY MAPPING DICTIONARIES (**REVISED KEYS & PATHS**)
# ==============================================================================
# Maps hierarchical entity keys to internal data paths and processing logic.

# Structure: entity_key: (data_source, path_list, value_key, get_formatter, set_formatter/action_params...)
SENSOR_MAP: dict[str, SensorMapInfoType] = {
    "device.info.api_version": ("device_info", [DEVICE_INFO_KEY_API_VERSION], None, None),
    "device.info.power.avg": ("device_info", [DEVICE_INFO_KEY_POWER_AVG], None, None),
    "device.info.calibration.state": ("device_info", [DEVICE_INFO_KEY_CALIB_STATE], None, _map_to_string_upper),
    "device.info.power.now": ("device_info", [DEVICE_INFO_KEY_POWER_NOW], None, None),
    "device.info.installer_state": ("device_info", [DEVICE_INFO_KEY_INSTALLER_STATE], None, _map_to_string_upper),
    "device.info.ip_address": ("device_info", [DEVICE_INFO_KEY_IP], None, None),
    "device.info.mac": ("device_info", [DEVICE_INFO_KEY_MAC], None, None),
    "device.info.serial": ("device_info", [DEVICE_INFO_KEY_SERIAL], None, None),
    "device.info.sw_version": ("device_info", [DEVICE_INFO_KEY_SW_VERSION], None, None),
    "device.info.device_time": ("device_info", [DEVICE_INFO_KEY_DEVICE_TIME], None, _calculate_utc_datetime),
    "device.info.pressure.total": ("device_info", [DEVICE_INFO_KEY_PRESSURE_TOTAL], None, None),
    "device.info.uptime": ("device_info", [DEVICE_INFO_KEY_UPTIME], None, _calculate_uptime_dt),
    "device.info.filter.remaining_time": ("device_info", [DEVICE_INFO_KEY_FILTER_REMAINING_TIME], None, None),
    "device.info.temp.oda": ("device_info", [DEVICE_INFO_KEY_TEMP_ODA], None, _map_temp_times_10_get), # V1 WTW Temp
    "device.info.temp.sup": ("device_info", [DEVICE_INFO_KEY_TEMP_SUP], None, _map_temp_times_10_get), # V1 WTW Temp
    "device.info.temp.eta": ("device_info", [DEVICE_INFO_KEY_TEMP_ETA], None, _map_temp_times_10_get), # V1 WTW Temp
    "device.info.temp.eha": ("device_info", [DEVICE_INFO_KEY_TEMP_EHA], None, _map_temp_times_10_get), # V1 WTW Temp
    "device.info.fan.supply_speed": ("device_info", [DEVICE_INFO_KEY_SUPPLY_FAN_SPEED], None, None),
    "device.info.fan.exhaust_speed": ("device_info", [DEVICE_INFO_KEY_EXHAUST_FAN_SPEED], None, None),
    "device.info.fan.supply_pwm": ("device_info", [DEVICE_INFO_KEY_SUPPLY_FAN_PWM], None, None),
    "device.info.fan.exhaust_pwm": ("device_info", [DEVICE_INFO_KEY_EXHAUST_FAN_PWM], None, None),

    "node.info.actual_level": ("info", [NODE_INFO_KEY_ACTUAL_LEVEL], None, None),
    "node.info.co2": ("info", [NODE_INFO_KEY_CO2], None, None),
    "node.info.comm_error_code": ("info", [NODE_INFO_KEY_COMM_ERROR_CODE], None, None),
    "node.info.countdown": ("info", [NODE_INFO_KEY_COUNTDOWN], None, None),
    "node.info.device_type": ("info", [NODE_INFO_KEY_DEVICE_TYPE], None, None),
    "node.info.end_time": ("info", [NODE_INFO_KEY_ENDTIME], None, _calculate_utc_datetime),
    "node.info.error_code": ("info", [NODE_INFO_KEY_ERROR_CODE], None, None),
    "node.info.humidity": ("info", [NODE_INFO_KEY_RH], None, None),
    "node.info.mode": ("info", [NODE_INFO_KEY_MODE], None, None),
    "node.info.rssi": ("info", [NODE_INFO_KEY_RSSI], None, None),
    "node.info.sensor_demand": ("info", [NODE_INFO_KEY_SENSOR_DEMAND], None, None),
    "node.info.serial": ("info", [NODE_INFO_KEY_SERIAL], None, None), # Node serial
    "node.info.state": ("info", [NODE_INFO_KEY_STATE], None, None),
    "node.info.sw_version": ("info", [NODE_INFO_KEY_SW_VERSION], None, None), # Node sw version
    "node.info.target_level": ("info", [NODE_INFO_KEY_TARGET_LEVEL], None, None),
    "node.info.temperature": ("info", [NODE_INFO_KEY_TEMP], None, None),
    "node.info.hop_via": ("info", [NODE_INFO_KEY_HOP_VIA], None, None),
    "node.info.rssi_n2h": ("info", [NODE_INFO_KEY_RSSI_N2H], None, None),
    "node.info.iaq_co2": ("info", [NODE_INFO_KEY_IAQ_CO2], None, None),
    "node.info.iaq_rh": ("info", [NODE_INFO_KEY_IAQ_RH], None, None),
}
BINARY_SENSOR_MAP: dict[str, BinarySensorMapInfoType] = { "device.info.calibration.running": ("device_info", [DEVICE_INFO_KEY_CALIB_STATE], "RUNNING", False), "device.info.calibration.valid": ("device_info", [DEVICE_INFO_KEY_CALIB_VALID], True, False), "device.info.installer_mode.active": ("device_info", [DEVICE_INFO_KEY_INSTALLER_STATE], "OPERATIONAL", True), "device.info.weather.present": ("device_info", [DEVICE_INFO_KEY_WEATHER_PRESENT], True, False), "node.info.error.status": ("info", [NODE_INFO_KEY_ERROR_STATUS], True, False), "node.info.link.status": ("info", [NODE_INFO_KEY_LINK], True, False), "node.info.show.status": ("info", [NODE_INFO_KEY_SHOW], True, False),}
BUTTON_ACTION_MAP: dict[str, ButtonActionMapInfoType] = { ACTION_CLEAR_NETWORK: ("async_box_clear_network", None), ACTION_REBOOT_DEVICE: ("async_board_reset", None), ACTION_SET_TIME: ("async_box_set_time", None), "action.calibration.start": ("async_box_set_calibration", DucoCalibCommand.START.value), "action.calibration.stop": ("async_box_set_calibration", DucoCalibCommand.STOP.value), "action.overrule.clear": ("async_node_set_overrule", V1_CANCEL_OVERRULE_VALUE), ACTION_LOAD_DEFAULTS_NODE: ("async_node_load_defaults", None), ACTION_RESET_NODE: ("async_node_reset", None),}
NUMBER_ENTITY_MAP: dict[str, NumberMapInfoType] = { "config.box.fan.headcount": ("general_config", ['box', KEY_MODULE_FAN, KEY_PARAM_HEADCOUNT], NODE_CONFIG_KEY_VALUE, None, None), "config.ip.ethernet.hostname": ("general_config", ['ip', KEY_MODULE_ETHERNET, KEY_PARAM_HOSTNAME], NODE_CONFIG_KEY_VALUE, None, None), "config.box.fan.maxhighlevel": ("general_config", ['box', KEY_MODULE_FAN, KEY_PARAM_MAXHIGHLEVEL], NODE_CONFIG_KEY_VALUE, None, None), "config.box.modbus.address": ("general_config", ['box', KEY_MODULE_MODBUS, KEY_PARAM_MB_ADDRESS], NODE_CONFIG_KEY_VALUE, None, None), "config.box.modbus.offset": ("general_config", ['box', KEY_MODULE_MODBUS, KEY_PARAM_MB_OFFSET], NODE_CONFIG_KEY_VALUE, None, None), "config.box.modbus.parity": ("general_config", ['box', KEY_MODULE_MODBUS, KEY_PARAM_MB_PARITY], NODE_CONFIG_KEY_VALUE, None, None), "config.box.modbus.speed": ("general_config", ['box', KEY_MODULE_MODBUS, KEY_PARAM_MB_SPEED], NODE_CONFIG_KEY_VALUE, None, None), "config.box.modbus.stopbit": ("general_config", ['box', KEY_MODULE_MODBUS, KEY_PARAM_MB_STOPBIT], NODE_CONFIG_KEY_VALUE, None, None), "config.box.nightboost.starttemp": ("general_config", ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STARTTEMP], NODE_CONFIG_KEY_VALUE, None, None), "config.box.ventcool.maxwindspeed": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_MAXWIND], NODE_CONFIG_KEY_VALUE, None, None), "config.box.ventctrl.balancethresh": ("general_config", ['box', KEY_MODULE_VENTCTRL, KEY_PARAM_BALANCETHRESH], NODE_CONFIG_KEY_VALUE, None, None), "config.box.ventctrl.tempctrlhigh": ("general_config", ['box', KEY_MODULE_VENTCTRL, KEY_PARAM_TEMPCTRLHIGH], NODE_CONFIG_KEY_VALUE, _map_temp_times_10_get, _map_temp_times_10_set), "config.box.ventctrl.tempctrllow": ("general_config", ['box', KEY_MODULE_VENTCTRL, KEY_PARAM_TEMPCTRLLOW], NODE_CONFIG_KEY_VALUE, _map_temp_times_10_get, _map_temp_times_10_set), "node.info.asso_id": ("info", [NODE_INFO_KEY_ASSO_ID], None, None, lambda v: int(v)), "config.automax": ("config", [KEY_PARAM_AUTOMAX], NODE_CONFIG_KEY_VALUE, None, None), "config.automin": ("config", [KEY_PARAM_AUTOMIN], NODE_CONFIG_KEY_VALUE, None, None), "config.capacity": ("config", [KEY_PARAM_CAPACITY], NODE_CONFIG_KEY_VALUE, None, None), "config.co2.setpoint": ("config", [KEY_PARAM_CO2SETPOINT], NODE_CONFIG_KEY_VALUE, None, None), "config.manual.level1": ("config", [KEY_PARAM_MANUAL1], NODE_CONFIG_KEY_VALUE, None, None), "config.manual.level2": ("config", [KEY_PARAM_MANUAL2], NODE_CONFIG_KEY_VALUE, None, None), "config.manual.level3": ("config", [KEY_PARAM_MANUAL3], NODE_CONFIG_KEY_VALUE, None, None), "config.manual.timeout": ("config", [KEY_PARAM_MANUALTIMEOUT], NODE_CONFIG_KEY_VALUE, None, None), "config.rh.setpoint": ("config", [KEY_PARAM_RHSETPOINT], NODE_CONFIG_KEY_VALUE, None, None), "config.sensorvisulevel": ("config", [KEY_PARAM_SENSORVISULEVEL], NODE_CONFIG_KEY_VALUE, None, None), "node.info.overrule_percentage": ("info", [NODE_INFO_KEY_OVERRULE_PCT], None, _map_overrule_value, lambda v: V1_CANCEL_OVERRULE_VALUE if int(v) == 0 else max(1, min(100, int(v)))), "node.info.parent_id": ("info", [NODE_INFO_KEY_PARENT_ID], None, None, lambda v: int(v)), }
SELECT_ENTITY_MAP: dict[str, SelectMapInfoType] = { "action.calibration_command": ("device_info", [DEVICE_INFO_KEY_CALIB_STATE], None, None, lambda v: v), "config.box.nightboost.startmonth": ("general_config", ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STARTMONTH], NODE_CONFIG_KEY_VALUE, lambda v: MONTH_MAP.get(int(v)) if v is not None else None, lambda v: MONTH_MAP_INV.get(v)), "config.box.nightboost.stopmonth": ("general_config", ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STOPMONTH], NODE_CONFIG_KEY_VALUE, lambda v: MONTH_MAP.get(int(v)) if v is not None else None, lambda v: MONTH_MAP_INV.get(v)), "config.box.ventcool.mode": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_MODE], NODE_CONFIG_KEY_VALUE, lambda v: VENTCOOL_MODE_MAP.get(int(v)) if v is not None else None, lambda v: VENTCOOL_MODE_MAP_INV.get(v)), "node.info.state": ("info", [NODE_INFO_KEY_STATE], None, None, lambda v: v), "action.zone.set_state": ("info", [NODE_INFO_KEY_STATE], None, None, lambda v: v), # Zone select uses node state for read, action for write
}
SWITCH_ENTITY_MAP: dict[str, SwitchMapInfoType] = { "config.box.time.autodst": ("general_config", ['box', KEY_MODULE_TIME, KEY_PARAM_AUTO_DST], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.fan.calibonman2": ("general_config", ['box', KEY_MODULE_FAN, KEY_PARAM_CALIBONMAN2], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.ip.ethernet.dhcp": ("general_config", ['ip', KEY_MODULE_ETHERNET, KEY_PARAM_DHCP], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.fan.groundbound": ("general_config", ['box', KEY_MODULE_FAN, KEY_PARAM_GROUNDBOUND], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.nightboost.active": ("general_config", ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_ACTIVE], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.fan.pwminverted": ("general_config", ['box', KEY_MODULE_FAN, KEY_PARAM_PWMINVERTED], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.ventcool.active.friday": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_ACTIVE_FRI], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.ventcool.active.monday": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_ACTIVE_MON], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.ventcool.active.saturday": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_ACTIVE_SAT], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.ventcool.active.sunday": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_ACTIVE_SUN], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.ventcool.active.thursday": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_ACTIVE_THU], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.ventcool.active.tuesday": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_ACTIVE_TUE], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.ventcool.active.wednesday": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_ACTIVE_WED], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.box.ventctrl.tempdependent": ("general_config", ['box', KEY_MODULE_VENTCTRL, KEY_PARAM_VENTCTRL_TEMPDEP], NODE_CONFIG_KEY_VALUE, 1, 0, False), "action.installer_mode.toggle": ("device_info", [DEVICE_INFO_KEY_INSTALLER_STATE], None, "INSTALLER", "OPERATIONAL", False), "config.rh.delta": ("config", [KEY_PARAM_RHDELTA], NODE_CONFIG_KEY_VALUE, 1, 0, False), "config.temp.dependent": ("config", [KEY_PARAM_TEMPDEPENDENT], NODE_CONFIG_KEY_VALUE, 1, 0, False), "action.link_mode.toggle": ("info", [NODE_INFO_KEY_LINK], None, 1, 0, False), "action.show.toggle": ("info", [NODE_INFO_KEY_SHOW], None, 1, 0, False),}
TEXT_ENTITY_MAP: dict[str, TextMapInfoType] = { "config.box.time.timezone": ("general_config", ['box', KEY_MODULE_TIME, KEY_PARAM_TIMEZONE], NODE_CONFIG_KEY_VALUE, None), "device.info.ip_address.gateway": ("general_config", ['ip', KEY_MODULE_ETHERNET], KEY_PARAM_GATEWAY, reconstruct_ip_from_dict), "device.info.mqtt.brokerip": ("general_config", ['ip', KEY_MODULE_MQTT, KEY_PARAM_MQTT_BROKERIP], KEY_PARAM_MQTT_BROKERIP, reconstruct_ip_from_dict), "device.info.ip_address.netmask": ("general_config", ['ip', KEY_MODULE_ETHERNET], KEY_PARAM_NETMASK, reconstruct_ip_from_dict), "device.info.ip_address.static": ("general_config", ['ip', KEY_MODULE_ETHERNET], KEY_PARAM_STATICIP, reconstruct_ip_from_dict), "config.location": ("config", [KEY_LOCATION_V1_CONFIG], NODE_CONFIG_KEY_VALUE, None),}
TIME_ENTITY_MAP: dict[str, TimeMapInfoType] = { "config.box.nightboost.starttime": ("general_config", ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STARTTIME], NODE_CONFIG_KEY_VALUE, _map_minutes_to_time, _map_time_to_minutes), "config.box.nightboost.stoptime": ("general_config", ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STOPTIME], NODE_CONFIG_KEY_VALUE, _map_minutes_to_time, _map_time_to_minutes), "config.box.ventcool.starttime": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_STARTTIME], NODE_CONFIG_KEY_VALUE, _map_minutes_to_time, _map_time_to_minutes), "config.box.ventcool.stoptime": ("general_config", ['box', KEY_MODULE_VENTCOOL, KEY_PARAM_VC_STOPTIME], NODE_CONFIG_KEY_VALUE, _map_minutes_to_time, _map_time_to_minutes),}
PLATFORM_MAPS: Final[dict[Platform | str, dict[str, AnyMapInfoType]]] = { Platform.BINARY_SENSOR: BINARY_SENSOR_MAP, Platform.BUTTON: BUTTON_ACTION_MAP, Platform.FAN: {}, Platform.NUMBER: NUMBER_ENTITY_MAP, Platform.SELECT: SELECT_ENTITY_MAP, Platform.SENSOR: SENSOR_MAP, Platform.SWITCH: SWITCH_ENTITY_MAP, Platform.TEXT: TEXT_ENTITY_MAP, Platform.TIME: TIME_ENTITY_MAP }
TRANS_ERROR_UNKNOWN: Final = "unknown"; TRANS_ERROR_CANNOT_CONNECT: Final = "cannot_connect"; TRANS_ERROR_INVALID_AUTH: Final = "invalid_auth"; TRANS_ERROR_UNKNOWN_API_VERSION: Final = "unknown_api_version"; TRANS_ERROR_DISCOVERY_ERROR: Final = "discovery_error"; TRANS_ERROR_DEVICE_NOT_READY: Final = "device_not_ready"; TRANS_ERROR_MISSING_UNIQUE_ID: Final = "missing_unique_id"; TRANS_ABORT_ALREADY_CONFIGURED: Final = "already_configured"; TRANS_ABORT_ALREADY_IN_PROGRESS: Final = "already_in_progress"; TRANS_ABORT_CANNOT_CONNECT: Final = "cannot_connect"; TRANS_ABORT_UNKNOWN_API_VERSION: Final = "unknown_api_version"; TRANS_ABORT_DISCOVERY_ERROR: Final = "discovery_error"; TRANS_ABORT_DEVICE_NOT_READY: Final = "device_not_ready"; TRANS_ABORT_MISSING_UNIQUE_ID: Final = "missing_unique_id"; TRANS_ABORT_CONTEXT_ERROR: Final = "context_error"; TRANS_ERROR_COMMAND_FAILED: Final = "command_failed"; TRANS_ERROR_INVALID_INPUT: Final = "invalid_input"; TRANS_ERROR_NOT_IMPLEMENTED: Final = "not_implemented"