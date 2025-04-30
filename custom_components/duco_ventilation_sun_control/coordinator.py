# === custom_components/duco_ventilation_sun_control/coordinator.py ===
"""DataUpdateCoordinator for the Duco Ventilation System integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

# External library imports (placeholders)
from .api import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    ApiResponseError,
    DucoApiClient,
)

# Local integration imports
from .const import (
    ACTION_CLEAR_NETWORK, ACTION_LOAD_DEFAULTS_NODE, ACTION_REBOOT_DEVICE,
    ACTION_RESET_NODE, ACTION_SET_ASSOCIATION, ACTION_SET_CALIBRATION,
    ACTION_SET_INSTALLER_MODE, ACTION_SET_LINK_MODE, ACTION_SET_OPER_STATE,
    ACTION_SET_OVERRULE, ACTION_SET_PARENT, ACTION_SET_SHOW, ACTION_SET_TIME,
    API_V1, API_V2, BIN_SENSOR_DESC_BOX, BIN_SENSOR_DESC_NODE, BUTTON_DESC_BOX,
    BUTTON_DESC_NODE, DEVICE_INFO_KEY_SERIAL, DEVICE_TYPE_BOX, DEVICE_TYPE_UCCO2,
    DEVICE_TYPE_UCRH, DEVICE_TYPE_VALVE, # Added VALVE type
    DOMAIN, DucoCoordinatorData, IdentifiedEntity, KEY_LOCATION_V1_CONFIG,
    KEY_MODULE_ETHERNET, KEY_MODULE_FAN, KEY_MODULE_IDENTIFICATION,
    KEY_MODULE_MODBUS, KEY_MODULE_MQTT, KEY_MODULE_NETWORK, KEY_MODULE_NIGHTBOOST,
    KEY_MODULE_NODECONFIG_LOCATION, KEY_MODULE_NODECONFIG_NODE, KEY_MODULE_NODECONFIG_RH,
    KEY_MODULE_NODECONFIG_SENSOR_CO2, KEY_MODULE_NODECONFIG_SENSOR_RH,
    KEY_MODULE_NODECONFIG_TEMP, KEY_MODULE_NODECONFIG_VENT_AUTO,
    KEY_MODULE_NODECONFIG_VENT_MANUAL, KEY_MODULE_TIME, KEY_MODULE_VENTCOOL,
    KEY_MODULE_VENTCTRL, NODE_INFO_KEY_CO2, NODE_INFO_KEY_DEVICE_TYPE,
    NODE_INFO_KEY_RH, NODE_INFO_KEY_TEMP, NUMBER_DESC_BOX, NUMBER_DESC_NODE,
    PLATFORM_MAPS, SELECT_DESC_BOX, SELECT_DESC_NODE, SENSOR_DESC_BOX,
    SENSOR_DESC_NODE, SWITCH_DESC_BOX, SWITCH_DESC_NODE, TEXT_DESC_BOX,
    TEXT_DESC_NODE, TIME_DESC_BOX, TRANS_ERROR_COMMAND_FAILED,
    TRANS_ERROR_INVALID_AUTH, TRANS_ERROR_INVALID_INPUT, TRANS_ERROR_NOT_IMPLEMENTED,
    TRANS_ERROR_UNKNOWN, V1_CANCEL_OVERRULE_VALUE, AnyEntityDescription,
    DucoCalibCommand, # Enum for actions
)
from .device import async_create_device_info, async_create_node_device_info
from .util import get_nested_value

if TYPE_CHECKING:
    # Only import for type hints to avoid circular imports
    from homeassistant.helpers.entity import DeviceInfo

_LOGGER = logging.getLogger(__name__)

# Time to wait after a command before forcing a refresh
POST_ACTION_REFRESH_DELAY: Final = 1.5

# List of node.info.* entity keys ALLOWED to be created for the Box Node (Node 1)
# Others are assumed to be node-specific status/config irrelevant to the main box UI.
ALLOWED_NODE_ENTITY_KEYS_ON_BOX: Final[list[str]] = [
    "node.info.state",          # Box Operating State (Select)
    "node.info.mode",           # Box Operating Mode (Sensor)
    "node.info.actual_level",   # Box Actual Speed (Sensor)
    "node.info.target_level",   # Box Target Speed (Sensor)
    "node.info.overrule_percentage", # Box Overrule Level (Number)
    "node.info.countdown",      # Box Timer Countdown (Sensor)
    "node.info.temperature",    # Box Temperature (Sensor, if available)
    "node.info.co2",            # Box CO2 (Sensor, if available)
    "node.info.humidity",       # Box Humidity (Sensor, if available)
    "node.info.sensor_demand",  # Box Sensor Demand (Sensor)
    "node.info.error.status",   # Box Error Status (Binary Sensor)
    "node.info.error_code",     # Box Error Code (Sensor)
    "node.info.comm_error_code",# Box Comm Error (Sensor)
    # Add others if the box node provides meaningful status directly
]


class DucoDataUpdateCoordinator(DataUpdateCoordinator[DucoCoordinatorData]):
    """Manages fetching Duco data and coordinating updates for entities.

    Responsible for polling the device via the external API client, normalizing
    data (using helpers from the API client), identifying available entities based
    on the data, storing the latest state, and providing methods for entities
    to trigger actions on the device.
    """

    config_entry: ConfigEntry
    api: DucoApiClient # API Client instance

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: DucoApiClient,
        scan_interval_seconds: int,
    ) -> None:
        """Initialize the data update coordinator.

        Args:
            hass: The Home Assistant instance.
            config_entry: The configuration entry for this Duco device.
            api_client: An initialized Duco API client instance.
            scan_interval_seconds: The polling interval in seconds.
        """
        self.api = api_client
        self.config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._host = api_client.host
        self._api_version = api_client._api_version # type: ignore[attr-defined] # Access internal for logging

        # Ensure scan interval is reasonable
        interval = timedelta(seconds=max(10, scan_interval_seconds))

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator_{self._entry_id}",
            update_interval=interval,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=POST_ACTION_REFRESH_DELAY, immediate=False
            ),
        )
        # Initialize data structure and state variables
        self.data: DucoCoordinatorData = DucoCoordinatorData() # Explicitly initialize
        self._box_node_id: int | None = None # Determined during update
        self._main_device_info: DeviceInfo | None = None # Created during update

    @property
    def main_device_info(self) -> DeviceInfo | None:
        """Return the DeviceInfo for the main DucoBox device."""
        return self._main_device_info

    async def _async_update_data(self) -> DucoCoordinatorData:
        """Fetch the latest data from the Duco device via the API client."""
        _LOGGER.debug("Coordinator: Starting data update cycle for %s", self._host)
        current_data = DucoCoordinatorData() # Use temporary object for atomicity

        try:
            # 1. Fetch Device Info (Essential)
            _LOGGER.debug("Coordinator: Fetching device info...")
            device_info_raw = await self.api.get_device_info() # Already normalized by API client
            if not device_info_raw: raise UpdateFailed("Failed to get device info")
            current_data.device_info = device_info_raw

            # 2. Fetch Node List (Essential)
            _LOGGER.debug("Coordinator: Fetching node list...")
            node_list = await self.api.get_node_list()
            _LOGGER.info("Coordinator: Active node IDs found: %s", node_list)

            # 3. Fetch Node Data (Info and Config) Concurrently
            _LOGGER.debug("Coordinator: Fetching data for %d nodes...", len(node_list))
            nodes_data: dict[str, dict[str, Any]] = {}
            node_fetch_tasks = [self._fetch_single_node_data(node_id) for node_id in node_list]
            node_results = await asyncio.gather(*node_fetch_tasks, return_exceptions=True)

            for idx, result in enumerate(node_results):
                node_id = node_list[idx]
                node_id_str = str(node_id)
                if isinstance(result, Exception):
                    _LOGGER.warning("Coordinator: Failed to fetch data for node %d: %s", node_id, result)
                    nodes_data[node_id_str] = {"info": {}, "config": {}} # Store empty on failure
                elif isinstance(result, dict):
                    nodes_data[node_id_str] = result

            current_data.nodes = nodes_data
            _LOGGER.debug("Coordinator: Node data fetched for IDs: %s", list(nodes_data.keys()))

            # 4. Identify Box Node ID *after* fetching all node data
            self._box_node_id = self._find_box_node_id(current_data.nodes)

            # 5. Create/Update Main Device Info (after finding box node ID)
            self._main_device_info = async_create_device_info(
                self.config_entry, device_info_raw, self._box_node_id
            )

            # 6. Fetch General Configuration (Best Effort)
            _LOGGER.debug("Coordinator: Fetching general config...")
            general_config_all: dict[str, dict[str, Any]] = {}
            config_areas = ["box", "ip", "eco"]
            config_tasks = [self.api.get_general_config(area) for area in config_areas]
            config_results = await asyncio.gather(*config_tasks, return_exceptions=True)

            for idx, result in enumerate(config_results):
                area = config_areas[idx]
                if isinstance(result, Exception):
                    _LOGGER.warning("Coordinator: Could not fetch config for area '%s': %s", area, result)
                elif isinstance(result, dict) and result: # Check if result is a non-empty dict
                    general_config_all[area] = result
            current_data.general_config = general_config_all

            # 7. Identify Entities based on all fetched data
            _LOGGER.debug("Coordinator: Identifying entities...")
            current_data.entities = self._identify_entities(
                current_data.device_info, current_data.general_config, current_data.nodes
            )
            _LOGGER.info("Coordinator: Identified %d entities.", len(current_data.entities))

            return current_data

        except ApiAuthError as err:
            _LOGGER.error("Coordinator: Authentication error during update: %s", err)
            raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key=TRANS_ERROR_INVALID_AUTH) from err
        except (ApiConnectionError, ApiResponseError, ApiError, Exception) as err:
            _LOGGER.error("Coordinator: Failed to fetch Duco data: %s", err, exc_info=False) # Log exception only in debug
            _LOGGER.debug("Coordinator update error details:", exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _fetch_single_node_data(self, node_id: int) -> dict[str, Any]:
        """Fetch info and config for a single node concurrently, return combined dict."""
        try:
            # Fetch info and config concurrently
            info_data, config_data = await asyncio.gather(
                self.api.get_node_info(node_id),
                self.api.get_node_config(node_id),
                return_exceptions=True # Return exception object on failure
            )
            # Process results, handling potential exceptions during gather
            node_info = info_data if not isinstance(info_data, Exception) else {}
            node_config = config_data if not isinstance(config_data, Exception) else {}
            if isinstance(info_data, Exception): _LOGGER.warning("Coordinator: Failed node %d info fetch: %s", node_id, info_data)
            if isinstance(config_data, Exception): _LOGGER.warning("Coordinator: Failed node %d config fetch: %s", node_id, config_data)
            return {"info": node_info, "config": node_config}
        except Exception as e:
            # Catch unexpected errors during the gather itself
            _LOGGER.error("Coordinator: Unexpected error fetching data for node %d: %s", node_id, e)
            return {"info": {}, "config": {}} # Return empty on failure

    def _find_box_node_id(self, nodes_data: dict[str, dict[str, Any]]) -> int | None:
        """Iterate through node data to find the node ID marked as DEVICE_TYPE_BOX."""
        for node_id_str, node_data in nodes_data.items():
            if node_data.get("info", {}).get(NODE_INFO_KEY_DEVICE_TYPE) == DEVICE_TYPE_BOX:
                try: return int(node_id_str)
                except ValueError: _LOGGER.error("Invalid Box Node ID found: %s", node_id_str)
        if "1" in nodes_data: _LOGGER.warning("Could not detect Box Node ID, assuming Node 1"); return 1
        _LOGGER.error("Could not determine Box Node ID from available nodes."); return None

    def _identify_entities(
        self, device_info: dict[str, Any], general_config: dict[str, Any], nodes: dict[str, dict[str, Any]]
    ) -> list[IdentifiedEntity]:
        """Determine which entities should exist based on available data and descriptions."""
        identified: list[IdentifiedEntity] = []
        # Combine all entity descriptions from const.py
        all_descriptions: dict[Platform | str, tuple[AnyEntityDescription, ...]] = {
            Platform.SENSOR: SENSOR_DESC_BOX + SENSOR_DESC_NODE,
            Platform.BINARY_SENSOR: BIN_SENSOR_DESC_BOX + BIN_SENSOR_DESC_NODE,
            Platform.SWITCH: SWITCH_DESC_BOX + SWITCH_DESC_NODE,
            Platform.SELECT: SELECT_DESC_BOX + SELECT_DESC_NODE,
            Platform.NUMBER: NUMBER_DESC_BOX + NUMBER_DESC_NODE,
            Platform.TEXT: TEXT_DESC_BOX + TEXT_DESC_NODE,
            Platform.BUTTON: BUTTON_DESC_BOX + BUTTON_DESC_NODE,
            Platform.TIME: TIME_DESC_BOX,
            Platform.FAN: (EntityDescription(key="fan", name="Ventilation"),), # Fan placeholder
        }

        # Add Fan entity for the identified Box Node
        if self._box_node_id is not None:
            identified.append(IdentifiedEntity( platform=Platform.FAN, node_id=self._box_node_id, description_key="fan", entity_description=EntityDescription(key="fan"), is_box_node_entity=True, map_info=None ))

        # Iterate through platforms and their descriptions
        for platform, descriptions in all_descriptions.items():
            if platform == Platform.FAN: continue # Handled above

            platform_map = PLATFORM_MAPS.get(platform, {})
            for description in descriptions:
                key = description.key # Hierarchical key, e.g., "device.info.serial"
                map_info = platform_map.get(key)
                if not map_info: _LOGGER.debug("No map info found for %s key %s", platform, key); continue

                # Determine entity type based on key prefix
                is_device_entity = key.startswith("device.info.") or key.startswith("config.box.") or key.startswith("config.ip.") or key.startswith("config.eco.") or key.startswith("action.") and platform != Platform.SELECT # Device-level actions/configs
                is_node_entity = key.startswith("node.info.") or key.startswith("config.") and not is_device_entity or key == "action.zone.set_state" # Node info/config/zone actions

                # Check device-level entities
                if is_device_entity:
                    # Check if data for this entity exists based on its mapping
                    if self._check_entity_data_exists(device_info, general_config, {}, key, map_info):
                        identified.append(IdentifiedEntity( platform=platform, node_id=None, description_key=key, entity_description=description, map_info=map_info ))

                # Check node-level entities across all nodes
                elif is_node_entity:
                    for node_id_str, node_data in nodes.items():
                        try: node_id_int = int(node_id_str)
                        except ValueError: continue

                        # Check if data for this entity exists for this node
                        if self._check_entity_data_exists(device_info, general_config, node_data, key, map_info):
                            # Apply filtering: node type specific sensors, box node exceptions
                            if not self._should_add_node_entity(key, node_data.get("info", {})): continue

                            is_box_node = (node_id_int == self._box_node_id)
                            if self._should_skip_based_on_node_type(key, is_box_node): continue

                            # Special handling for zone select
                            is_zone_select = key == "action.zone.set_state"
                            node_type = node_data.get("info", {}).get(NODE_INFO_KEY_DEVICE_TYPE)
                            # Only add zone select for potential zone nodes (e.g., VALVE), not the box itself
                            if is_zone_select and (is_box_node or node_type not in [DEVICE_TYPE_VALVE]): # Add other controllable zone types if known
                                continue

                            identified.append(IdentifiedEntity( platform=platform, node_id=node_id_int, description_key=key, entity_description=description, is_box_node_entity=is_box_node, map_info=map_info ))
        return identified

    def _check_entity_data_exists(
        self, device_info: dict, general_config: dict, node_data: dict,
        entity_key: str, map_info: AnyMapInfoType
    ) -> bool:
        """Check if the required data path for an entity exists."""
        try:
            data_source_key = map_info[0]
            path_list = map_info[1]
            value_key = map_info[2] if len(map_info) > 2 else None
            get_formatter = map_info[3] if len(map_info) > 3 and callable(map_info[3]) else None

            source_data: dict | None = None
            if data_source_key == "device_info": source_data = device_info
            elif data_source_key == "general_config": source_data = general_config
            elif data_source_key == "info": source_data = node_data.get("info")
            elif data_source_key == "config": source_data = node_data.get("config")
            else: return False # Includes action keys which don't map to data

            if source_data is None: return False

            # Special check for reconstructor needing parent dict
            if get_formatter and get_formatter.__name__ == 'reconstruct_ip_from_dict':
                parent_dict = get_nested_value(source_data, *path_list)
                return get_formatter(parent_dict, value_key) is not None # value_key is base_key here
            else:
                val = get_nested_value(source_data, *path_list, value_key=value_key)
                return val is not None
        except Exception:
            return False

    def _should_add_node_entity(self, key: str, node_info: dict[str, Any]) -> bool:
        """Apply filters based on node type for specific sensor entities."""
        node_type = node_info.get(NODE_INFO_KEY_DEVICE_TYPE)
        # Only add CO2 entities if node is CO2 sensor or Box
        if ("co2" in key.lower() or "iaq_co2" in key.lower()) and node_type not in (DEVICE_TYPE_UCCO2, DEVICE_TYPE_BOX): return False
        # Only add RH entities if node is RH sensor or Box
        if ("humidity" in key.lower() or "iaq_rh" in key.lower() or key == "config.rh.delta" or key == "config.rh.setpoint") and node_type not in (DEVICE_TYPE_UCRH, DEVICE_TYPE_BOX): return False
        # Only add Temp Dependent switch if node is CO2 or RH sensor (or Box?)
        if key == "config.temp.dependent" and node_type not in (DEVICE_TYPE_UCCO2, DEVICE_TYPE_UCRH, DEVICE_TYPE_BOX): return False
        return True

    def _should_skip_based_on_node_type(self, key: str, is_box_node: bool) -> bool:
        """Determine if an entity should be skipped based on its key and if it's the box node."""
        is_device_info_key = key.startswith("device.info.")
        is_box_config_key = key.startswith("config.box.") or key.startswith("config.ip.") or key.startswith("config.eco.")
        is_box_action_key = key.startswith("action.") and key not in ["action.zone.set_state", "action.overrule.clear", "action.load_defaults", "action.reset", "action.link_mode.toggle", "action.show.toggle"]
        is_node_info_key = key.startswith("node.info.")
        is_node_config_key = key.startswith("config.") and not is_box_config_key
        is_node_action_key = key in ["action.zone.set_state", "action.overrule.clear", "action.load_defaults", "action.reset", "action.link_mode.toggle", "action.show.toggle"]

        # Skip device-level info/config/actions if we are processing a node entity
        if not is_box_node and (is_device_info_key or is_box_config_key or is_box_action_key): return True
        # Skip node-level info/config/actions if we are processing the box node, *unless* allowed
        if is_box_node and (is_node_info_key or is_node_config_key or is_node_action_key) and key not in ALLOWED_NODE_ENTITY_KEYS_ON_BOX: return True

        return False

    # === Action Methods ===
    async def _call_api_action(self, action_coro: asyncio.Task, requires_refresh: bool = True) -> bool:
        """Helper to call API action, handle errors, trigger refresh."""
        try:
            success = await action_coro
            if success:
                if requires_refresh: await self.async_request_refresh()
                return True
            _LOGGER.warning("API action reported failure.")
            # Raise a user-facing error for command failures
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key=TRANS_ERROR_COMMAND_FAILED, translation_placeholders={"error_details": "Action returned unsuccessful"})
        except ApiError as err:
            _LOGGER.error("API error during action: %s", err)
            raise HomeAssistantError(f"Duco command failed: {err}", translation_domain=DOMAIN, translation_key=TRANS_ERROR_COMMAND_FAILED, translation_placeholders={"error_details": str(err)}) from err
        except Exception as err:
            _LOGGER.exception("Unexpected error during action")
            raise HomeAssistantError(f"Unexpected error: {err}", translation_domain=DOMAIN, translation_key=TRANS_ERROR_UNKNOWN, translation_placeholders={"error_details": str(err)}) from err

    async def async_box_set_config(self, module: str, parameter: str, value: Any) -> bool:
        """Set a 'box' area config parameter."""
        return await self._call_api_action( self.api.set_general_config_value("box", module, parameter, value) )
    async def async_ip_set_config(self, module: str, parameter: str, value: Any) -> bool:
        """Set an 'ip' area config parameter."""
        return await self._call_api_action( self.api.set_general_config_value("ip", module, parameter, value) )
    async def async_eco_set_config(self, module: str, parameter: str, value: Any) -> bool:
        """Set an 'eco' area config parameter."""
        return await self._call_api_action( self.api.set_general_config_value("eco", module, parameter, value) )

    async def async_node_set_config( self, node_id: int, parameter: str, value: Any, module: str | None = None ) -> bool:
        """Set a config parameter for a specific node."""
        # Determine V2 module name if needed (could be moved to entity logic)
        if self.api._api_version == API_V2 and module is None: # type: ignore[attr-defined]
            if parameter == KEY_LOCATION_V1_CONFIG: module = V2_MODULE_NODECONFIG_LOCATION
            elif parameter == KEY_PARAM_CO2SETPOINT: module = V2_MODULE_NODECONFIG_SENSOR_CO2
            elif parameter == KEY_PARAM_RHSETPOINT: module = V2_MODULE_NODECONFIG_SENSOR_RH
            elif parameter == KEY_PARAM_RHDELTA: module = V2_MODULE_NODECONFIG_RH
            elif parameter == KEY_PARAM_TEMPDEPENDENT: module = V2_MODULE_NODECONFIG_TEMP
            elif parameter in (KEY_PARAM_AUTOMAX, KEY_PARAM_AUTOMIN): module = V2_MODULE_NODECONFIG_VENT_AUTO
            elif parameter in (KEY_PARAM_MANUAL1, KEY_PARAM_MANUAL2, KEY_PARAM_MANUAL3, KEY_PARAM_MANUALTIMEOUT): module = V2_MODULE_NODECONFIG_VENT_MANUAL
            else: module = parameter # Fallback for simple cases or V1
            _LOGGER.debug("Coordinator determined V2 module '%s' for node param '%s'", module, parameter)
        return await self._call_api_action( self.api.set_node_config_value(node_id, parameter, value, module) )

    async def async_node_set_operation_state(self, node_id: int, state: str) -> bool:
        """Set operational state for a node."""
        return await self._call_api_action( self.api.perform_node_action(node_id, ACTION_SET_OPER_STATE, state) )
    async def async_node_set_overrule(self, node_id: int, value: int) -> bool:
        """Set manual overrule percentage for a node."""
        return await self._call_api_action( self.api.perform_node_action(node_id, ACTION_SET_OVERRULE, value) )
    async def async_node_reset(self, node_id: int) -> bool:
        """Reset a specific node."""
        return await self._call_api_action( self.api.perform_node_action(node_id, ACTION_RESET_NODE) )
    async def async_node_load_defaults(self, node_id: int) -> bool:
        """Load defaults onto a specific node."""
        return await self._call_api_action( self.api.perform_node_action(node_id, ACTION_LOAD_DEFAULTS_NODE) )
    async def async_node_toggle_show(self, node_id: int, show: bool) -> bool:
        """Set 'show' status for a node."""
        return await self._call_api_action( self.api.perform_node_action(node_id, ACTION_SET_SHOW, 1 if show else 0) )
    async def async_node_set_link_mode(self, node_id: int, link_mode: bool) -> bool:
        """Set link mode (pairing) for a node."""
        return await self._call_api_action( self.api.perform_node_action(node_id, ACTION_SET_LINK_MODE, 1 if link_mode else 0) )
    async def async_node_set_parent(self, node_id: int, parent_id: int) -> bool:
        """Set parent node ID."""
        return await self._call_api_action( self.api.perform_node_action(node_id, ACTION_SET_PARENT, parent_id) )
    async def async_node_set_association(self, node_id: int, asso_id: int) -> bool:
        """Set associated node ID."""
        return await self._call_api_action( self.api.perform_node_action(node_id, ACTION_SET_ASSOCIATION, asso_id) )

    async def async_box_set_time(self) -> bool:
        """Synchronize box time."""
        return await self._call_api_action( self.api.perform_device_action(ACTION_SET_TIME) )
    async def async_box_toggle_installer_mode(self, enable: bool) -> bool:
        """Enable/disable installer mode."""
        return await self._call_api_action( self.api.perform_device_action(ACTION_SET_INSTALLER_MODE, 1 if enable else 0) )
    async def async_box_clear_network(self) -> bool:
        """Clear RF network config."""
        return await self._call_api_action( self.api.perform_device_action(ACTION_CLEAR_NETWORK) )
    async def async_box_set_calibration(self, command: DucoCalibCommand | str) -> bool:
        """Send calibration command."""
        cmd_value = command.value if isinstance(command, DucoCalibCommand) else command
        return await self._call_api_action( self.api.perform_device_action(ACTION_SET_CALIBRATION, cmd_value) )
    async def async_board_reset(self) -> bool:
        """Reboot the device."""
        # Reboot might disconnect, so don't require refresh immediately
        return await self._call_api_action( self.api.perform_device_action(ACTION_REBOOT_DEVICE), requires_refresh=False )