"""
Custom Command Compiler (Project Aether-Human V3.0)
Allows users to compile and execute custom private commands and triggers
strictly within their personal sandbox without cross-tenant pollution.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Aether.MultiTenant.CommandCompiler")


@dataclass
class CustomCommand:
    command_trigger: str  # e.g. "/study", "كود_سري", "/cheer"
    response_template: str
    action_type: str = "TEXT"  # 'TEXT', 'AI_PROMPT', 'DYNAMIC'
    description: str = ""
    usage_count: int = 0
    created_at: float = 0.0

    @property
    def trigger(self) -> str:
        return self.command_trigger

    @property
    def action(self) -> str:
        return self.action_type


class CustomCommandCompiler:
    """
    Manages custom commands per tenant.
    """

    def __init__(self, storage_path: str = "data/tenant_custom_commands.json"):
        self.storage_path = storage_path
        self._commands: Dict[int, Dict[str, CustomCommand]] = {}
        self._ensure_storage()
        self._load()

    def _ensure_storage(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load(self) -> None:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                for uid_str, cmds in raw_data.items():
                    uid = int(uid_str)
                    self._commands[uid] = {}
                    for trig, c_dict in cmds.items():
                        # Filter to only known fields of CustomCommand
                        valid_fields = {
                            "command_trigger", "response_template", "action_type",
                            "description", "usage_count", "created_at"
                        }
                        sanitized = {k: v for k, v in c_dict.items() if k in valid_fields}
                        self._commands[uid][trig] = CustomCommand(**sanitized)
            logger.info(f"Loaded custom commands for {len(self._commands)} users.")
        except Exception as exc:
            logger.warning(f"Could not load custom commands: {exc}")

    def _save(self) -> None:
        try:
            data = {
                str(uid): {trig: asdict(cmd) for trig, cmd in cmds.items()}
                for uid, cmds in self._commands.items()
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error(f"Failed to save custom commands: {exc}")

    def register_command(
        self,
        user_id: int,
        trigger: str,
        response: str = "",
        action_type: str = "TEXT",
        action: Optional[str] = None,
        response_template: Optional[str] = None,
        response_text: Optional[str] = None,
        description: str = "",
        **kwargs,
    ) -> CustomCommand:
        """
        Compiles a new custom command for a specific user.
        Accepts action, response_text, response_template, and arbitrary kwargs flexibly.
        """
        clean_trig = trigger.strip().lower()
        if user_id not in self._commands:
            self._commands[user_id] = {}

        eff_response = (
            response_template
            or response_text
            or response
            or kwargs.get("response_template")
            or kwargs.get("response_text")
            or kwargs.get("text")
            or ""
        )
        eff_action = action or action_type or kwargs.get("action") or "TEXT"
        eff_desc = description or kwargs.get("description") or ""

        cmd = CustomCommand(
            command_trigger=clean_trig,
            response_template=str(eff_response).strip(),
            action_type=str(eff_action).upper(),
            description=str(eff_desc).strip(),
            created_at=time.time(),
        )
        self._commands[user_id][clean_trig] = cmd
        self._save()
        logger.info(f"Registered custom command '{clean_trig}' for User [{user_id}]")
        return cmd

    def delete_command(self, user_id: int, trigger: str) -> bool:
        clean_trig = trigger.strip().lower()
        if user_id in self._commands and clean_trig in self._commands[user_id]:
            del self._commands[user_id][clean_trig]
            self._save()
            return True
        return False

    def clear_user_commands(self, user_id: int) -> bool:
        if user_id in self._commands:
            self._commands[user_id] = {}
            self._save()
            return True
        return False

    def list_commands(self, user_id: int) -> List[CustomCommand]:
        if user_id not in self._commands:
            return []
        return list(self._commands[user_id].values())

    def match_and_execute(self, user_id: int, text: str) -> Optional[Dict[str, Any]]:
        """
        Checks if text matches any custom command for this user.
        Returns execution payload or None.
        """
        if user_id not in self._commands:
            return None

        clean_text = text.strip().lower()
        # Direct command match
        user_cmds = self._commands[user_id]
        if clean_text in user_cmds:
            cmd = user_cmds[clean_text]
            return {
                "triggered": True,
                "command": cmd.command_trigger,
                "action": cmd.action_type,
                "output": cmd.response_template,
            }

        return None


custom_commands = CustomCommandCompiler()

