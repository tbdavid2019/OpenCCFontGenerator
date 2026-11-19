"""Tests for OpenCCFontGenerator Web UI, FastAPI endpoints, rate limits, and worker execution."""

import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

try:
    from fastapi.testclient import TestClient
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from OpenCCFontGenerator.web import worker as worker_module
    from OpenCCFontGenerator.web.app import _client_ip_from_scope, _parse_trusted_networks, create_app
    from OpenCCFontGenerator.web.config import WebSettings
    from OpenCCFontGenerator.web.jobs import JobManager, ZipExtractionBudget, extract_fonts_from_zip
    from OpenCCFontGenerator.web.rate_limit import SlidingWindowRateLimiter
except ImportError as exc:
    raise unittest.SkipTest(f'Web optional dependencies unavailable: {exc}')


def _build_minimal_ttf_bytes() -> bytes:
    """Construct a valid minimal TTF in memory with ASCII + sample Han glyphs."""
    chars = {
        '.notdef': 0,
        'uni4E00': 0x4E00,
        'uni540E': 0x540E,  # 后
        'uni5F8C': 0x5F8C,  # 後
        'uni6765': 0x6765,  # 来
        'uni4F86': 0x4F86,  # 來
        'uni7687': 0x7687,  # 皇
        'uni8F6F': 0x8F6F,  # 软
        'uni8EDF': 0x8EDF,  # 軟
        'uni4EF6': 0x4EF6,  # 件
        'uni9AD4': 0x9AD4,  # 體
        'A': ord('A'),
    }
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(chars.keys()))
    cmap = {cp: name for name, cp in chars.items() if cp > 0}
    fb.setupCharacterMap(cmap)

    glyf_map = {}
    metrics = {}
    for name in chars:
        pen = TTGlyphPen(None)
        pen.moveTo((100, 0))
        pen.lineTo((100, 700))
        pen.lineTo((800, 700))
        pen.lineTo((800, 0))
        pen.closePath()
        glyf_map[name] = pen.glyph()
        metrics[name] = (1000, 100)

    fb.setupGlyf(glyf_map)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=850, descent=-150)
    fb.setupNameTable({'familyName': 'MiniTestFont', 'styleName': 'Regular'})
    fb.setupOS2()
    fb.setupPost()

    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.settings = WebSettings(
            storage_dir=Path(self.tmpdir.name),
            max_file_mb=2,
            max_total_upload_mb=4,
            max_concurrent_jobs=1,
            max_queued_jobs=5,
            job_ttl_seconds=300,
            job_timeout_seconds=120,
            rate_limit_per_min=20,
            trust_proxy_headers=False,
        )
        self.app = create_app(self.settings)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_index_health_and_capabilities(self):
        with TestClient(self.app) as client:
            index_resp = client.get('/')
            self.assertEqual(index_resp.status_code, 200)
            self.assertIn('OpenCC 字型工作台', index_resp.text)

            health_resp = client.get('/healthz')
            self.assertEqual(health_resp.status_code, 200)
            health = health_resp.json()
            self.assertTrue(health['cache_ready'])

            cap_resp = client.get('/api/v1/capabilities')
            self.assertEqual(cap_resp.status_code, 200)
            cap = cap_resp.json()
            self.assertEqual(cap['max_file_mb'], 2)
            self.assertIn('twp', cap['configs'])
            self.assertEqual(len(cap['variable_weights']), 9)

    def test_preview_endpoint_matches_opencc_rules(self):
        with TestClient(self.app) as client:
            resp = client.get('/api/v1/preview', params={
                'config': 'twp',
                'no_punc': 'true',
                'text': '皇后后来软件“你好”',
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data['sample_converted'], '皇后後來軟體“你好”')

            resp_punc = client.get('/api/v1/preview', params={
                'config': 'twp',
                'no_punc': 'false',
                'text': '“你好”',
            })
            self.assertEqual(resp_punc.status_code, 200)
            self.assertEqual(resp_punc.json()['sample_converted'], '「你好」')

    def test_rate_limiter_enforces_limit_and_window(self):
        limiter = SlidingWindowRateLimiter(limit_per_minute=2, window_seconds=60)
        self.assertTrue(limiter.check_and_record('1.2.3.4', now=100.0).allowed)
        self.assertTrue(limiter.check_and_record('1.2.3.4', now=110.0).allowed)
        blocked = limiter.check_and_record('1.2.3.4', now=120.0)
        self.assertFalse(blocked.allowed)
        self.assertGreater(blocked.retry_after, 0)
        # Other IP unaffected
        self.assertTrue(limiter.check_and_record('5.6.7.8', now=120.0).allowed)
        # Window advances past first hit
        self.assertTrue(limiter.check_and_record('1.2.3.4', now=161.0).allowed)

    def test_upload_validation_and_rate_limit_responses(self):
        limited_settings = WebSettings(
            storage_dir=Path(self.tmpdir.name) / 'limited',
            max_file_mb=1,
            max_total_upload_mb=2,
            max_concurrent_jobs=1,
            max_queued_jobs=5,
            rate_limit_per_min=1,
        )
        limited_app = create_app(limited_settings)

        with TestClient(limited_app) as client:
            # Invalid extension -> 400
            bad_ext = client.post(
                '/api/v1/jobs/webfont',
                files={'source_font': ('bad.txt', b'hello', 'text/plain')},
            )
            self.assertEqual(bad_ext.status_code, 400)

            # Second request in same minute hits rate limit -> 429
            over_rate = client.post(
                '/api/v1/jobs/webfont',
                files={'source_font': ('font.ttf', _build_minimal_ttf_bytes(), 'font/ttf')},
            )
            self.assertEqual(over_rate.status_code, 429)
            self.assertIn('Retry-After', over_rate.headers)

        with TestClient(self.app) as client:
            # Oversized payload (> 2 MB limit) -> 413
            oversized = b'0' * (2 * 1024 * 1024 + 128)
            too_big = client.post(
                '/api/v1/jobs/webfont',
                files={'source_font': ('huge.ttf', oversized, 'font/ttf')},
            )
            self.assertEqual(too_big.status_code, 413)

            # Invalid zip on static-family -> 400
            bad_zip = client.post(
                '/api/v1/jobs/static-family',
                files={'source_files': ('fonts.zip', b'not-a-zip', 'application/zip')},
            )
            self.assertEqual(bad_zip.status_code, 400)

    def test_webfont_and_convert_end_to_end_job_lifecycle(self):
        ttf_bytes = _build_minimal_ttf_bytes()

        with TestClient(self.app) as client:
            # 1. Webfont WOFF2 + CSS bundle job
            submit = client.post(
                '/api/v1/jobs/webfont',
                files={'source_font': ('MiniTest.ttf', ttf_bytes, 'font/ttf')},
                data={'font_family': 'MiniSpecimen'},
            )
            self.assertEqual(submit.status_code, 202, submit.text)
            job_id = submit.json()['job_id']

            deadline = time.time() + 30
            status_data = None
            while time.time() < deadline:
                poll = client.get(f'/api/v1/jobs/{job_id}')
                self.assertEqual(poll.status_code, 200)
                status_data = poll.json()
                if status_data['status'] in ('completed', 'failed'):
                    break
                time.sleep(0.15)

            self.assertIsNotNone(status_data)
            self.assertEqual(status_data['status'], 'completed', status_data)
            self.assertTrue(status_data['download_url'])

            # Batch query works
            batch = client.get('/api/v1/jobs', params={'ids': job_id})
            self.assertEqual(batch.status_code, 200)
            self.assertEqual(len(batch.json()), 1)

            # Download primary ZIP archive and inspect contents
            dl = client.get(status_data['download_url'])
            self.assertEqual(dl.status_code, 200)
            with zipfile.ZipFile(io.BytesIO(dl.content), 'r') as zf:
                names = set(zf.namelist())
                self.assertIn('MiniTest.woff2', names)
                self.assertIn('fonts.css', names)
                css_text = zf.read('fonts.css').decode('utf-8')
                self.assertIn("font-family: 'MiniSpecimen';", css_text)

            # Delete job cleans up
            deleted = client.delete(f'/api/v1/jobs/{job_id}')
            self.assertEqual(deleted.status_code, 200)
            missing = client.get(f'/api/v1/jobs/{job_id}')
            self.assertEqual(missing.status_code, 404)

    def test_convert_and_rotate90_end_to_end_when_otfcc_present(self):
        with TestClient(self.app) as client:
            health = client.get('/healthz').json()
            if not (health['otfccdump_available'] and health['otfccbuild_available'] and health['cache_ready']):
                self.skipTest('otfcc binaries or OpenCC cache missing in test environment')

            ttf_bytes = _build_minimal_ttf_bytes()
            submit = client.post(
                '/api/v1/jobs/convert',
                files={'source_font': ('MiniTest.ttf', ttf_bytes, 'font/ttf')},
                data={
                    'config': 'twp',
                    'no_punc': 'true',
                    'output_woff2': 'true',
                    'kobo_mode': 'true',
                },
            )
            self.assertEqual(submit.status_code, 202, submit.text)
            job_id = submit.json()['job_id']

            deadline = time.time() + 60
            status_data = None
            while time.time() < deadline:
                status_data = client.get(f'/api/v1/jobs/{job_id}').json()
                if status_data['status'] in ('completed', 'failed'):
                    break
                time.sleep(0.25)

            self.assertEqual(status_data['status'], 'completed', status_data)
            filenames = {a['filename'] for a in status_data['artifacts']}
            self.assertIn('MiniTest_TC.ttf', filenames)
            self.assertIn('MiniTest_TC.woff2', filenames)
            self.assertIn('MiniTest_TC_bundle.zip', filenames)

            dl_ttf = client.get(f'/api/v1/jobs/{job_id}/artifacts/MiniTest_TC.ttf')
            self.assertEqual(dl_ttf.status_code, 200)
            self.assertGreater(len(dl_ttf.content), 100)

            # Also verify rotate90 and static-family (ZIP upload)
            rot = client.post(
                '/api/v1/jobs/rotate90',
                files={'source_font': ('MiniTest.ttf', ttf_bytes, 'font/ttf')},
                data={'direction': 'cw', 'kobo_mode': 'true'},
            )
            self.assertEqual(rot.status_code, 202, rot.text)
            rot_id = rot.json()['job_id']

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                zf.writestr('Mini-Regular.ttf', ttf_bytes)
                zf.writestr('__MACOSX/._Mini-Regular.ttf', b'garbage')
            fam = client.post(
                '/api/v1/jobs/static-family',
                files={'source_files': ('static.zip', zip_buf.getvalue(), 'application/zip')},
                data={'config': 's2tw', 'family_name_prefix': 'MiniFam'},
            )
            self.assertEqual(fam.status_code, 202, fam.text)
            fam_id = fam.json()['job_id']

            for jid, expected_file in ((rot_id, 'MiniTest_Rotated90.ttf'), (fam_id, 'static_family_TC.zip')):
                end = time.time() + 60
                res = None
                while time.time() < end:
                    res = client.get(f'/api/v1/jobs/{jid}').json()
                    if res['status'] in ('completed', 'failed'):
                        break
                    time.sleep(0.25)
                self.assertEqual(res['status'], 'completed', res)
                self.assertIn(expected_file, {a['filename'] for a in res['artifacts']})

    def test_security_hardening_guards(self):
        # 1. Proxy headers fail closed unless trust_proxy=True AND valid trusted_proxies configured
        spoof_scope = {
            'type': 'http',
            'client': ('198.51.100.25', 12345),
            'headers': [(b'x-forwarded-for', b'203.0.113.9, 10.0.0.5')],
        }
        self.assertEqual(_client_ip_from_scope(spoof_scope, False, []), '198.51.100.25')
        self.assertEqual(_client_ip_from_scope(spoof_scope, True, []), '198.51.100.25')
        with self.assertRaises(ValueError):
            _parse_trusted_networks(('not-an-ip',))
        trusted_nets = _parse_trusted_networks(('127.0.0.1', '10.0.0.0/8'))
        self.assertEqual(_client_ip_from_scope(spoof_scope, True, trusted_nets), '198.51.100.25')
        proxied_scope = {
            'type': 'http',
            'client': ('10.0.0.2', 12345),
            'headers': [(b'x-forwarded-for', b'1.1.1.1, 203.0.113.9, 10.0.0.5')],
        }
        self.assertEqual(_client_ip_from_scope(proxied_scope, True, trusted_nets), '203.0.113.9')

        # 2. Degraded /healthz returns HTTP 503
        with TestClient(self.app) as client:
            with patch.object(shutil, 'which', return_value=None):
                degraded = client.get('/healthz')
                self.assertEqual(degraded.status_code, 503)
                self.assertEqual(degraded.json()['status'], 'degraded')

            # 3. Pre-multipart Content-Length AND streaming/chunked limits return 413 (not 400)
            too_large = client.post(
                '/api/v1/jobs/webfont',
                headers={'Content-Length': str(50 * 1024 * 1024)},
                content=b'x',
            )
            self.assertEqual(too_large.status_code, 413)

            def _oversized_stream():
                for _ in range(9):
                    yield b'x' * (1024 * 1024)

            streamed_too_large = client.post(
                '/api/v1/jobs/webfont',
                headers={'Content-Type': 'multipart/form-data; boundary=testboundary'},
                content=_oversized_stream(),
            )
            self.assertEqual(streamed_too_large.status_code, 413)

            # 4. Path traversal in fallback_prefix rejected with 400
            bad_prefix = client.post(
                '/api/v1/jobs/variable-family',
                files={
                    'source_font': ('VF.ttf', _build_minimal_ttf_bytes(), 'font/ttf'),
                    'fallback_files': ('FB-Regular.ttf', _build_minimal_ttf_bytes(), 'font/ttf'),
                },
                data={'fallback_prefix': '../../secret'},
            )
            self.assertEqual(bad_prefix.status_code, 400)

    def test_zip_shared_budget_and_queue_slot_reservation(self):
        # Shared budget stops decompression across multiple archives
        z1 = Path(self.tmpdir.name) / 'a.zip'
        z2 = Path(self.tmpdir.name) / 'b.zip'
        with zipfile.ZipFile(z1, 'w') as zf:
            zf.writestr('a.ttf', b'A' * 600)
        with zipfile.ZipFile(z2, 'w') as zf:
            zf.writestr('b.ttf', b'B' * 600)

        budget = ZipExtractionBudget(remaining_bytes=1000, remaining_entries=10, max_single_file_bytes=800)
        out_dir = Path(self.tmpdir.name) / 'unzipped'
        res1 = extract_fonts_from_zip(z1, out_dir, {'.ttf'}, 1000, budget=budget)
        self.assertEqual(len(res1), 1)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            extract_fonts_from_zip(z2, out_dir, {'.ttf'}, 1000, budget=budget)
        self.assertEqual(ctx.exception.status_code, 413)

        # Queue slot reservation honors max_queued_jobs=1 even before submit_job()
        q_settings = WebSettings(storage_dir=Path(self.tmpdir.name) / 'qcap', max_queued_jobs=1, max_concurrent_jobs=1)
        mgr = JobManager(q_settings)
        try:
            jid, _ = mgr.create_job_dir()
            with self.assertRaises(HTTPException) as full_ctx:
                mgr.create_job_dir()
            self.assertEqual(full_ctx.exception.status_code, 503)
            mgr.release_pending_job(jid)
            jid2, _ = mgr.create_job_dir()
            mgr.release_pending_job(jid2)
        finally:
            mgr.shutdown()

    def test_worker_register_outputs_rejects_empty_and_cleans_intermediates(self):
        with self.assertRaises(RuntimeError):
            worker_module._register_outputs(
                Path(self.tmpdir.name),
                [Path(self.tmpdir.name) / 'nonexistent.ttf'],
                Path(self.tmpdir.name) / 'nonexistent.ttf',
            )

        job_dir = Path(self.tmpdir.name) / 'job_cleanup'
        inputs_dir = job_dir / 'inputs' / 'source'
        outputs_dir = job_dir / 'outputs'
        inputs_dir.mkdir(parents=True)
        outputs_dir.mkdir(parents=True)
        (inputs_dir / 'A.ttf').write_bytes(b'src')

        spec_path = job_dir / 'spec.json'
        spec_path.write_text(json.dumps({
            'job_id': 'a1b2c3d4e5f6',
            'mode': 'static-family',
            'job_dir': str(job_dir),
            'input_dir': str(inputs_dir),
            'fallback_dir': None,
            'params': {'config': 's2t'},
        }), encoding='utf-8')

        def fake_static_family(**kwargs):
            out_file = Path(kwargs['output_dir']) / 'A_TC.ttf'
            out_file.write_bytes(b'compiled-ttf')
            return [{'output_file': str(out_file)}]

        prev_cwd = os.getcwd()
        try:
            with patch.object(worker_module, 'build_static_cjk_family', side_effect=fake_static_family):
                rc = worker_module.run_job_spec(spec_path)
        finally:
            os.chdir(prev_cwd)

        self.assertEqual(rc, 0)
        self.assertFalse((job_dir / 'inputs').exists())
        self.assertFalse((outputs_dir / 'family_files').exists())
        self.assertTrue((outputs_dir / 'static_family_TC.zip').is_file())
        self.assertTrue((job_dir / 'result.json').is_file())

    def test_non_ascii_artifact_download_url_encoded(self):
        ttf_bytes = _build_minimal_ttf_bytes()
        with TestClient(self.app) as client:
            submit = client.post(
                '/api/v1/jobs/webfont',
                files={'source_font': ('測試字型.ttf', ttf_bytes, 'font/ttf')},
                data={'font_family': 'TestCJK'},
            )
            self.assertEqual(submit.status_code, 202, submit.text)
            job_id = submit.json()['job_id']

            deadline = time.time() + 30
            status_data = None
            while time.time() < deadline:
                status_data = client.get(f'/api/v1/jobs/{job_id}').json()
                if status_data['status'] in ('completed', 'failed'):
                    break
                time.sleep(0.15)

            self.assertEqual(status_data['status'], 'completed', status_data)
            artifacts = status_data['artifacts']
            self.assertTrue(artifacts)
            woff2_art = next((a for a in artifacts if a['filename'] == '測試字型.woff2'), None)
            self.assertIsNotNone(woff2_art, artifacts)
            self.assertIn('%E6%B8%AC%E8%A9%A6%E5%AD%97%E5%9E%8B.woff2', woff2_art['download_url'])
            self.assertNotIn('測試字型', woff2_art['download_url'])

            dl_art = client.get(woff2_art['download_url'])
            self.assertEqual(dl_art.status_code, 200)
            self.assertGreater(len(dl_art.content), 20)

            dl_primary = client.get(status_data['download_url'])
            self.assertEqual(dl_primary.status_code, 200)


if __name__ == '__main__':
    unittest.main()
