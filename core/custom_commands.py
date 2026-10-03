import os
import json
import uuid
from typing import List, Dict, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM_COMMANDS_FILE = os.path.join(PROJECT_ROOT, "config", "custom_commands.json")


class CustomCommandManager:
    """
    Registry for user-defined voice & gesture commands mapping to system actions.
    Ensures input validation, risk engine evaluation, and JSON import/export.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(CustomCommandManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.commands: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        """Loads custom commands from JSON storage with default fallback."""
        if os.path.exists(CUSTOM_COMMANDS_FILE):
            try:
                with open(CUSTOM_COMMANDS_FILE, "r", encoding="utf-8") as f:
                    self.commands = json.load(f)
                    return
            except Exception as e:
                print(f"[CustomCommandManager] Error loading custom commands: {e}")

        # Default pre-populated example command
        self.commands = [
            {
                "id": str(uuid.uuid4())[:8],
                "name": "Ouvrir Mes Documents",
                "trigger_type": "voice",
                "trigger_value": "ouvre mes documents",
                "action_type": "open_path",
                "action_target": os.path.expanduser("~/Documents"),
                "risk_level": "LOW",
                "enabled": True
            }
        ]
        self.save()

    def save(self) -> None:
        """Persists current commands to JSON."""
        try:
            os.makedirs(os.path.dirname(CUSTOM_COMMANDS_FILE), exist_ok=True)
            with open(CUSTOM_COMMANDS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.commands, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[CustomCommandManager] Error saving custom commands: {e}")

    def find_match(self, input_text: str) -> Optional[Dict[str, Any]]:
        """Matches a voice phrase or gesture name against enabled custom commands."""
        clean_input = input_text.strip().lower()
        for cmd in self.commands:
            if not cmd.get("enabled", True):
                continue
            val = str(cmd.get("trigger_value", "")).strip().lower()
            if val and (val == clean_input or val in clean_input):
                return cmd
        return None

    def add_command(
        self,
        name: str,
        trigger_type: str,
        trigger_value: str,
        action_type: str,
        action_target: str,
        risk_level: str = "LOW"
    ) -> Dict[str, Any]:
        """Creates and persists a new custom command."""
        cmd = {
            "id": str(uuid.uuid4())[:8],
            "name": name.strip(),
            "trigger_type": trigger_type,
            "trigger_value": trigger_value.strip().lower(),
            "action_type": action_type,
            "action_target": action_target.strip(),
            "risk_level": risk_level.upper(),
            "enabled": True
        }
        self.commands.append(cmd)
        self.save()
        return cmd

    def delete_command(self, cmd_id: str) -> bool:
        """Deletes a custom command by ID."""
        initial_count = len(self.commands)
        self.commands = [c for c in self.commands if c.get("id") != cmd_id]
        if len(self.commands) != initial_count:
            self.save()
            return True
        return False

    def export_json(self, export_path: str) -> bool:
        """Exports custom commands to an external JSON file."""
        try:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(self.commands, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[CustomCommandManager] Export error: {e}")
            return False

    def import_json(self, import_path: str) -> bool:
        """Imports and validates custom commands from an external JSON file."""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    validated = []
                    for item in data:
                        if isinstance(item, dict) and "trigger_value" in item and "action_target" in item:
                            if "id" not in item:
                                item["id"] = str(uuid.uuid4())[:8]
                            validated.append(item)
                    if validated:
                        self.commands = validated
                        self.save()
                        return True
        except Exception as e:
            print(f"[CustomCommandManager] Import error: {e}")
        return False
