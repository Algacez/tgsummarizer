import json
import os
from typing import Dict, Any


class Config:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}")
                self._config = self.get_default_config()
                self.save_config()
        else:
            self._config = self.get_default_config()
            self.save_config()

    def save_config(self) -> None:
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving config: {e}")

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "telegram": {
                "bot_token": "",
                "allowed_chats": [],
                "allow_bot_messages": False
            },
            "ai": {
                "api_base": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-3.5-turbo",
                "max_tokens": 1000,
                "temperature": 0.7
            },
            "storage": {
                "data_dir": "data",
                "file_format": "json"
            },
            "summary": {
                "daily_summary_enabled": True,
                "daily_summary_time": "23:59",
                "manual_summary_message_count": 100,
                "manual_summary_hours": 24,
                "timezone_offset_hours": 0
            },
            "logging": {
                "level": "INFO",
                "file": "bot.log"
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()

    @property
    def bot_token(self) -> str:
        return self.get("telegram.bot_token", "")

    @property
    def allowed_chats(self) -> list:
        return self.get("telegram.allowed_chats", [])

    @property
    def allow_bot_messages(self) -> bool:
        return self.get("telegram.allow_bot_messages", False)

    @property
    def api_base(self) -> str:
        return self.get("ai.api_base", "https://api.openai.com/v1")

    @property
    def api_key(self) -> str:
        return self.get("ai.api_key", "")

    @property
    def model(self) -> str:
        return self.get("ai.model", "gpt-3.5-turbo")

    @property
    def data_dir(self) -> str:
        return self.get("storage.data_dir", "data")

    @property
    def daily_summary_enabled(self) -> bool:
        return self.get("summary.daily_summary_enabled", True)

    @property
    def daily_summary_time(self) -> str:
        return self.get("summary.daily_summary_time", "23:59")

    @property
    def manual_summary_message_count(self) -> int:
        return self.get("summary.manual_summary_message_count", 100)

    @property
    def manual_summary_hours(self) -> int:
        return self.get("summary.manual_summary_hours", 24)

    @property
    def timezone_offset_hours(self) -> int:
        return self.get("summary.timezone_offset_hours", 0)


config = Config()