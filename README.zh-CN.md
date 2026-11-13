# ElevenLabs-Video-Dubbing-Translation

**让一段漫剧，拥有走向另一种语言的第一版配音。**

[English](README.md) · 简体中文 · 基于 ElevenLabs Dubbing v2 + FFmpeg

PanelDub 是本地运行的视频翻译配音工作流：上传片段、选择语言、等待配音，然后预览并下载视频、音频和字幕。适合先做一个可评审的多语言样片，再决定后续制作与出海流程。

## 为创作者解决什么问题

| 创作场景 | 可以获得什么 |
|---|---|
| 漫剧 / 动态漫画出海 | 一个可试听、可复核的目标语言配音版本 |
| 短剧 / 剧情短视频 | 先用短片段验证语言与配音方向 |
| 教程 / 产品展示 | 把同一段画面交给另一种语言的观众 |
| 译配流程研发 | 理解上传、转录、目标语言任务、音频下载与本地合成如何连接 |

它不自动改口型，也不保证翻译、角色演绎或字幕时间轴达到发行标准。发布前仍需要母语审校和实际试听。

## 功能与交付

- 支持 MP4 / MOV / MKV / WebM，输入需含音轨。
- 创建 Dubbing v2 项目时直接排队首个目标语言，轮询项目和配音状态。
- 下载配音 FLAC；上游返回字幕时提供 WebVTT，并用 FFmpeg 转换 SRT。
- 保留原视频画面内容，用新音轨合成 MP4，可选把字幕烧录进视频。
- 任务状态保存在本地；中断后可用“继续查询”复用已有上游项目。
- 可用 `DEMO_MODE=true` 验证本地流程，模拟音轨是提示音，不是真实翻译。

| 输出 | 说明 |
|---|---|
| MP4 | H.264 视频 + 配音音轨，可选烧录字幕 |
| FLAC | 上游生成的配音音频 |
| VTT / SRT | 仅在上游实际返回字幕时提供 |

界面目前以中文为主；本仓库提供中英文文档，尚未提供完整英文界面。

## 技术栈与配套环境

| 层 | 实现 |
|---|---|
| 前端 | 单文件 HTML / CSS / JavaScript |
| 后端 | Python、FastAPI、Uvicorn、Pydantic |
| 外部请求 | Requests → ElevenLabs Dubbing v2 |
| 配置 | python-dotenv + 进程环境变量 |
| 媒体 | FFmpeg / ffprobe，需 `libx264` 与字幕烧录用的 `libass` |
| 状态与任务 | 本地 `data/` JSON / 文件、进程内线程池和轮询；无外部数据库 |
| 推荐环境 | Python 3.11 / 3.12、FFmpeg、桌面浏览器；macOS / Linux / Windows |

## 快速开始

下载或克隆仓库，进入含 `app.py`、`requirements.txt` 的根目录。现有文件夹名称为 `elevenlabs-dubbing-demo`。

### 安装依赖

