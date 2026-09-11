from __future__ import annotations

DOMAIN = "mcss"

CONF_HOST = "host"
CONF_API_KEY_ENTITY = "api_key_entity"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CONSOLE_INTERVAL = "console_interval"
CONF_CONSOLE_LINES = "console_lines"
CONF_PLAYER_INTERVAL = "player_interval"

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_CONSOLE_INTERVAL = 5
DEFAULT_CONSOLE_LINES = 50
DEFAULT_PLAYER_INTERVAL = 60

ACTION_STOP = 1
ACTION_START = 2
ACTION_KILL = 3
ACTION_RESTART = 4

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SERVER_ACTION = "server_action"
ATTR_SERVER_ID = "server_id"
ATTR_COMMAND = "command"
ATTR_ACTION = "action"

PLATFORMS = ["sensor", "button", "camera", "text"]