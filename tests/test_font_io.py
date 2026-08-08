import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from OpenCCFontGenerator import font as font_module


class FakeCFF:
    def __init__(self):
        self.desubroutinized = False
        self.hints_removed = False
        self.topDictIndex = []

    def desubroutinize(self):
        self.desubroutinized = True

    def remove_hints(self):
        self.hints_removed = True


class FakeCFFTable:
    def __init__(self, cff):
        self.cff = cff


class FakeFont:
    def __init__(self, cff):
        self.cff = cff
        self.closed = False

    def __getitem__(self, tag):
        if tag != 'CFF ':
            raise KeyError(tag)
        return FakeCFFTable(self.cff)

    def save(self, output_path):
        Path(output_path).write_bytes(b'normalized-font')

    def close(self):
        self.closed = True


class FakeGeneratedFont:
    def __init__(self):
        self.cff_accessed = False
        self.closed = False
        self.cff = FakeCFF()
        font_dict = type('FontDict', (), {
            'rawDict': {'FontName': 'Test', 'FontBBox': [0, 0, 1, 1]},
        })()
        top_dict = type('TopDict', (), {'FDArray': [font_dict]})()
        self.cff.topDictIndex = [top_dict]

    def __contains__(self, tag):
        return tag == 'CFF '

    def __getitem__(self, tag):
        if tag != 'CFF ':
            raise KeyError(tag)
        self.cff_accessed = True
        return FakeCFFTable(self.cff)

    def save(self, output_path):
        if not self.cff_accessed:
            raise AssertionError('CFF table must be parsed before save')
        Path(output_path).write_bytes(b'recompiled-cff')

    def close(self):
        self.closed = True


class FontIOTests(unittest.TestCase):
    def test_normalize_otf_desubroutinizes_and_removes_cff_hints(self):
        cff = FakeCFF()
        fake_font = FakeFont(cff)
        with mock.patch.object(font_module, 'TTFont', return_value=fake_font):
            normalized_path = font_module.normalize_otf_for_otfcc('source.otf')
        try:
            self.assertTrue(cff.desubroutinized)
            self.assertTrue(cff.hints_removed)
            self.assertTrue(fake_font.closed)
            self.assertEqual(Path(normalized_path).read_bytes(), b'normalized-font')
        finally:
            os.remove(normalized_path)

    def test_load_font_always_normalizes_cff_before_otfccdump(self):
        with tempfile.TemporaryDirectory() as directory:
            normalized_path = os.path.join(directory, 'normalized.otf')
            Path(normalized_path).write_bytes(b'normalized-font')
            payload = {'cmap': {'65': 'A'}}
            with mock.patch.object(font_module, 'is_cff_font', return_value=True), \
                 mock.patch.object(
                     font_module, 'normalize_otf_for_otfcc',
                     return_value=normalized_path,
                 ) as normalize, \
                 mock.patch.object(
                     font_module.subprocess, 'check_output',
                     return_value=json.dumps(payload).encode('utf-8'),
                 ) as check_output:
                result = font_module.load_font('source.otf')

            normalize.assert_called_once_with('source.otf', ttc_index=None)
            check_output.assert_called_once_with(('otfccdump', normalized_path))
            self.assertEqual(result['cmap_rev']['A'], ['65'])

    def test_save_font_builds_validates_then_atomically_replaces_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = os.path.join(directory, 'output.otf')
            previous_cwd = os.getcwd()
            os.chdir(directory)
            try:
                def fake_run(command, **kwargs):
                    Path(command[2]).write_bytes(b'built-font')
                    return subprocess.CompletedProcess(command, 0)

                with mock.patch.object(
                    font_module.subprocess, 'run', side_effect=fake_run,
                ) as run, \
                     mock.patch.object(font_module, 'normalize_generated_font') as normalize, \
                     mock.patch.object(font_module, 'validate_font_output') as validate:
                    font_module.save_font({'cmap_rev': {}, 'cmap': {}}, output_path)
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(Path(output_path).read_bytes(), b'built-font')
            self.assertTrue(run.call_args.kwargs['check'])
            normalize.assert_called_once()
            validate.assert_called_once()

    def test_save_font_does_not_replace_existing_output_when_build_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = os.path.join(directory, 'output.otf')
            Path(output_path).write_bytes(b'existing-font')
            previous_cwd = os.getcwd()
            os.chdir(directory)
            try:
                error = subprocess.CalledProcessError(1, ('otfccbuild',))
                with mock.patch.object(font_module.subprocess, 'run', side_effect=error):
                    with self.assertRaises(subprocess.CalledProcessError):
                        font_module.save_font({'cmap': {}}, output_path)
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(Path(output_path).read_bytes(), b'existing-font')

    def test_normalize_generated_font_recompiles_cff_and_preserves_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = os.path.join(directory, 'output.otf')
            Path(output_path).write_bytes(b'raw-cff')
            os.chmod(output_path, 0o640)
            fake_font = FakeGeneratedFont()

            with mock.patch.object(font_module, 'TTFont', return_value=fake_font):
                font_module.normalize_generated_font(output_path)

            self.assertTrue(fake_font.cff_accessed)
            self.assertTrue(fake_font.closed)
            self.assertEqual(
                fake_font.cff.topDictIndex[0].FDArray[0].rawDict,
                {'FontName': 'Test'},
            )
            self.assertEqual(Path(output_path).read_bytes(), b'recompiled-cff')
            self.assertEqual(os.stat(output_path).st_mode & 0o777, 0o640)


if __name__ == '__main__':
    unittest.main()
