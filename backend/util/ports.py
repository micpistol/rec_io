import sys
import json
import os

def get_port(service_name):
    port_config_path = os.path.join(os.path.dirname(__file__), 'port_config.json')
    print(f"[DEBUG] Loading port config from: {port_config_path}", file=sys.stderr)
    with open(port_config_path) as f:
        raw = f.read()
    print(f"[DEBUG] Raw port_config.json contents: {raw}", file=sys.stderr)
    ports = json.loads(raw)
    return int(ports[service_name])

def get_executor_port():
    return get_port("KALSHI_EXECUTOR_PORT")

def get_main_app_port():
    return get_port("MAIN_APP_PORT")

def get_manager_port():
    return get_port("TRADE_MANAGER_PORT")

def get_api_watchdog_port():
    return get_port("API_WATCHDOG_PORT")


# ------------------------------------------------------------------------
# SINGLE-SOURCE PORT RESOLVER
# ------------------------------------------------------------------------

def get_positions_api_port() -> int:
    """
    The only function any code should call when it needs the FastAPI
    server that exposes `/api/db/*` (positions, fills, settlements).

    1. First look for MAIN_APP_PORT       (new, preferred)
    2. Fallback to API_WATCHDOG_PORT      (legacy name)
    3. Finally default to 5090
    """
    try:
        return get_port("MAIN_APP_PORT")
    except KeyError:
        try:
            return get_port("API_WATCHDOG_PORT")
        except KeyError:
            sys.stderr.write(
                "[WARN] MAIN_APP_PORT and API_WATCHDOG_PORT "
                "not in port_config.json –­ defaulting to 5090\n"
            )
            return 5090