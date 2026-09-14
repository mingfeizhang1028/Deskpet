import ast
import importlib.machinery
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "desktop"))

from llm_client import ModelUnavailable, YayanLLM  # noqa: E402


def verify_syntax():
    for path in (PROJECT_DIR / "desktop" / "main.pyw", PROJECT_DIR / "desktop" / "llm_client.py"):
        ast.parse(path.read_text(encoding="utf-8"))


def verify_offline_guard():
    previous = os.environ.pop("OPENAI_API_KEY", None)
    previous_store = os.environ.get("YAYAN_DISABLE_CREDENTIAL_STORE")
    os.environ["YAYAN_DISABLE_CREDENTIAL_STORE"] = "1"
    try:
        client = YayanLLM(PROJECT_DIR)
        try:
            client.chat([{"role": "user", "content": "你好"}])
        except ModelUnavailable:
            return True
        return False
    finally:
        if previous_store is None:
            os.environ.pop("YAYAN_DISABLE_CREDENTIAL_STORE", None)
        else:
            os.environ["YAYAN_DISABLE_CREDENTIAL_STORE"] = previous_store
        if previous is not None:
            os.environ["OPENAI_API_KEY"] = previous


def inspect_preview(name):
    image = Image.open(PROJECT_DIR / "output" / "playwright" / name).convert("RGBA")
    alpha = image.getchannel("A")
    values = list(alpha.getdata())
    return {
        "size": image.size,
        "corner_alpha": alpha.getpixel((0, 0)),
        "content_bbox": alpha.getbbox(),
        "nontransparent_coverage": round(sum(value > 0 for value in values) / len(values), 3),
    }


def verify_asset_transparency():
    image = Image.open(PROJECT_DIR / "assets" / "yayan-watercolor-base.png").convert("RGBA")
    alpha = image.getchannel("A")
    return {
        "size": image.size,
        "corner_alpha": alpha.getpixel((0, 0)),
        "content_bbox": alpha.getbbox(),
    }


def verify_pet_interaction():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication

    module = importlib.machinery.SourceFileLoader(
        "yayan_desktop_verify", str(PROJECT_DIR / "desktop" / "main.pyw")
    ).load_module()
    app = QApplication.instance() or QApplication([])
    pet = module.PetWindow("watercolor")
    actions = []
    pet.action_requested.connect(actions.append)
    pet.show()
    app.processEvents()
    QTest.mouseClick(pet, Qt.LeftButton, pos=QPoint(162, 190))
    app.processEvents()
    left_click_opens_chat = actions == ["chat"] and not pet.menu_visible
    QTest.mouseClick(pet, Qt.RightButton, pos=QPoint(162, 190))
    app.processEvents()
    right_click_opens_settings = actions[-1] == "settings"
    chat = module.ChatPanel()
    chat.add_message("你", "我今天有点不想工作。")
    chat.add_message(
        "芽砚",
        "（尾巴轻轻扫过桌角，挨近一点）那先不催你。我们只挑一件最小的事，做十分钟，好不好？",
        is_pet=True,
    )
    chat.add_message("你", "那就先把方案的开头写出来。")
    chat.add_message(
        "芽砚",
        "好呀，我帮你记住：现在只写方案开头，不管后面的。写完来碰一下我。",
        is_pet=True,
    )
    chat.show()
    app.processEvents()
    scroll_bar = chat.log.verticalScrollBar()
    auto_scroll_latest = scroll_bar.value() == scroll_bar.maximum()

    default_size = (chat.width(), chat.height())
    default_body_size = chat.rendered_bodies[0].font().pixelSize()
    default_bubble_width = max(bubble.width() for bubble in chat.rendered_bubbles)
    chat.resize(360, 520)
    app.processEvents()
    small_body_size = chat.rendered_bodies[0].font().pixelSize()
    small_bubble_width = max(bubble.width() for bubble in chat.rendered_bubbles)
    chat.resize(450, 660)
    app.processEvents()
    large_body_size = chat.rendered_bodies[0].font().pixelSize()
    large_bubble_width = max(bubble.width() for bubble in chat.rendered_bubbles)
    chat.resize(390, 570)
    app.processEvents()

    scroll_bar.setValue(scroll_bar.minimum())
    app.processEvents()
    chat_preview = PROJECT_DIR / "output" / "playwright" / "desktop-chat-panel.png"
    chat_preview.parent.mkdir(parents=True, exist_ok=True)
    chat.grab().save(str(chat_preview))
    chat.add_message("你", "<测试>\n第二行")
    app.processEvents()
    message_texts = [label.text() for label in chat.rendered_bodies]
    chat_design = {
        "panel_object_name": chat.objectName() == "chatPanel",
        "default_page_ratio": default_size == (390, 570),
        "font_family": chat.font().family() == "Microsoft YaHei UI",
        "default_body_size": default_body_size == 14,
        "responsive_font_size": small_body_size < default_body_size < large_body_size,
        "responsive_bubble_width": small_bubble_width
        < default_bubble_width
        < large_bubble_width,
        "message_font_family": all(
            label.font().family() == "Microsoft YaHei UI" for label in chat.rendered_bodies
        ),
        "safe_message_rendering": "<测试>\n第二行" in message_texts,
        "message_hierarchy": len(chat.rendered_bubbles) == 5,
        "stage_hierarchy": len(chat.rendered_stages) == 1,
        "auto_scroll_latest": auto_scroll_latest,
        "unified_composer": chat.input.objectName() == "chatInput"
        and chat.send_button.objectName() == "chatSend",
        "preview_written": chat_preview.exists() and chat_preview.stat().st_size > 0,
    }
    chat.set_busy(True)
    chat_design["busy_state"] = not chat.input.isEnabled() and not chat.send_button.isEnabled()
    chat.set_busy(False)
    chat_design["ready_state"] = chat.input.isEnabled() and chat.send_button.isEnabled()
    voice_input_default_hidden = chat.mic.isHidden()
    chat.set_voice_input_enabled(True)
    voice_input_can_enable = not chat.mic.isHidden() and chat.mic.isEnabled()
    chat.set_voice_input_enabled(False)
    voice_input_can_disable = chat.mic.isHidden() and not chat.mic.isEnabled()
    always_on_top = bool(pet.windowFlags() & Qt.WindowStaysOnTopHint)
    translucent = pet.testAttribute(Qt.WA_TranslucentBackground)
    chat.close()
    pet.close()
    return {
        "left_click_opens_chat": left_click_opens_chat,
        "right_click_opens_settings": right_click_opens_settings,
        "voice_input_default_hidden": voice_input_default_hidden,
        "voice_input_can_enable": voice_input_can_enable,
        "voice_input_can_disable": voice_input_can_disable,
        "chat_design": chat_design,
        "always_on_top": always_on_top,
        "translucent_background": translucent,
    }


