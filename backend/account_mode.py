# Global account mode state shared across backend
account_mode_state = {"mode": "prod"}

import os
import json

def get_account_mode():
    try:
        with open(os.path.join(os.path.dirname(__file__), "account_mode_state.json")) as f:
            return json.load(f).get("mode", "prod")
    except Exception:
        return "prod"

def set_account_mode(mode):
    if mode not in ("prod", "demo"):
        raise ValueError("Invalid mode")
    with open(os.path.join(os.path.dirname(__file__), "account_mode_state.json"), "w") as f:
        json.dump({"mode": mode}, f)
