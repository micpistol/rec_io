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