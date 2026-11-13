# ElevenLabs Dubbing v2 + FFmpeg 视频翻译配音 Demo

面向短视频、漫剧、常规视频的**独立、单机** Web Demo。后端 Python FastAPI，前端单文件 HTML，视频合成使用 FFmpeg。

## 支持能力

- 上传 MP4 / MOV / MKV / WebM（文件需要有音轨），选择原语言和翻译目标语言
- 创建 **Dubbing v2** 项目并直接排队首个目标语言（避免重复支付首个目标语言费用）
- 查询项目转录状态及目标语言配音状态（轮询，Demo 不需要 webhook）
- 下载上游的配音 FLAC 和 WebVTT；本地将 WebVTT 转成 SRT
- 保留**源视频画面**，将配音音轨与视频合成；可选将字幕直接烧录到 MP4
- MP4 预览、MP4 / FLAC / VTT / SRT 下载、失败提示、状态持久化
- 中断后通过“继续查询”复用**已有**上游项目，避免因为重新上传重复收费
- 本地模拟模式可以在**不消耗 ElevenLabs 费用**的情况下验证 FFmpeg 全流程（模拟音轨是提示音，不是翻译配音）

## 运行环境

- Python 3.10+
- `ffmpeg` 和 `ffprobe` 在系统 PATH 中，FFmpeg 需要 `libx264` 和 `libass`（字幕滤镜）
- ElevenLabs API Key（真实模式；具有 Dubbing 调用权限、足够额度）

安装（macOS：`brew install ffmpeg`；Ubuntu：`sudo apt-get install ffmpeg`）：

```bash
cd elevenlabs-dubbing-demo
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中填写：

```dotenv
ELEVENLABS_API_KEY=你的密钥
DEMO_MODE=false
```

启动：

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000`。**不要将此无登录鉴权的本地 Demo 直接对公网开放。**

不想先消费 API 时，设置 `DEMO_MODE=true` 后重启服务，用一个 3–10 秒有音轨的短视频验证 UI、字幕烧录和交付流程。模拟生成的是测试音，不是翻译结果，界面会明确提示。

## 真实流程

1. `POST /v1/dubbing/project`：文件上传，`model_id=dubbing_v2`，`target_language=en`，可选 `source_language`。**创建项目即可能收取至少一个目标语言的费用**。
2. `GET /v1/dubbing/project/{project_id}`：轮询源视频转录状态，直到 `ready`（或 `failed`）。
3. `GET /v1/dubbing/project/{project_id}/language/{language_id}`：轮询目标语言，直至 `completed`；返回 `outputs.lossless_audio` 和可能存在的 `outputs.subtitles`（签名下载 URL）。
4. 下载配音音频与 WebVTT，FFmpeg 将字幕导出 SRT，并将原视频画面与新音轨合成 MP4；可选烧录字幕。
5. 交付视频、音频及字幕。如果上游未返回 `outputs.subtitles`，仍交付**无字幕视频**，并明确警告，不假装字幕已生成。

注意：官网签名文件的主机名通过 `ALLOWED_OUTPUT_HOSTS` 白名单验证，默认 `storage.googleapis.com`；如果官方后续改用其他域名，需核对后更新配置。

## 产品边界与风险

- 视频中的**原始音轨会全部替换**：包括原声对话、背景音乐与音效。若奇想希望保留背景音乐和音效，需要另外增加音频分离、轨道混音，不建议简单叠加两套声音。
- 默认用 H.264 重新编码输出视频（`libx264`），画面内容来自原视频，但不是逐位无损。默认字幕样式可在 `render_outputs()` 调整。字幕与实际嘴型同步质量需要结合真实样片验证。
- `outputs.subtitles` 是官方返回的 WebVTT，按**源语音时间轴**定时；配音速度变化可能导致字幕和目标语音有偏差，严苛场景可增加 Forced Alignment 或 Scribe。
- 当前最多 200 MB / 600 秒，可在 `.env` 修改。使用本地磁盘保存所有文件，**不自动清理任务**，不适合长视频或高并发生产。
- 真实模式为轮询；正式 SaaS 建议改用 ElevenLabs 签名验证 webhook + 对象存储 + 独立任务队列 + 用户权限/频控 + 自动清理 + 成本计费。
- 本代码没有实现账号共享、API Key 前端输入、客户用量计价；Key 仅在后端 `.env` 保存。
- 创建项目后如果上游超时，先点击“继续查询”；不要直接重新创建项目。未创建上游项目但网络超时的极端情况仍需管理员核对 ElevenLabs 后台，以免重复计费。

## 技术参考（官方）

- [Dubbing v2 Create project](https://elevenlabs.io/docs/api-reference/dubbing/create-project)
- [Get project](https://elevenlabs.io/docs/api-reference/dubbing/get-project)
- [Get language target](https://elevenlabs.io/docs/api-reference/dubbing/language-targets/get-language-target)
- [Dubbing quickstart](https://elevenlabs.io/docs/eleven-api/guides/cookbooks/dubbing)

## 运行测试

```bash
DEMO_MODE=true python -m pytest -q
```

集成测试使用 FFmpeg 自制测试视频，不会调用 ElevenLabs 或消耗额度。