def verify_tool_window_lifecycle():
    source = (PROJECT_DIR / "desktop" / "main.pyw").read_text(encoding="utf-8")
    return "app.setQuitOnLastWindowClosed(False)" in source


def verify_forced_sse_chat():
    stream = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="你"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="好呀"))]),
    ]
    return YayanLLM._collect_chat_stream(stream) == "你好呀"


def verify_restart_controls():
    source = (PROJECT_DIR / "desktop" / "main.pyw").read_text(encoding="utf-8")
    required = (
        'restart = QPushButton("重启芽砚")',
        'quit_button = QPushButton("退出芽砚")',
        '"--restart-delay"',
        "QProcess.startDetached",
    )
    return all(item in source for item in required)


def verify_audio_failure_routing():
    source = (PROJECT_DIR / "desktop" / "main.pyw").read_text(encoding="utf-8")
    required = (
        'elif mode == "tts":',
        'self.client.save_user_settings({"speak_replies": False})',
        'self.chat_panel.mic.setText("语音暂不可用")',
    )
    return all(item in source for item in required)


def verify_voice_input_setting():
    main_source = (PROJECT_DIR / "desktop" / "main.pyw").read_text(encoding="utf-8")
    client_source = (PROJECT_DIR / "desktop" / "llm_client.py").read_text(encoding="utf-8")
    defaults = json.loads((PROJECT_DIR / "desktop" / "settings.json").read_text(encoding="utf-8"))
    required = (
        'QCheckBox("在聊天窗显示“按住说话”按钮")' in main_source,
        'settings.get("voice_input_enabled", False)' in main_source,
        '"voice_input_enabled"' in client_source,
        defaults.get("voice_input_enabled") is False,
    )
    return all(required)


def verify_safe_audio_error():
    class FakeResponse:
        status_code = 404
        headers = {"content-type": "application/json; charset=utf-8"}

    class FakeError(Exception):
        response = FakeResponse()

    class FakeSpeech:
        @staticmethod
        def create(**_kwargs):
            raise FakeError("secret provider response")

    class FakeAudio:
        speech = FakeSpeech()

    class FakeClient:
        audio = FakeAudio()

    client = YayanLLM(PROJECT_DIR)
    client._client = lambda: FakeClient()
    try:
        client.synthesize("你好", PROJECT_DIR / "output" / "runtime" / "unused.wav")
    except ModelUnavailable as error:
        message = str(error)
        return (
            "语音合成服务不可用" in message
            and "HTTP 404" in message
            and "application/json" in message
            and "secret provider response" not in message
        )
    return False


def main():
    verify_syntax()
    result = {
        "syntax": "ok",
        "offline_guard": verify_offline_guard(),
        "tool_window_lifecycle": verify_tool_window_lifecycle(),
        "forced_sse_chat": verify_forced_sse_chat(),
        "restart_controls": verify_restart_controls(),
        "audio_failure_routing": verify_audio_failure_routing(),
        "voice_input_setting": verify_voice_input_setting(),
        "safe_audio_error": verify_safe_audio_error(),
        "pet_interaction": verify_pet_interaction(),
        "asset": verify_asset_transparency(),
    }
    print(json.dumps(result, ensure_ascii=True, indent=2))
    if not result["offline_guard"]:
        raise SystemExit(1)
    if not result["tool_window_lifecycle"]:
        raise SystemExit(1)
    if not result["forced_sse_chat"]:
        raise SystemExit(1)
    if not result["restart_controls"]:
        raise SystemExit(1)
    if not result["audio_failure_routing"]:
        raise SystemExit(1)
    if not result["voice_input_setting"]:
        raise SystemExit(1)
    if not result["safe_audio_error"]:
        raise SystemExit(1)
    if result["asset"]["corner_alpha"] != 0 or not result["asset"]["content_bbox"]:
        raise SystemExit(1)
    interaction = result["pet_interaction"]
    chat_design = interaction["chat_design"]
    interaction_checks = {
        key: value for key, value in interaction.items() if key != "chat_design"
    }
    if not all(interaction_checks.values()) or not all(chat_design.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
