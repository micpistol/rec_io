# Global account mode state shared across backend
account_mode_state = {"mode": "prod"}

import os
import json
from backend.util.paths import get_data_dir

def get_account_mode():
    try:
        account_mode_file = os.path.join(get_data_dir(), "account_mode_state.json")
        with open(account_mode_file) as f:
            return json.load(f).get("mode", "prod")
    except Exception:
        return "prod"

def set_account_mode(mode):
    if mode not in ("prod", "demo"):
        raise ValueError("Invalid mode")
    account_mode_file = os.path.join(get_data_dir(), "account_mode_state.json")
    # Ensure directory exists
    os.makedirs(os.path.dirname(account_mode_file), exist_ok=True)
    with open(account_mode_file, "w") as f:
        json.dump({"mode": mode}, f)
