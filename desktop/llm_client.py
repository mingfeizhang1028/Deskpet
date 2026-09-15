import json
import os
from urllib.parse import urlparse
from pathlib import Path

import keyring
from openai import OpenAI

from chat_stream import ChatCancelled, extract_delta, select_recent_messages


class ModelUnavailable(RuntimeError):
    pass


class YayanLLM:
    KEYRING_SERVICE = "YayanDesktopPet"
    KEYRING_ACCOUNT = "llm-api-key"

    def __init__(self, project_dir):
        self.project_dir = Path(project_dir)
        self.settings_path = self.project_dir / "desktop" / "settings.json"
        self.user_settings_path = self.project_dir / "output" / "runtime" / "user-settings.json"
        self.persona_path = self.project_dir / "desktop" / "persona.md"
        self.persona = self.persona_path.read_text(encoding="utf-8")
        self.reload_settings()

    def reload_settings(self):
        self.settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
        try:
            user_settings = json.loads(self.user_settings_path.read_text(encoding="utf-8-sig"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            user_settings = {}
        self.settings.update(user_settings)
        normalized_url = self.normalize_base_url(self.settings.get("llm_base_url"))
        if normalized_url:
            self.settings["llm_base_url"] = normalized_url
            if urlparse(normalized_url).hostname == "api.deepseek.com":
                self.settings["api_mode"] = "chat"

    @staticmethod
    def normalize_base_url(base_url):
        """Normalize known provider aliases without changing custom endpoints."""
        value = str(base_url or "").strip().rstrip("/")
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.hostname in {"platform.deepseek.com", "www.platform.deepseek.com"}:
            return "https://api.deepseek.com"
        return value

    def _api_config(self):
        base_url = (
            os.environ.get("YAYAN_LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or self.settings.get("llm_base_url")
        )
        base_url = self.normalize_base_url(base_url)
        requested_mode = os.environ.get("YAYAN_API_MODE") or self.settings.get(
            "api_mode", "responses"
        )
        api_mode = requested_mode
        hostname = urlparse(base_url).hostname if base_url else None
        # DeepSeek's OpenAI-compatible endpoint exposes Chat Completions,
        # not the newer Responses API. Keep existing settings usable and
        # avoid making the user re-enter a valid key for a 405 response.
        if hostname in {"api.deepseek.com", "platform.deepseek.com"}:
            api_mode = "chat"
        return base_url, api_mode

    def save_user_settings(self, values):
        allowed = {
            "llm_base_url",
            "llm_model",
            "api_mode",
            "tts_voice",
            "voice_input_enabled",
            "speak_replies",
            "interaction_style",
            "reminder_strength",
            "memory_mode",
            "api_key_saved",
        }
        current = {
            key: value for key, value in self.settings.items() if key in allowed
        }
        current.update({key: value for key, value in values.items() if key in allowed})
        if "llm_base_url" in current:
            current["llm_base_url"] = self.normalize_base_url(current["llm_base_url"])
        if urlparse(current.get("llm_base_url", "")).hostname == "api.deepseek.com":
            current["api_mode"] = "chat"
        self.user_settings_path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.user_settings_path.with_suffix(".pending")
        pending.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        pending.replace(self.user_settings_path)
        self.reload_settings()

    def save_api_key(self, api_key):
        api_key = api_key.strip()
        if not api_key:
            return
        keyring.set_password(self.KEYRING_SERVICE, self.KEYRING_ACCOUNT, api_key)
        if not keyring.get_password(self.KEYRING_SERVICE, self.KEYRING_ACCOUNT):
            raise ModelUnavailable("API 密钥没有成功写入 Windows 凭据管理器，请检查系统凭据服务。")
        self.save_user_settings({"api_key_saved": True})

    def clear_api_key(self):
        try:
            keyring.delete_password(self.KEYRING_SERVICE, self.KEYRING_ACCOUNT)
        except keyring.errors.PasswordDeleteError:
            pass
        self.save_user_settings({"api_key_saved": False})

    def _api_key(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            return api_key
        if os.environ.get("YAYAN_DISABLE_CREDENTIAL_STORE") == "1":
            return None
        if self.settings.get("api_key_saved"):
            try:
                return keyring.get_password(self.KEYRING_SERVICE, self.KEYRING_ACCOUNT)
            except Exception:
                return None
        return None

    @property
    def configured(self):
        # The flag is only a hint; the credential store is the source of truth.
        return bool(self._api_key())

    def _client(self):
        api_key = self._api_key()
        if not api_key:
            raise ModelUnavailable(
                "我还没接上真正的大脑。请右键点我打开设置，"
                "在本机配置 API 地址、密钥和模型。"
            )
        base_url, _ = self._api_config()
        options = {"api_key": api_key}
        if base_url:
            options["base_url"] = base_url
        options["timeout"] = 60.0
        return OpenAI(**options)

    @staticmethod
    def _collect_chat_stream(stream):
        parts = []
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None) if delta is not None else None
            if isinstance(content, str):
                parts.append(content)
        text = "".join(parts).strip()
        if not text:
            raise ModelUnavailable("模型服务返回了流式响应，但其中没有可读取的文本。")
        return text

    @staticmethod
    def _safe_api_error(error):
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None) or getattr(error, "status_code", None)
        headers = getattr(response, "headers", {}) or {}
        content_type = headers.get("content-type", "") if hasattr(headers, "get") else ""
        details = []
        if status:
            details.append(f"HTTP {status}")
        if content_type:
            details.append(f"Content-Type: {content_type.split(';', 1)[0]}")
        if details:
            return "，".join(details)
        return str(error)

    def chat(self, messages, context=None):
        client = self._client()
        model = os.environ.get("YAYAN_LLM_MODEL") or self.settings.get("llm_model")
        if not model:
            raise ModelUnavailable("请在 YAYAN_LLM_MODEL 中指定要使用的模型。")

        context_text = json.dumps(context or {}, ensure_ascii=False, indent=2)
        instructions = f"{self.persona}\n\n## 当前明确上下文\n{context_text}"
        trimmed = select_recent_messages(messages)
        _, api_mode = self._api_config()

        if api_mode == "chat":
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": instructions}, *trimmed],
                    stream=True,
                )
                return self._collect_chat_stream(stream)
            except ModelUnavailable:
                raise
            except Exception as error:
                raise ModelUnavailable(
                    f"Chat Completions 流式请求失败：{self._safe_api_error(error)}"
                ) from error

        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=trimmed,
            store=False,
            max_output_tokens=500,
        )
        return response.output_text.strip()

    def stream_chat(self, messages, context=None, on_delta=None, should_cancel=None):
        """Stream plain-text chat deltas and return the completed response."""
        client = self._client()
        model = os.environ.get("YAYAN_LLM_MODEL") or self.settings.get("llm_model")
        if not model:
            raise ModelUnavailable("请在 YAYAN_LLM_MODEL 中指定要使用的模型。")

        context_text = json.dumps(context or {}, ensure_ascii=False, indent=2)
        instructions = f"{self.persona}\n\n## 当前明确上下文\n{context_text}"
        trimmed = select_recent_messages(messages)
        _, api_mode = self._api_config()
        parts = []
        callback = on_delta or (lambda _text: None)
        cancelled = should_cancel or (lambda: False)
        try:
            if api_mode == "chat":
                stream = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": instructions}, *trimmed],
                    stream=True,
                )
            else:
                stream = client.responses.create(
                    model=model,
                    instructions=instructions,
                    input=trimmed,
                    store=False,
                    max_output_tokens=500,
                    stream=True,
                )
            for event in stream:
                if cancelled():
                    raise ChatCancelled("".join(parts))
                delta = extract_delta(event, api_mode)
                if not delta:
                    continue
                parts.append(delta)
                callback(delta)
        except ChatCancelled:
            raise
        except ModelUnavailable:
            raise
        except Exception as error:
            raise ModelUnavailable(
                f"{api_mode} 流式请求失败：{self._safe_api_error(error)}"
            ) from error

        text = "".join(parts).strip()
        if not text:
            raise ModelUnavailable("模型服务返回了流式响应，但其中没有可读取的文本。")
        return text

    def synthesize(self, text, output_path):
        client = self._client()
        model = os.environ.get("YAYAN_TTS_MODEL") or self.settings.get("tts_model")
        voice = os.environ.get("YAYAN_TTS_VOICE") or self.settings.get("tts_voice", "shimmer")
        try:
            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format="wav",
                speed=1.06,
                instructions=(
                    "用明亮、自然、活泼、可爱的年轻童声感普通话表达。"
                    "不要夹嗓，不要故意奶声奶气，不模仿任何具体儿童。"
                    "语气像一只聪明的小动物朋友，轻快但不吵。"
                ),
            )
        except Exception as error:
            raise ModelUnavailable(
                f"语音合成服务不可用：{self._safe_api_error(error)}"
            ) from error
        Path(output_path).write_bytes(response.content)
        return str(output_path)

    def transcribe(self, audio_path):
        client = self._client()
        model = os.environ.get("YAYAN_STT_MODEL") or self.settings.get("stt_model")
        try:
            with Path(audio_path).open("rb") as audio:
                response = client.audio.transcriptions.create(
                    model=model,
                    file=audio,
                    language="zh",
                )
        except Exception as error:
            raise ModelUnavailable(
                f"语音识别服务不可用：{self._safe_api_error(error)}"
            ) from error
        return getattr(response, "text", str(response)).strip()
