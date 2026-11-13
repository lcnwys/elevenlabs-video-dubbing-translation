# ElevenLabs Video Dubbing & Translation

**Give a motion-comic scene its first voice in another language.**

English · [简体中文](README.zh-CN.md) · Built with ElevenLabs Dubbing v2 + FFmpeg

PanelDub is a locally hosted video translation and dubbing workflow: upload a clip, choose a language, wait for the dub, then preview and download video, audio, and subtitles. Make a reviewable multilingual pilot before committing to a larger localization workflow.

## Why creators might use it

| Scenario | Outcome |
|---|---|
| Motion comics / animated panels | A target-language dub to listen to and review |
| Short dramas / narrative clips | A short pilot to evaluate language and performance |
| Tutorials / product films | Bring existing visuals to an audience in another language |
| Localization prototyping | Explore upload, transcription, language jobs, downloads, and local rendering |

This does not alter lip movements or guarantee release-ready translation, character performance, or subtitle timing. Native-language review and listening checks remain part of publishing.

## Features & deliverables

- MP4 / MOV / MKV / WebM input with an audio track.
- Dubbing v2 project creation with the first target language queued immediately, followed by status polling.
- FLAC dub download; WebVTT when returned upstream, plus SRT conversion with FFmpeg.
- Original visual content composited with the new audio into MP4, with optional burned-in subtitles.
- Local job persistence and a resume-query action that reuses an existing upstream project.
- `DEMO_MODE=true` for local workflow checks; it generates a test tone, not a translation.

| Output | Description |
|---|---|
| MP4 | H.264 video with dubbed audio and optional burned-in subtitles |
| FLAC | Upstream-generated dub |
| VTT / SRT | Available only when the upstream service returns subtitles |

> The application UI is currently primarily in Chinese; this README provides English setup and workflow instructions.

## Stack & requirements

| Layer | Implementation |
|---|---|
| Frontend | Single-file HTML / CSS / JavaScript |
| Backend | Python, FastAPI, Uvicorn, Pydantic |
| API client | Requests → ElevenLabs Dubbing v2 |
| Configuration | python-dotenv and process environment |
| Media | FFmpeg / ffprobe; `libx264` and `libass` for subtitle burning |
| Jobs & state | Local `data/` JSON/files, in-process thread pool, polling; no external database |
| Recommended setup | Python 3.11 / 3.12, FFmpeg, desktop browser; macOS / Linux / Windows |

## Quick start

Download or clone the repository and enter its root, containing `app.py` and `requirements.txt`. The existing folder is named `elevenlabs-dubbing-demo`.

### Install dependencies

