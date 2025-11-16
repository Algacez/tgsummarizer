import json
import os
from datetime import datetime, date
from typing import List, Dict, Any
from pathlib import Path
import pytz

from ..config import config


class MessageStorage:
    def __init__(self):
        self.data_dir = Path(config.data_dir)
        self.data_dir.mkdir(exist_ok=True)

    def get_chat_dir(self, chat_id: int) -> Path:
        chat_dir = self.data_dir / str(chat_id)
        chat_dir.mkdir(exist_ok=True)
        return chat_dir

    def get_today_file_path(self, chat_id: int) -> Path:
        today = date.today().strftime("%Y-%m-%d")
        chat_dir = self.get_chat_dir(chat_id)
        return chat_dir / f"{today}.json"

    def get_file_path(self, chat_id: int, target_date: date) -> Path:
        date_str = target_date.strftime("%Y-%m-%d")
        chat_dir = self.get_chat_dir(chat_id)
        return chat_dir / f"{date_str}.json"

    def save_message(self, chat_id: int, message: Dict[str, Any]) -> None:
        file_path = self.get_today_file_path(chat_id)

        # 使用北京时间确定今天的日期
        beijing_tz = pytz.timezone('Asia/Shanghai')
        beijing_now = datetime.now(beijing_tz)
        beijing_today = beijing_now.date()

        messages = self.load_messages(chat_id, beijing_today)

        # 使用北京时间戳
        message['timestamp'] = beijing_now.isoformat()
        messages.append(message)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving message: {e}")

    def load_messages(self, chat_id: int, target_date: date) -> List[Dict[str, Any]]:
        file_path = self.get_file_path(chat_id, target_date)

        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading messages: {e}")
            return []

    def load_recent_messages(self, chat_id: int, hours: int = 24) -> List[Dict[str, Any]]:
        now = datetime.now()
        messages = []

        for day_offset in range(max(0, hours // 24 + 1)):
            target_date = (now.date() - timedelta(days=day_offset))
            day_messages = self.load_messages(chat_id, target_date)

            for msg in day_messages:
                msg_time = datetime.fromisoformat(msg['timestamp'])
                time_diff = (now - msg_time).total_seconds()

                if time_diff <= hours * 3600:
                    messages.append(msg)

        messages.sort(key=lambda x: x['timestamp'])
        return messages

    def get_message_count(self, chat_id: int, hours: int = 24) -> int:
        return len(self.load_recent_messages(chat_id, hours))

    def get_latest_messages(self, chat_id: int, count: int = 100) -> List[Dict[str, Any]]:
        messages = []
        now = datetime.now()

        for day_offset in range(30):
            target_date = (now.date() - timedelta(days=day_offset))
            day_messages = self.load_messages(chat_id, target_date)
            messages.extend(day_messages)

            if len(messages) >= count:
                break

        messages.sort(key=lambda x: x['timestamp'], reverse=True)
        return messages[:count]

    def delete_old_messages(self, chat_id: int, days_to_keep: int = 30) -> None:
        chat_dir = self.get_chat_dir(chat_id)
        cutoff_date = date.today() - timedelta(days=days_to_keep)

        for file_path in chat_dir.glob("*.json"):
            try:
                file_date_str = file_path.stem
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()

                if file_date < cutoff_date:
                    file_path.unlink()
                    print(f"Deleted old messages file: {file_path}")
            except ValueError:
                continue

    def get_chat_list(self) -> List[int]:
        chat_ids = []
        for item in self.data_dir.iterdir():
            if item.is_dir():
                # 支持负数群组ID（如 -1003128718593）
                try:
                    chat_id = int(item.name)
                    chat_ids.append(chat_id)
                except ValueError:
                    # 忽略非数字目录名
                    continue
        return chat_ids

    def get_daily_stats(self, chat_id: int, target_date: date) -> Dict[str, Any]:
        messages = self.load_messages(chat_id, target_date)

        if not messages:
            return {
                "date": target_date.isoformat(),
                "message_count": 0,
                "user_count": 0,
                "users": []
            }

        user_counts = {}
        for msg in messages:
            user = msg.get('user', 'Unknown')
            user_counts[user] = user_counts.get(user, 0) + 1

        return {
            "date": target_date.isoformat(),
            "message_count": len(messages),
            "user_count": len(user_counts),
            "users": sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        }


from datetime import timedelta