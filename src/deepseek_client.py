"""
DeepSeek API 客户端模块。
封装 OpenAI 兼容的 /chat/completions 接口，提供重试和 JSON 解析 fallback。
"""

import json
import re
import time
import logging
from typing import Optional

import requests

logger = logging.getLogger("news_digest.deepseek")


class DeepSeekError(Exception):
    """DeepSeek API 调用失败。"""
    pass


class DeepSeekClient:
    """DeepSeek API 客户端（OpenAI 兼容接口）。

    使用 requests 直接调用，零额外 SDK 依赖。
    内置重试、超时和 JSON 解析 fallback 机制。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: int = 90,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """发送聊天补全请求并返回模型回复文本。

        Args:
            messages: 标准 OpenAI 格式的消息列表。
            temperature: 覆盖默认温度。
            max_tokens: 覆盖默认最大 token 数。
            json_mode: 是否启用 JSON 模式（response_format）。

        Returns:
            模型回复的文本内容。

        Raises:
            DeepSeekError: API 调用失败或全部重试耗尽。
        """
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.debug(
                        f"  API 调用成功: {data.get('usage', {}).get('total_tokens', '?')} tokens"
                    )
                    return content

                elif resp.status_code == 429:
                    # 频率限制 — 等待后重试
                    wait = 30 * (attempt + 1)
                    logger.warning(f"  API 429 频率限制，等待 {wait}s 后重试...")
                    time.sleep(wait)

                elif resp.status_code >= 500:
                    # 服务端错误 — 退避重试
                    wait = 2 ** attempt
                    logger.warning(f"  API {resp.status_code} 错误，等待 {wait}s 后重试...")
                    time.sleep(wait)

                else:
                    raise DeepSeekError(
                        f"API 返回 {resp.status_code}: {resp.text[:300]}"
                    )

            except requests.Timeout:
                last_error = DeepSeekError(f"请求超时 ({self.timeout}s)")
                if attempt < self.max_retries:
                    logger.warning(f"  API 超时，重试 {attempt+1}/{self.max_retries}")
            except requests.ConnectionError as e:
                last_error = DeepSeekError(f"连接失败: {e}")
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(f"  连接失败，等待 {wait}s 后重试...")
                    time.sleep(wait)
            except DeepSeekError:
                raise
            except Exception as e:
                last_error = DeepSeekError(f"未知错误: {e}")
                if attempt < self.max_retries:
                    logger.warning(f"  未知错误，重试 {attempt+1}/{self.max_retries}")

        raise last_error or DeepSeekError("API 调用失败（已达最大重试次数）")

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
    ) -> dict:
        """发送请求并强制返回 JSON 对象。

        内置 JSON 解析 fallback 链：
        1. 直接 json.loads
        2. 去除 markdown 代码块后解析
        3. 正则提取首个 JSON 对象

        Args:
            messages: 标准 OpenAI 格式的消息列表。
            temperature: 可选温度覆盖。

        Returns:
            解析后的 JSON 字典。

        Raises:
            DeepSeekError: 所有 JSON 解析尝试均失败。
        """
        raw = self.chat_completion(
            messages,
            temperature=temperature,
            json_mode=True,
        )

        return _parse_json_response(raw)


def _parse_json_response(raw: str) -> dict:
    """JSON 响应解析 fallback 链。"""
    attempts = []

    # 尝试 1: 直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        attempts.append(f"直接解析: {e}")

    # 尝试 2: 去除 markdown 代码块
    cleaned = raw.strip()
    # 移除 ```json ... ``` 包裹
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        attempts.append(f"去代码块后: {e}")

    # 尝试 3: 正则提取首个 JSON 对象
    brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError as e:
            attempts.append(f"正则提取: {e}")

    # 全部失败
    raise DeepSeekError(
        f"无法解析 API 响应为 JSON。尝试了:\n"
        + "\n".join(f"  - {a}" for a in attempts)
        + f"\n\n原始响应 (前 500 字符):\n{raw[:500]}"
    )
