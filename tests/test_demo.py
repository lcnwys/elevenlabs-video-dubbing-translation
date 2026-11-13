import importlib
import os
import subprocess
import time
from pathlib import Path

from fastapi.testclient import TestClient

os.environ['DEMO_MODE'] = 'true'
os.environ['POLL_SECONDS'] = '2'
os.environ['MAX_DURATION_SEC'] = '600'
# Use a fixed path for test artifacts; no upstream requests.
os.environ['DATA_DIR'] = str(Path(__file__).resolve().parent / '.test-data')
app_module = importlib.import_module('app')
client = TestClient(app_module.app)


def make_sample(tmp_path):
    result = tmp_path / 'sample.mp4'
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'lavfi', '-i', 'color=c=darkblue:s=320x240:r=15:d=2.5',
        '-f', 'lavfi', '-i', 'sine=frequency=550:sample_rate=44100:duration=2.5',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
        '-shortest', str(result),
    ], check=True, capture_output=True)
    return result


def test_home_and_config():
    r = client.get('/')
    assert r.status_code == 200 and '视频翻译配音工作台' in r.text
    config = client.get('/api/config').json()
    assert config['demo_mode'] is True


def test_reject_missing_video():
    result = client.post('/api/jobs', files={'file': ('notes.txt', b'abcd', 'text/plain')},
                         data={'target_language': 'en'})
    assert result.status_code == 422


def test_end_to_end_mock(tmp_path):
    source = make_sample(tmp_path)
    with source.open('rb') as fp:
        r = client.post('/api/jobs', files={'file': ('clip.mp4', fp, 'video/mp4')}, data={
            'source_language': 'zh', 'target_language': 'en', 'burn_subtitles': 'true',
        })
    assert r.status_code == 202, r.text
    job_id = r.json()['id']
    deadline = time.time() + 80
    while time.time() < deadline:
        job = client.get('/api/jobs/' + job_id).json()
        if job['status'] in ('completed', 'failed'):
            break
        time.sleep(.3)
    assert job['status'] == 'completed', job.get('error')
    assert '本地模拟' in job['warning']
    assert job['outputs']['video'] == 'dubbed.mp4'
    for kind in ('video', 'vtt', 'srt', 'audio'):
        r = client.get(f'/api/jobs/{job_id}/download/{kind}')
        assert r.status_code == 200 and len(r.content) > 0
    vtt = client.get(f'/api/jobs/{job_id}/download/vtt').text
    assert 'WEBVTT' in vtt and '未调用翻译 API' in vtt
    video = app_module.job_dir(job_id) / 'dubbed.mp4'
    duration = app_module.probe_media(video)
    assert 1.5 < duration < 4
    invalid = client.get(f'/api/jobs/{job_id}/download/private')
    assert invalid.status_code == 404


def test_real_api_flow_stubbed_without_billing(tmp_path, monkeypatch):
    """Exercises the real-mode project/language polling contract with fake upstream responses."""
    monkeypatch.setattr(app_module, 'DEMO_MODE', False)
    monkeypatch.setattr(app_module, 'API_KEY', 'test-not-a-real-key')
    source = make_sample(tmp_path)
    api_calls = []
    def fake_api(method, path, *, data=None, files=None):
        api_calls.append((method, path))
        if method == 'POST' and path == '':
            assert data['model_id'] == 'dubbing_v2'
            assert data['target_language'] == 'en'
            assert 'file' in files
            return {'project_id': 'proj_stub', 'language_ids': ['lang_stub'], 'status': 'queued'}
        if path == '/proj_stub':
            return {'status': 'ready'}
        if path == '/proj_stub/language/lang_stub':
            return {'status': 'completed', 'revision': 0, 'output_revision': 0,
                    'outputs': {'lossless_audio': 'https://storage.googleapis.com/test/audio',
                                'subtitles': 'https://storage.googleapis.com/test/subtitles'}}
        raise AssertionError((method, path))

    def fake_download(url, destination, max_bytes):
        folder = destination.parent
        if destination.suffix == '.flac':
            app_module.run_command([
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
                '-i', 'sine=frequency=440:duration=2.5', '-c:a', 'flac', 'dub.flac',
            ], folder)
        else:
            destination.write_text('WEBVTT\n\n00:00:00.000 --> 00:00:02.500\nHello\n', encoding='utf-8')

    monkeypatch.setattr(app_module, 'api_json', fake_api)
    monkeypatch.setattr(app_module, 'download_signed_file', fake_download)
    with source.open('rb') as fp:
        r = client.post('/api/jobs', files={'file': ('clip.mp4', fp, 'video/mp4')},
                        data={'source_language': 'zh', 'target_language': 'en', 'burn_subtitles': 'true'})
    assert r.status_code == 202, r.text
    job_id = r.json()['id']
    deadline = time.time() + 80
    while time.time() < deadline:
        job = client.get('/api/jobs/' + job_id).json()
        if job['status'] in ('completed', 'failed'):
            break
        time.sleep(.2)
    assert job['status'] == 'completed', job.get('error')
    assert job['project_id'] == 'proj_stub'
    assert job['language_id'] == 'lang_stub'
    assert job['warning'] == ''
    assert ('POST', '') in api_calls and ('GET', '/proj_stub/language/lang_stub') in api_calls
    assert client.get(f'/api/jobs/{job_id}/download/video').status_code == 200
    assert 'Hello' in client.get(f'/api/jobs/{job_id}/download/srt').text
