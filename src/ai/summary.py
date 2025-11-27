import json
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..config import config


class AISummary:
    def __init__(self):
        self.api_base = config.api_base.rstrip('/')
        self.api_key = config.api_key
        self.model = config.model
        self.max_tokens = config.get("ai.max_tokens", 1000)
        self.temperature = config.get("ai.temperature", 0.7)

    def _make_api_request(self, messages: List[Dict[str, str]],
                         max_tokens: Optional[int] = None) -> Optional[str]:
        if not self.api_key:
            return "错误：未配置API密钥，请在config.json中设置ai.api_key"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature
        }

        try:
            print(f"Making API request to: {self.api_base}/chat/completions")
            print(f"Model: {self.model}, Max tokens: {max_tokens or self.max_tokens}")
            print(f"Messages count: {len(messages)}")

            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60  # 增加超时时间
            )

            print(f"Response status: {response.status_code}")

            if response.status_code != 200:
                print(f"Response body: {response.text}")
                return f"API请求失败: HTTP {response.status_code} - {response.text[:200]}"

            result = response.json()

            if "choices" not in result or not result["choices"]:
                print(f"Invalid API response: {result}")
                return "API响应格式错误：缺少choices字段"

            if "message" not in result["choices"][0]:
                print(f"Invalid choice format: {result['choices'][0]}")
                return "API响应格式错误：缺少message字段"

            content = result["choices"][0]["message"]["content"]
            print(f"Successfully got response, length: {len(content)}")
            return content

        except requests.exceptions.Timeout:
            return "API请求超时：请检查网络连接或稍后重试"
        except requests.exceptions.ConnectionError as e:
            return f"网络连接错误: {str(e)}"
        except requests.exceptions.RequestException as e:
            return f"API请求失败: {str(e)}"
        except json.JSONDecodeError as e:
            return f"JSON解析失败: {str(e)}"
        except (KeyError, IndexError) as e:
            return f"API响应解析失败: {str(e)}"
        except Exception as e:
            return f"未知错误: {str(e)}"

    def format_messages_for_summary(self, messages: List[Dict[str, Any]]) -> str:
        formatted_msgs = []
        for msg in messages:
            timestamp = msg.get('timestamp', '')
            user = msg.get('user', 'Unknown')
            text = msg.get('text', '')

            if text:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime("%H:%M")
                    formatted_msgs.append(f"[{time_str}] {user}: {text}")
                except:
                    formatted_msgs.append(f"{user}: {text}")

        return "\n".join(formatted_msgs)

    def generate_summary(self, messages: List[Dict[str, Any]],
                        summary_type: str = "daily") -> Optional[str]:
        if not messages:
            return "没有消息可以总结"

        formatted_messages = self.format_messages_for_summary(messages)

        if summary_type == "daily":
            system_prompt = """你是一个专业的群聊分析助手。请根据提供的群组聊天记录，生成一份结构化的分话题总结。

重要规则：只输出总结内容，不要添加任何开场白、解释或其他无关文字。不要使用转义字符。

输出格式要求：
热聊话题

1. [话题标题]
   - 时间：[时间范围，如：14:30-16:45]
   - 群成员：[参与该话题讨论的主要成员]
   - 总结：[详细描述该话题的讨论过程、重要观点和结论，合理长度]
   - 高热发言：[引用或转述该话题中最有代表性的观点或有趣言论]

格式要求：
- 话题标题要简洁且能概括讨论核心内容
- 时间范围要准确反映讨论的起止时间
- 群成员列出该话题的主要参与者，3-5人最佳
- 总结部分要详细但不冗长
- 高热发言要生动有趣，体现讨论的热点
- 按话题重要性和热度排序，最重要的放在前面
- 话题数量根据实际讨论情况调整，通常3-8个

请直接按格式输出总结内容，不要使用任何转义字符："""
        else:
            system_prompt = """你是一个专业的群聊分析助手。请根据提供的群组聊天记录，生成一份结构化的分话题总结。

重要规则：只输出总结内容，不要添加任何开场白、解释或其他无关文字。不要使用转义字符。

输出格式要求：
热聊话题

1. [话题标题]
   - 时间：[时间范围，如：14:30-16:45]
   - 群成员：[参与该话题讨论的主要成员]
   - 总结：[详细描述该话题的讨论过程、重要观点和结论，合理长度]
   - 高热发言：[引用或转述该话题中最有代表性的观点或有趣言论]

格式要求：
- 话题标题要简洁且能概括讨论核心内容
- 时间范围要准确反映讨论的起止时间
- 群成员列出该话题的主要参与者，3-5人最佳
- 总结部分要详细但不冗长
- 高热发言要生动有趣，体现讨论的热点
- 按话题重要性和热度排序，最重要的放在前面
- 话题数量根据实际讨论情况调整，通常3-8个

请直接按格式输出总结内容，不要使用任何转义字符："""

        api_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"以下是群组消息记录：\n\n{formatted_messages}"}
        ]

        return self._make_api_request(api_messages)

    def generate_period_summary(self, messages: List[Dict[str, Any]], period_name: str) -> Optional[str]:
        """生成特定时段的总结"""
        if not messages:
            return "没有消息可以总结"

        try:
            formatted_messages = self.format_messages_for_summary(messages)

            system_prompt = f"""你是一个专业的群聊分析助手。请根据提供的群组聊天记录，生成一份关于{period_name}时段的结构化分话题总结。

重要规则：只输出总结内容，不要添加任何开场白、解释或其他无关文字。不要使用转义字符。

输出格式要求：
热聊话题

1. [话题标题]
   - 时间：[具体时间范围，如：14:30-16:45]
   - 群成员：[参与该话题讨论的主要成员]
   - 总结：[详细描述该话题的讨论过程、重要观点和结论，合理长度]
   - 高热发言：[引用或转述该话题中最有代表性的观点或有趣言论]

格式要求：
- 话题标题要简洁且能概括讨论核心内容
- 时间范围要准确反映讨论的起止时间
- 群成员列出该话题的主要参与者，3-5人最佳
- 总结部分要详细但不冗长
- 高热发言要生动有趣，体现讨论的热点
- 按话题重要性和热度排序，最重要的放在前面
- 话题数量根据实际讨论情况调整，通常3-8个

请直接按格式输出总结内容，不要使用任何转义字符："""

            api_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"以下是{period_name}时段的群组消息记录：\n\n{formatted_messages}"}
            ]

            return self._make_api_request(api_messages)
        except Exception as e:
            return f"错误：生成{period_name}时段总结时发生异常 - {str(e)}"

    def generate_daily_summary(self, chat_id: int, messages: List[Dict[str, Any]]) -> Optional[str]:
        summary = self.generate_summary(messages, "daily")

        if summary and not summary.startswith("错误") and not summary.startswith("没有消息"):
            date_str = datetime.now().strftime("%Y-%m-%d")

            header = f"📊 **群组每日总结** ({date_str})\n"
            header += f"📝 消息总数: {len(messages)} 条\n"

            user_counts = {}
            for msg in messages:
                user = msg.get('user', 'Unknown')
                user_counts[user] = user_counts.get(user, 0) + 1

            if user_counts:
                top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                header += f"👥 活跃用户: {', '.join([f'{user}({count})' for user, count in top_users])}\n\n"

            return header + summary

        return summary

    def generate_manual_summary(self, chat_id: int, messages: List[Dict[str, Any]],
                              hours: int = 24) -> Optional[str]:
        summary = self.generate_summary(messages, "manual")
        return summary

    def test_connection(self) -> bool:
        test_messages = [
            {"role": "system", "content": "你是一个测试助手。"},
            {"role": "user", "content": "请回复'连接成功'"}
        ]

        response = self._make_api_request(test_messages, max_tokens=50)
        return response and "连接成功" in response


__all__ = ['AISummary']