建议 Python **3.11 或 3.12**，并为每个项目单独建立虚拟环境。本项目是 Python 应用，**不需要 Node.js、npm 或独立数据库**。建议使用较新的 Chrome、Edge、Firefox 或 Safari；实际媒体解码能力取决于浏览器。

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果 PowerShell 的执行策略不允许激活，可直接使用 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`，后续启动命令也使用该 Python 路径。

FFmpeg 安装示例：

```bash
# macOS（已安装 Homebrew）
brew install ffmpeg
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install ffmpeg
```

Windows 请安装 FFmpeg 并将其 `bin` 目录加入 PATH。新开终端后确认：

```bash
ffmpeg -version
ffprobe -version
```

### 先跑不消耗 API 的模拟模式

复制示例配置：macOS / Linux 使用 `cp .env.example .env`，PowerShell 使用 `Copy-Item .env.example .env`。编辑本机 `.env`：

```dotenv
ELEVENLABS_API_KEY=
DEMO_MODE=true
```

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

打开 **http://127.0.0.1:8000**，上传一段 3–10 秒、有音轨的视频。模拟模式用于检查上传、状态更新、字幕烧录和 MP4 下载；声音为测试提示音。

### 切换真实配音

```dotenv
ELEVENLABS_API_KEY=<your-elevenlabs-api-key>
DEMO_MODE=false
```

保存后重启服务。账号需有 Dubbing 权限和可用额度。已有终端环境变量会优先于 `.env`。

1. 上传视频，选择原语言或自动检测，以及一个目标语言。
2. 创建任务并等待源视频转录和目标语言配音完成。
3. 预览、检查台词、音色和字幕，再下载交付物。
4. 查询超时先用“继续查询”，避免重复创建付费项目。

**创建 Dubbing 项目即产生至少一种语言的最低收费，可能在输出产生之前发生。**首个目标语言由该费用覆盖，额外语言单独计费，实际以账号和官方规则为准。参见 [官方创建项目说明](https://elevenlabs.io/docs/api-reference/dubbing/create-project)。

## 配置项

| 变量 | 默认值 / 用途 |
|---|---|
| `ELEVENLABS_API_KEY` | 真实模式认证 Key |
| `DEMO_MODE` | `false`；设 `true` 使用本地模拟 |
| `DATA_DIR` | 默认项目根目录 `data/`，保存输入、状态与输出 |
| `MAX_UPLOAD_MB` | `200`，本地上传大小限制 |
| `MAX_DURATION_SEC` | `600`，本地素材时长限制 |
| `POLL_SECONDS` | `5`，轮询间隔，最小 2 秒 |
| `POLL_TIMEOUT_SEC` | `1800`，查询等待上限，最小 60 秒 |
| `ALLOWED_OUTPUT_HOSTS` | `storage.googleapis.com`，下载输出的主机白名单；变更前需核实 |

当前界面提供中文、英语、日语、韩语、西班牙语、法语、德语、葡萄牙语、意大利语、印尼语、泰语、越南语选项。界面列出语言不代表你的账号对所有组合都已验收，真实支持仍需用样片检查。

## 数据与制作边界

| 环节 | 当前行为 |
|---|---|
| 上传到本地服务 | 源视频写入 `data/`，Git 已忽略该目录 |
| 创建真实配音 | 源视频及语言参数发送给 ElevenLabs |
| API Key | 后端读取本机配置，仅向 ElevenLabs API 发送认证头 |
| 下载配音 / 字幕 | 从上游返回的白名单地址下载，不向下载地址附带 API Key |
| 本地输出 | FFmpeg 合成并保存；任务没有自动过期清理 |

**原始音轨会被整条替换，包括其中的音乐和音效。**需要保留背景时，应另建音频分离与重混流程。输出视频默认 H.264 重编码，画面内容保留，但不是逐位无损。字幕可能基于源语音时间轴，目标配音速度变化时需要人工检查；上游没有字幕时会交付无字幕视频并提示。

没有自动口型同步、字幕编辑器、声音克隆界面、多用户账号或生产级队列。代码没有独立遥测上报，但在线配音会上传内容，也不承诺上游零留存。请只处理获得授权的音视频；生成内容商用权限以实际授权和服务条款为准。

## 开发与排障

| 路径 | 职责 |
|---|---|
| `app.py` | 项目创建、轮询、下载校验、FFmpeg 合成、任务状态 |
| `static/index.html` | 上传、状态、预览与下载 UI |
| `.env.example` | 可公开的配置模板，不含真实 Key |
| `tests/test_demo.py` | 使用模拟接口与本地生成素材的流程测试 |

开发检查：`DEMO_MODE=true python -m pytest -q`。Windows 可先设 `$env:DEMO_MODE="true"` 再执行 `python -m pytest -q`。如果测试环境尚未安装 pytest，先在虚拟环境中执行 `python -m pip install pytest`；测试不需要付费 API。

若上游超时且本地尚未保存项目 ID，先核对 ElevenLabs 后台再重建，避免重复收费。烧录字幕失败时检查 FFmpeg 是否包含 `subtitles` 滤镜及字体支持。

## 参考

- [Dubbing v2 创建项目](https://elevenlabs.io/docs/api-reference/dubbing/create-project)
- [Dubbing 项目状态](https://elevenlabs.io/docs/api-reference/dubbing/get-project)
- [Dubbing 目标语言状态](https://elevenlabs.io/docs/api-reference/dubbing/language-targets/get-language-target)
- [FFmpeg 文档](https://ffmpeg.org/documentation.html)

## 本地部署与二次开发

以上命令启动的是**本机单用户服务**。终端保持运行即可使用，按 `Ctrl+C` 停止；重启时进入同一目录，激活同一虚拟环境，再执行启动命令。不同项目使用相同端口时，请停止前一个服务，或把 `--port` 改为未占用端口。

如需让服务长期运行，可由进程管理器管理同一条 Uvicorn 命令。正式向团队或公网提供服务之前，需要增加身份认证、用户数据隔离、任务队列、用量限制、日志脱敏和文件清理。当前仓库没有实现这些生产部署能力。

## 常见问题

| 问题 | 排查方向 |
|---|---|
| 找不到 `uvicorn` 或模块 | 确认已激活虚拟环境，并在项目根目录执行 `python -m pip install -r requirements.txt` |
| 找不到 FFmpeg / 无法读取媒体 | 检查 `ffmpeg -version`、`ffprobe -version`，安装后重启终端 |
| API 提示 401 / 403 | 检查本机 Key、对应产品权限和账号状态；不要把完整 Key 发到 Issue |
| API 提示 429 / 生成超时 | 检查额度、并发与网络；先用短素材验证，确认上游任务状态后再决定是否重新提交 |
| 浏览器无法播放 | 检查浏览器支持的封装与编码；可以下载到本地播放器检查 |
| 修改环境变量后仍未生效 | 在配置所在终端重启 Uvicorn |

## 参与改进

欢迎提交复现步骤、已脱敏报错和功能建议。漫剧对白被音乐遮住、译配字幕偏移、音乐情绪不匹配等具体场景，比单纯写“效果不好”更有帮助。请写明系统、Python / FFmpeg 版本、输入格式和最短复现流程；真实素材请先确认分享权限。

代码采用 [MIT License](LICENSE)。API 使用、生成内容、音视频素材与依赖软件的授权另行适用。

## ElevenLabs 接入与价格咨询

这个项目由独立开发者维护，希望用一个能实际操作的小工具，帮助漫剧团队、视频创作者和产品开发者理解 ElevenLabs 的能力。

如果你正在做**漫剧配音、短剧出海、视频配乐、音效制作、语音产品或批量 API 集成**，欢迎联系我，一起评估适合的产品、工作流和接入方式。我也可以提供**有价格优势的 ElevenLabs 方案报价**，具体方案、适用条件和价格以实际需求及单独报价为准。

**咨询邮箱：[lcnwys@gmail.com](mailto:lcnwys@gmail.com)**

为了更快给出建议，邮件中可以写明：

- 你在做什么内容或产品，以及一段已脱敏的需求说明。
- 每月预计视频/音频分钟数、目标语言、团队规模和是否需要 API。
- 希望先做样片验证，还是正在准备上线。

请不要在邮件或公开 Issue 中发送 API Key、账号密码或未获授权的客户素材。功能问题适合提 Issue；商务和价格咨询请发邮件。

> 这是独立社区项目，并非 ElevenLabs 官方产品。咨询和报价也不代表官方背书；ElevenLabs 的名称和商标归其权利人所有。
