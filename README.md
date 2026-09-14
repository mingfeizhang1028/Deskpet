# 芽砚 Yayan

芽砚是一只住在 Windows 桌面角落的水彩狐猫小宠物。它可以自然聊天、记录当前任务和进度，并用温和、不制造压力的方式陪你开始工作。

![芽砚聊天窗口](docs/images/desktop-chat-panel.png)

## 功能

- 透明、无边框、置顶的桌面宠物窗口
- 靠近、触碰、拖动、害羞、思考和开心等动态反馈
- 可调整大小的清新纸感聊天窗口
- OpenAI SDK 兼容的 Responses API 与 Chat Completions 接口
- 支持第三方兼容服务返回的 SSE 流式 Chat Completions
- 当前任务、下一步和进度记录
- 可选语音输入和朗读；文字与语音服务互不影响
- API 密钥保存在 Windows 凭据管理器，不写入仓库

## 系统要求

- Windows 10 或 Windows 11
- Python 3.10 或更高版本
- 麦克风功能需要可用的 QtMultimedia 音频后端

## 安装

在 PowerShell 中进入项目目录，然后执行：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

安装完成后双击 `Start-Yayan.cmd`。右键点击芽砚可以打开设置，设置页底部可以重启或退出；也可以双击 `Stop-Yayan.cmd` 完全退出。

如果启动后没有窗口，请查看 `output/runtime/` 中的启动日志。这个目录只保存本机运行状态，并已被 Git 忽略。

## 配置模型

在芽砚的设置页中填写：

- API 地址：OpenAI 或兼容服务的 API 基础地址
- API 密钥：保存到 Windows 凭据管理器
- 模型名称：使用供应商实际提供的模型名
- 接口类型：`responses` 或 `chat`

也可以使用环境变量：

- `OPENAI_API_KEY`
- `YAYAN_LLM_MODEL`
- `YAYAN_LLM_BASE_URL`
- `YAYAN_API_MODE`

不要把 API 密钥写进 `desktop/settings.json`、代码、Issue 或提交记录。

不同供应商对文字、语音识别和语音合成的支持可能不同。某个地址能聊天，不代表它也提供 Audio API。芽砚会把文字与语音错误分开处理。

## 隐私和权限边界

- 芽砚不会自动读取、修改、移动或删除你的工作文件。
- 默认模型上下文只包含聊天内容和你主动填写的任务状态。
- API 密钥只从环境变量或 Windows 凭据管理器读取。
- 本机设置、日志、录音和任务状态位于 `output/runtime/`，不会进入 Git。
- 模型只能提出建议，不能替用户做决定。

## 验证

安装运行依赖后执行：

```powershell
.\.venv\Scripts\python.exe scripts\verify_desktop.py
```

素材处理工具使用额外依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 项目结构

```text
assets/                  正式宠物素材
desktop/                 PyQt5 桌面程序、模型接入与人设
Start-Yayan.cmd          启动桌面宠物
Stop-Yayan.cmd           安全退出桌面宠物
scripts/                 离线验证和素材处理工具
docs/images/             README 使用的精选截图
legacy/web-prototype/    早期网页原型，不是当前默认产品
```

## 早期网页原型

`legacy/web-prototype/` 保留了最初的浏览器版本。它不需要参与桌面宠物启动；需要查看时，可在该目录中运行本地静态服务器。

## 许可证

本项目采用 [MIT License](LICENSE)。仓库中的角色素材也随本项目一同开放使用；如果素材的原始生成平台对输出另有约束，使用者仍需遵守相应平台条款。