Use Python **3.11 or 3.12** and a separate virtual environment for this project. This is a Python application: **Node.js, npm, and an external database are not required**. Use a recent Chrome, Edge, Firefox, or Safari; media decoding depends on the browser.

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` directly and use that Python executable for subsequent commands.

Install FFmpeg, for example:

```bash
# macOS with Homebrew
brew install ffmpeg
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install ffmpeg
```

On Windows, install FFmpeg and add its `bin` directory to PATH. Open a new terminal and check:

```bash
ffmpeg -version
ffprobe -version
```

### Start with the API-free simulation

Copy the configuration: `cp .env.example .env` on macOS / Linux, or `Copy-Item .env.example .env` in PowerShell. Edit your local `.env`:

```dotenv
ELEVENLABS_API_KEY=
DEMO_MODE=true
```

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** and upload a 3–10 second video with audio. Simulation checks upload, progress, subtitles, and MP4 download; the output sound is a test tone.

### Switch to real dubbing

```dotenv
ELEVENLABS_API_KEY=<your-elevenlabs-api-key>
DEMO_MODE=false
```

Restart the service after saving. Your account needs Dubbing access and sufficient quota. Existing environment variables take precedence over `.env`.

1. Upload footage, select a source language or automatic detection, and choose one target language.
2. Create the job and wait for source transcription and target-language generation.
3. Preview dialogue, voices, and subtitles before downloading deliverables.
4. After a query timeout, resume querying before creating another paid project.

**Creating a Dubbing project incurs a minimum charge for one language, potentially before an output exists.** It covers the first language target; additional languages are billed separately. Account terms and official rules apply. See the [official project-creation documentation](https://elevenlabs.io/docs/api-reference/dubbing/create-project).

## Configuration

| Variable | Default / purpose |
|---|---|
| `ELEVENLABS_API_KEY` | Authentication for real dubbing |
| `DEMO_MODE` | `false`; set `true` for local simulation |
| `DATA_DIR` | Repository `data/` by default; inputs, state, outputs |
| `MAX_UPLOAD_MB` | `200`, local upload limit |
| `MAX_DURATION_SEC` | `600`, local duration limit |
| `POLL_SECONDS` | `5`, polling interval, minimum 2 seconds |
| `POLL_TIMEOUT_SEC` | `1800`, query wait limit, minimum 60 seconds |
| `ALLOWED_OUTPUT_HOSTS` | `storage.googleapis.com`; verify any change to the download-host allowlist |

The UI offers Chinese, English, Japanese, Korean, Spanish, French, German, Portuguese, Italian, Indonesian, Thai, and Vietnamese. Listed options do not establish verified support for every account or language pair; validate with a pilot.

## Data & production limits

| Stage | Current behavior |
|---|---|
| Upload to local service | Source saved under Git-ignored `data/` |
| Real dubbing project | Source video and language settings sent to ElevenLabs |
| API key | Read on the backend; authentication headers sent to ElevenLabs API only |
| Audio / subtitle download | Retrieved from upstream allowlisted URLs without attaching the API key |
| Local output | FFmpeg renders and saves files; jobs are not automatically expired |

**The entire original audio track is replaced, including existing music and sound effects.** Preserving background material requires a separate separation/remixing workflow. H.264 output preserves visual content but is re-encoded, not bit-for-bit lossless. Subtitles may follow the source speech timeline and drift against translated delivery; if upstream provides none, the application warns and delivers video without subtitles.

There is no automatic lip sync, subtitle editor, cloning interface, multi-user login, or production queue. No separate telemetry-upload code is included, but online dubbing uploads content and does not guarantee upstream zero retention. Use authorized media and verify commercial rights under the applicable terms.

## Development & diagnostics

| Path | Role |
|---|---|
| `app.py` | Project creation, polling, download validation, rendering, and state |
| `static/index.html` | Upload, progress, preview, and download UI |
| `.env.example` | Public configuration template without real keys |
| `tests/test_demo.py` | Mocked service calls and locally generated media checks |

Developer checks: `DEMO_MODE=true python -m pytest -q`. In PowerShell set `$env:DEMO_MODE="true"` first, then run `python -m pytest -q`. If pytest is not installed in the test environment, install it with `python -m pip install pytest`. Tests do not require paid API requests.

If a request times out before the upstream project ID is saved, inspect the ElevenLabs account before retrying creation to avoid duplicate charges. For subtitle burn-in errors, check the FFmpeg `subtitles` filter and font availability.

## References

- [Dubbing v2 project creation](https://elevenlabs.io/docs/api-reference/dubbing/create-project)
- [Dubbing project status](https://elevenlabs.io/docs/api-reference/dubbing/get-project)
- [Dubbing target-language status](https://elevenlabs.io/docs/api-reference/dubbing/language-targets/get-language-target)
- [FFmpeg documentation](https://ffmpeg.org/documentation.html)

## Local deployment & development

The commands above start a **single-user service on your own machine**. Leave the terminal running and press `Ctrl+C` to stop it. To restart, enter the same directory, activate the same environment, and run the start command again. If another project uses the port, stop it or choose a different `--port`.

A process manager can keep the same Uvicorn command running. Before offering this service to a team or the public, add authentication, user isolation, a job queue, usage limits, redacted logs, and file cleanup. These production deployment features are not implemented here.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Missing `uvicorn` or Python module | Activate the virtual environment; run `python -m pip install -r requirements.txt` from the project root |
| FFmpeg missing / media probe fails | Check `ffmpeg -version` and `ffprobe -version`; reopen the terminal after installation |
| API returns 401 / 403 | Check the local key, product permissions, and account status; never paste a full key into an issue |
| API returns 429 / generation times out | Check quota, concurrency, and network access; start with a short clip and inspect upstream job state before resubmitting |
| Preview does not play | Check browser codec support; download the result and try a local player |
| Environment changes do not take effect | Restart Uvicorn from the terminal where the variables are configured |

## Contributing

Reproduction steps, sanitized errors, and feature suggestions are welcome. A concrete case—music masking comic dialogue, subtitle drift after dubbing, or an unsuitable musical mood—is especially useful. Include OS, Python / FFmpeg versions, media format, and a minimal workflow. Confirm sharing rights before providing real media.

Code is provided under the [MIT License](LICENSE). API terms, generated-content rights, media-asset rights, and dependency licenses apply separately.

## ElevenLabs integration & pricing inquiries

Maintained by an independent developer, this project gives motion-comic teams, video creators, and builders a practical way to explore ElevenLabs.

Working on **motion-comic dubbing, short-drama localization, video soundtracks, sound effects, voice products, or batch API integration**? Get in touch to discuss product fit, workflow design, and integration. I can also offer **competitively priced ElevenLabs solutions**; availability, terms, and pricing depend on your requirements and an individual quotation.

**Email: [lcnwys@gmail.com](mailto:lcnwys@gmail.com)**

For a useful first conversation, include:

- Your content or product type and a short, sanitized description of the requirement.
- Estimated monthly audio/video minutes, target languages, team size, and API needs.
- Whether you are testing a pilot or preparing a launch.

Do not send API keys, passwords, or unauthorized customer media by email or in public issues. Use issues for product feedback and email for commercial inquiries.

> An independent community project, not an official ElevenLabs product. Inquiries and quotations do not imply official endorsement. ElevenLabs names and trademarks belong to their respective owners.
