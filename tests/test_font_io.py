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


class OpenCCGsubAndVariantTests(unittest.TestCase):
    def test_gsub_tables_merge_into_existing_indexed_features_without_duplicates(self):
        obj = {
            'GSUB': {
                'languages': {
                    'DFLT_DFLT': {'features': ['ccmp_00000', 'liga_00001', 'rlig_00002']},
                    'hani_ZHT ': {'features': ['ccmp_00003', 'liga_00004', 'rlig_00005']},
                    'latn_DFLT': {'features': ['liga_00001']},
                },
                'features': {
                    'ccmp_00000': ['existing_ccmp'],
                    'liga_00001': ['existing_liga'],
                    'rlig_00002': ['existing_rlig'],
                    'ccmp_00003': ['existing_ccmp_zht'],
                    'liga_00004': ['existing_liga_zht'],
                    'rlig_00005': ['existing_rlig_zht'],
                },
                'lookups': {},
                'lookupOrder': ['existing_ccmp', 'existing_liga', 'existing_rlig'],
            }
        }
        feature_names = ['liga', 'rlig', 'ccmp']
        font_module.insert_empty_features(obj, feature_names)
        font_module.create_word2pseu_table(obj, feature_names, [(['a', 'b'], 'pseu0')])
        font_module.create_char2char_table(obj, feature_names, [('a', 'b')])
        font_module.create_pseu2word_table(obj, feature_names, [('pseu0', ['c', 'd'])])

        for lang_name, lang_table in obj['GSUB']['languages'].items():
            tags = [font_module.get_gsub_feature_tag(k) for k in lang_table['features']]
            self.assertEqual(len(tags), len(set(tags)), f'Duplicate tags in {lang_name}: {tags}')
            self.assertEqual(set(tags), {'ccmp', 'liga', 'rlig'})

        for feat_key in ('ccmp_00000', 'liga_00001', 'rlig_00002', 'ccmp_00003', 'liga_00004', 'rlig_00005'):
            self.assertEqual(
                obj['GSUB']['features'][feat_key][-3:],
                ['word2pseu', 'char2char', 'pseu2word'],
            )
        self.assertEqual(
            obj['GSUB']['lookupOrder'][-3:],
            ['word2pseu', 'char2char', 'pseu2word'],
        )

    def test_apply_variants_separates_fa_and_hair_and_handles_s2hk_and_t2s(self):
        # Font has 髮 only (missing 發): 發 must NOT map to 髮
        obj_hair_only = {
            'cmap': {str(ord('髮')): 'g_hair'},
            'cmap_rev': {'g_hair': [str(ord('髮'))]},
        }
        font_module.apply_variants(obj_hair_only, config='s2t')
        self.assertNotIn(str(ord('發')), obj_hair_only['cmap'])

        # Font has 發 only (missing 髮): 髮 must NOT map to 發
        obj_emit_only = {
            'cmap': {str(ord('發')): 'g_emit'},
            'cmap_rev': {'g_emit': [str(ord('發'))]},
        }
        font_module.apply_variants(obj_emit_only, config='s2t')
        self.assertNotIn(str(ord('髮')), obj_emit_only['cmap'])

        # s2hk uses Var_hk.txt which has space-separated entries; must not raise TypeError
        obj_hk = {
            'cmap': {str(ord('敘')): 'g_xu'},
            'cmap_rev': {'g_xu': [str(ord('敘'))]},
        }
        font_module.apply_variants(obj_hk, config='s2hk')
        self.assertEqual(obj_hk['cmap'].get(str(ord('敍'))), 'g_xu')

        # t2s must not pre-fill Simplified codepoints with Traditional glyphs
        obj_t2s = {
            'cmap': {str(ord('後')): 'g_hou_t', str(ord('發')): 'g_fa_t'},
            'cmap_rev': {'g_hou_t': [str(ord('後'))], 'g_fa_t': [str(ord('發'))]},
        }
        font_module.apply_variants(obj_t2s, config='t2s')
        self.assertNotIn(str(ord('后')), obj_t2s['cmap'])
        self.assertNotIn(str(ord('发')), obj_t2s['cmap'])

    def test_build_font_merges_fallback_before_apply_variants(self):
        primary_font = {
            'cmap': {
                str(ord('后')): 'g_hou_s',
                str(ord('来')): 'g_lai_s',
            },
            'cmap_rev': {
                'g_hou_s': [str(ord('后'))],
                'g_lai_s': [str(ord('来'))],
            },
            'glyf': {
                '.notdef': {},
                'g_hou_s': {'contours': []},
                'g_lai_s': {'contours': []},
            },
            'glyph_order': ['.notdef', 'g_hou_s', 'g_lai_s'],
            'name': [{'platformID': 3, 'encodingID': 1, 'languageID': 1033, 'nameID': 1, 'nameString': 'TestSC'}],
            'head': {'fontRevision': 1.0},
        }
        fallback_font = {
            'cmap': {
                str(ord('後')): 'g_hou_t_fb',
                str(ord('來')): 'g_lai_t_fb',
            },
            'cmap_rev': {
                'g_hou_t_fb': [str(ord('後'))],
                'g_lai_t_fb': [str(ord('來'))],
            },
            'glyf': {
                'g_hou_t_fb': {'contours': [[{'x': 1, 'y': 2, 'on': True}]]},
                'g_lai_t_fb': {'contours': [[{'x': 3, 'y': 4, 'on': True}]]},
            },
            'glyph_order': ['g_hou_t_fb', 'g_lai_t_fb'],
        }

        saved_objs = []

        def fake_load(font_path, ttc_index=None):
            if font_path == 'primary.ttf':
                return primary_font
            if font_path == 'fallback.ttf':
                return fallback_font
            raise AssertionError(font_path)

        def fake_save(obj, output_path, output_woff2=False):
            saved_objs.append(obj)

        with mock.patch.object(font_module, 'load_font', side_effect=fake_load), \
             mock.patch.object(font_module, 'save_font', side_effect=fake_save), \
             mock.patch.object(font_module, 'build_opencc_char_table', return_value=[(ord('后'), ord('後')), (ord('来'), ord('來'))]), \
             mock.patch.object(font_module, 'build_opencc_word_table', return_value=[((ord('后'), ord('来')), (ord('後'), ord('來')))]):
            font_module.build_font('primary.ttf', 'out.ttf', fallback_font='fallback.ttf', config='s2t')

        self.assertEqual(len(saved_objs), 1)
        out = saved_objs[0]
        # Fallback's real 後 must be used instead of Variants.txt's 后
        self.assertEqual(out['cmap'][str(ord('後'))], 'g_hou_t_fb')
        self.assertEqual(out['GSUB']['lookups']['word2pseu']['subtables'][0]['substitutions'], [
            {'from': ['g_hou_s', 'g_lai_s'], 'to': 'pseu0'}
        ])
        self.assertEqual(out['GSUB']['lookups']['pseu2word']['subtables'][0]['pseu0'], ['g_hou_t_fb', 'g_lai_t_fb'])


if __name__ == '__main__':
    unittest.main()
