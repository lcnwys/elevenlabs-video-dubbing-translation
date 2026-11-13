"""Local video dubbing demo: ElevenLabs Dubbing v2 + FFmpeg.

Run with: uvicorn app:app --host 127.0.0.1 --port 8000
This is a local single-process demo, not a public multi-tenant service.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env')
DATA_DIR = Path(os.getenv('DATA_DIR', str(BASE / 'data'))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
API_BASE = 'https://api.elevenlabs.io/v1/dubbing/project'
API_KEY = os.getenv('ELEVENLABS_API_KEY', '').strip()
DEMO_MODE = os.getenv('DEMO_MODE', 'false').strip().lower() == 'true'
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '200'))
MAX_DURATION_SEC = int(os.getenv('MAX_DURATION_SEC', '600'))
POLL_SECONDS = max(2, int(os.getenv('POLL_SECONDS', '5')))
POLL_TIMEOUT_SEC = max(60, int(os.getenv('POLL_TIMEOUT_SEC', '1800')))
ALLOWED_OUTPUT_HOSTS = [x.strip().lower() for x in os.getenv('ALLOWED_OUTPUT_HOSTS', 'storage.googleapis.com').split(',') if x.strip()]
ALLOWED_EXTS = {'.mp4', '.mov', '.mkv', '.webm'}
LANGUAGES = {
    'zh': '中文', 'en': 'English', 'ja': '日本語', 'ko': '한국어',
    'es': 'Español', 'fr': 'Français', 'de': 'Deutsch',
    'pt': 'Português', 'it': 'Italiano', 'id': 'Bahasa Indonesia',
    'th': 'ไทย', 'vi': 'Tiếng Việt',
}
lock = threading.RLock()
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='dub')
app = FastAPI(title='ElevenLabs 视频翻译配音 Demo', version='1.0')


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def job_dir(job_id: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise HTTPException(404, '任务不存在')
    folder = DATA_DIR / job_id
    if not folder.is_dir():
        raise HTTPException(404, '任务不存在')
    return folder


def read_job(job_id: str) -> dict:
    with lock:
        path = job_dir(job_id) / 'job.json'
        if not path.is_file():
            raise HTTPException(404, '任务不存在')
        return json.loads(path.read_text(encoding='utf-8'))


def write_job(job_id: str, **changes) -> dict:
    with lock:
        job = read_job(job_id)
        job.update(changes)
        job['updated_at'] = now()
        path = job_dir(job_id) / 'job.json'
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding='utf-8')
        tmp.replace(path)
        return job


def run_command(cmd: list[str], cwd: Path, timeout: int = 600) -> None:
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('FFmpeg 处理超时') from exc
    if p.returncode:
        raise RuntimeError(f"FFmpeg 错误：{p.stderr[-1200:]}")


def probe_media(path: Path) -> float:
    p = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
        capture_output=True, text=True, timeout=45, check=False,
    )
    if p.returncode:
        raise ValueError('无法读取视频，建议上传 MP4（H.264 + AAC）')
    data = json.loads(p.stdout)
    streams = data.get('streams', [])
    if not any(x.get('codec_type') == 'video' for x in streams):
        raise ValueError('文件中没有视频画面')
    if not any(x.get('codec_type') == 'audio' for x in streams):
        raise ValueError('文件中没有音轨，无法进行翻译配音')
    duration = float(data.get('format', {}).get('duration') or 0)
    if duration <= 0:
        raise ValueError('视频时长无法识别')
    if duration > MAX_DURATION_SEC:
        raise ValueError(f'当前 Demo 仅支持 {MAX_DURATION_SEC} 秒以内的视频')
    return duration


def api_json(method: str, path: str, *, data=None, files=None) -> dict:
    if not API_KEY:
        raise RuntimeError('未配置 ELEVENLABS_API_KEY；或将 DEMO_MODE=true 运行本地模拟')
    url = f'{API_BASE}{path}'
    headers = {'xi-api-key': API_KEY, 'Accept': 'application/json'}
    try:
        r = requests.request(method, url, headers=headers, data=data, files=files, timeout=(15, 150))
    except requests.RequestException as exc:
        raise RuntimeError(f'连接 ElevenLabs 失败：{type(exc).__name__}') from exc
    if not r.ok:
        # Do not include request headers or signed download URLs in errors.
        try:
            info = r.json()
            message = json.dumps(info, ensure_ascii=False)[:700]
        except ValueError:
            message = r.text[:300]
        raise RuntimeError(f'ElevenLabs HTTP {r.status_code}：{message}')
    return r.json()


def create_project(job: dict, folder: Path) -> tuple[str, str | None]:
    if job.get('project_id'):
        return job['project_id'], job.get('language_id')
    with (folder / job['source_file']).open('rb') as fp:
        payload = {
            'model_id': 'dubbing_v2',
            'target_language': job['target_language'],
            'reference': f'Local demo {job["id"]}',
        }
        if job['source_language'] != 'auto':
            payload['source_language'] = job['source_language']
        result = api_json('POST', '', data=payload, files={'file': (job['source_file'], fp, 'application/octet-stream')})
    project_id = result.get('project_id')
    if not project_id:
        raise RuntimeError('创建项目没有返回 project_id')
    langs = result.get('language_ids') or []
    language_id = langs[0] if langs else None
    write_job(job['id'], project_id=project_id, language_id=language_id,
              message='已创建 Dubbing v2 项目；创建即可能产生收费，正在等待上游处理。', progress=18)
    return project_id, language_id


def resolve_language_id(project_id: str, target_language: str) -> str | None:
    result = api_json('GET', f'/{project_id}/language')
    for lang in result.get('languages', []):
        if lang.get('target_language') == target_language:
            return lang.get('language_id')
    return None


def poll_dubbing(job_id: str, project_id: str, language_id: str | None) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_SEC
    project_ready = False
    while time.monotonic() < deadline:
        project = api_json('GET', f'/{project_id}')
        state = project.get('status')
        if state == 'failed':
            raise RuntimeError(f'源视频准备失败：{project.get("error") or "未知原因"}')
        if state == 'ready':
            project_ready = True
            break
        write_job(job_id, status='preparing', progress=22,
                  message=f'上游正在识别源视频（{state or "等待中"}）')
        time.sleep(POLL_SECONDS)
    if not project_ready:
        raise RuntimeError('等待源视频准备超时；可点击「继续查询」复用现有项目，无须重新上传')

    if not language_id:
        language_id = resolve_language_id(project_id, read_job(job_id)['target_language'])
        if not language_id:
            raise RuntimeError('未找到目标语言任务；请检查上游项目，避免重复收费创建')
        write_job(job_id, language_id=language_id)

    while time.monotonic() < deadline:
        language = api_json('GET', f'/{project_id}/language/{language_id}')
        state = language.get('status')
        if state == 'failed':
            raise RuntimeError(f'目标语言配音失败：{language.get("error") or "未知原因"}')
        if state == 'completed':
            if language.get('output_revision') is not None and language.get('revision') != language.get('output_revision'):
                raise RuntimeError('配音输出版本与最新翻译文本不一致')
            return language.get('outputs') or {}
        if state == 'stale':
            raise RuntimeError('目标语言已过期（stale），请在上游确认重新生成后继续查询')
        write_job(job_id, status='dubbing', progress=55,
                  message=f'正在生成目标语言配音（{state or "等待中"}）')
        time.sleep(POLL_SECONDS)
    raise RuntimeError('等待配音完成超时；可点击「继续查询」复用现有项目')


def download_signed_file(url: str, destination: Path, max_bytes: int) -> None:
    u = urlparse(url)
    if u.scheme != 'https' or not u.hostname or u.hostname.lower() not in ALLOWED_OUTPUT_HOSTS or u.username or u.password:
        raise RuntimeError('上游输出下载域名未在可信白名单中，请核实 ALLOWED_OUTPUT_HOSTS')
    total = 0
    # Do not send ElevenLabs API credentials to the signed download URL.
    with requests.get(url, stream=True, timeout=(15, 120), allow_redirects=False) as response:
        response.raise_for_status()
        with destination.open('wb') as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    total += len(chunk)
                    if total > max_bytes:
                        destination.unlink(missing_ok=True)
                        raise RuntimeError('上游输出文件超出 Demo 限制')
                    file.write(chunk)
    if total == 0:
        raise RuntimeError('上游返回空文件')


def mock_dub(folder: Path, duration: float, language: str) -> bool:
    # Test the COMPLETE local media pipeline without pretending to translate.
    run_command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
                 '-i', f'sine=frequency=480:sample_rate=44100:duration={duration:.3f}',
                 '-c:a', 'flac', 'dub.flac'], folder)
    boundary = min(duration, max(0.8, duration / 2))
    def vtt_ts(sec):
        ms = round(sec * 1000)
        return f'{ms//3600000:02}:{(ms//60000)%60:02}:{(ms//1000)%60:02}.{ms%1000:03}'
    text = (f'WEBVTT\n\n{vtt_ts(0)} --> {vtt_ts(boundary)}\n'
            '本地模拟字幕：未调用翻译 API\n\n')
    if duration > boundary + 0.1:
        text += (f'{vtt_ts(boundary)} --> {vtt_ts(duration)}\n'
                 f'Mock only · Target: {language}\n')
    (folder / 'subtitles.vtt').write_text(text, encoding='utf-8')
    return True


def render_outputs(job_id: str, subtitles: bool) -> dict:
    job = read_job(job_id)
    folder = job_dir(job_id)
    source = job['source_file']
    if subtitles:
        run_command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                     '-i', 'subtitles.vtt', '-f', 'srt', 'subtitles.srt'], folder, 40)
    video_filter = [
        '-vf', "subtitles=filename=subtitles.vtt:force_style='FontName=DejaVu Sans,FontSize=18,Outline=2,Shadow=0,MarginV=25,Alignment=2'"
    ] if subtitles and job['burn_subtitles'] else []
    run_command([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-i', source, '-i', 'dub.flac',
        '-map', '0:v:0', '-map', '1:a:0',
        *video_filter,
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest', '-movflags', '+faststart', 'dubbed.mp4',
    ], folder, timeout=max(240, int(job['duration'] * 10)))
    outputs = {'video': 'dubbed.mp4', 'audio': 'dub.flac'}
    if subtitles:
        outputs.update(vtt='subtitles.vtt', srt='subtitles.srt')
    return outputs


def process_job(job_id: str) -> None:
    try:
        job = read_job(job_id)
        folder = job_dir(job_id)
        write_job(job_id, status='preparing', progress=10, message='准备提交 Dubbing v2 任务…', error=None)
        if DEMO_MODE:
            write_job(job_id, status='dubbing', progress=65, message='本地模拟音频和字幕中；不会真正翻译')
            has_subtitles = mock_dub(folder, job['duration'], job['target_language'])
        else:
            project_id, language_id = create_project(job, folder)
            urls = poll_dubbing(job_id, project_id, language_id)
            audio_url = urls.get('lossless_audio')
            if not audio_url:
                raise RuntimeError('上游完成，但没有返回 outputs.lossless_audio')
            write_job(job_id, status='rendering', progress=83, message='下载配音音轨和字幕…')
            (folder / 'dub.flac').unlink(missing_ok=True)
            download_signed_file(audio_url, folder / 'dub.flac', 600 * 1024 * 1024)
            subtitle_url = urls.get('subtitles')
            if subtitle_url:
                (folder / 'subtitles.vtt').unlink(missing_ok=True)
                download_signed_file(subtitle_url, folder / 'subtitles.vtt', 20 * 1024 * 1024)
            has_subtitles = bool(subtitle_url)
        write_job(job_id, status='rendering', progress=88, message='FFmpeg 正在合成视频…')
        outputs = render_outputs(job_id, has_subtitles)
        warning = '' if has_subtitles else '上游未返回 subtitles；已生成无字幕配音视频，请在上游确认字幕可用性。'
        if DEMO_MODE:
            warning = '当前为本地模拟：音频是测试提示音，字幕是占位文字，不是真实翻译配音。'
        write_job(job_id, status='completed', progress=100, message='视频合成完成',
                  outputs=outputs, warning=warning, error=None)
    except Exception as exc:
        write_job(job_id, status='failed', message='任务中断', error=str(exc)[:1500])


@app.get('/')
def home():
    return FileResponse(BASE / 'static' / 'index.html', media_type='text/html; charset=utf-8')


@app.get('/api/config')
def config():
    return {'demo_mode': DEMO_MODE, 'api_configured': bool(API_KEY),
            'max_upload_mb': MAX_UPLOAD_MB, 'max_duration_sec': MAX_DURATION_SEC,
            'languages': LANGUAGES}


@app.post('/api/jobs', status_code=202)
async def create_job(file: UploadFile = File(...), source_language: str = Form('auto'),
                     target_language: str = Form('en'), burn_subtitles: bool = Form(True)):
    if not DEMO_MODE and not API_KEY:
        raise HTTPException(503, '未配置 ElevenLabs API Key。请先在 .env 中设置 ELEVENLABS_API_KEY')
    if source_language != 'auto' and source_language not in LANGUAGES:
        raise HTTPException(422, '源语言不支持')
    if target_language not in LANGUAGES:
        raise HTTPException(422, '目标语言不支持')
    if source_language == target_language:
        raise HTTPException(422, '源语言和目标语言不能相同')
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED_EXTS:
        raise HTTPException(422, '支持 MP4、MOV、MKV、WebM')
    job_id = uuid.uuid4().hex
    folder = DATA_DIR / job_id
    folder.mkdir(mode=0o700)
    source_file = 'source' + suffix
    size = 0
    try:
        with (folder / source_file).open('wb') as fp:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f'文件超过 {MAX_UPLOAD_MB} MB 限制')
                fp.write(chunk)
        duration = probe_media(folder / source_file)
    except HTTPException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    except (ValueError, subprocess.TimeoutExpired) as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()
    job = {
        'id': job_id, 'created_at': now(), 'updated_at': now(),
        'status': 'queued', 'progress': 0, 'message': '已排队',
        'source_file': source_file, 'source_language': source_language,
        'target_language': target_language, 'burn_subtitles': burn_subtitles,
        'duration': round(duration, 3), 'size_bytes': size,
        'project_id': None, 'language_id': None,
        'outputs': {}, 'warning': '', 'error': None,
    }
    (folder / 'job.json').write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
    executor.submit(process_job, job_id)
    return public_job(job)


def public_job(job: dict) -> dict:
    return {k: v for k, v in job.items() if k != 'source_file'}


@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    return public_job(read_job(job_id))


@app.post('/api/jobs/{job_id}/resume', status_code=202)
def resume_job(job_id: str):
    job = read_job(job_id)
    if job['status'] not in ('failed', 'interrupted'):
        raise HTTPException(409, '仅允许继续查询失败或被中断的任务')
    if not DEMO_MODE and not job.get('project_id'):
        raise HTTPException(409, '上游项目尚未创建；请重新上传')
    write_job(job_id, status='queued', progress=15, message='继续查询现有任务', error=None)
    executor.submit(process_job, job_id)
    return public_job(read_job(job_id))


@app.get('/api/jobs/{job_id}/download/{kind}')
def download_file(job_id: str, kind: str):
    if kind not in ('video', 'audio', 'vtt', 'srt'):
        raise HTTPException(404, '文件类型不存在')
    job = read_job(job_id)
    if job['status'] != 'completed' or kind not in job.get('outputs', {}):
        raise HTTPException(404, '文件尚未生成')
    path = job_dir(job_id) / job['outputs'][kind]
    if not path.is_file():
        raise HTTPException(404, '文件不存在')
    return FileResponse(path, filename=path.name,
                        media_type='video/mp4' if kind == 'video' else 'application/octet-stream')


@app.get('/api/jobs/{job_id}/preview')
def video_preview(job_id: str):
    job = read_job(job_id)
    if job['status'] != 'completed':
        raise HTTPException(404, '成片尚未生成')
    return FileResponse(job_dir(job_id) / job['outputs']['video'], media_type='video/mp4')


# Jobs persist across restarts. Do not silently resubmit paid API calls.
for record in DATA_DIR.glob('*/job.json'):
    try:
        saved = json.loads(record.read_text(encoding='utf-8'))
        if saved.get('status') not in ('completed', 'failed', 'interrupted'):
            saved['status'] = 'interrupted'
            saved['message'] = '服务已重启；如已有上游项目，请选择继续查询（不会重新创建项目）'
            record.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
    except (ValueError, OSError):
        pass
