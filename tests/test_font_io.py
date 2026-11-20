import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from OpenCCFontGenerator import font as font_module
from OpenCCFontGenerator import run90 as run90_module
from OpenCCFontGenerator import static_family as static_family_module
from OpenCCFontGenerator import vf_family as vf_family_module
from OpenCCFontGenerator import webfont as webfont_module


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

    def test_build_font_auto_subsets_only_when_exceeding_max_glyph_count(self):
        # Extra CJK Extension B glyph outside OpenCC Han/non-Han cache pushes total > MAX_GLYPH_COUNT=5
        ext_b_cp = 0x20000
        font_obj = {
            'cmap': {
                str(ord('后')): 'g_hou_s',
                str(ord('来')): 'g_lai_s',
                str(ord('後')): 'g_hou_t',
                str(ord('來')): 'g_lai_t',
                str(ext_b_cp): 'g_ext_b',
            },
            'cmap_rev': {
                'g_hou_s': [str(ord('后'))],
                'g_lai_s': [str(ord('来'))],
                'g_hou_t': [str(ord('後'))],
                'g_lai_t': [str(ord('來'))],
                'g_ext_b': [str(ext_b_cp)],
            },
            'glyf': {
                '.notdef': {},
                'g_hou_s': {'contours': []},
                'g_lai_s': {'contours': []},
                'g_hou_t': {'contours': []},
                'g_lai_t': {'contours': []},
                'g_ext_b': {'contours': []},
            },
            'glyph_order': ['.notdef', 'g_hou_s', 'g_lai_s', 'g_hou_t', 'g_lai_t', 'g_ext_b'],
            'name': [{'platformID': 3, 'encodingID': 1, 'languageID': 1033, 'nameID': 1, 'nameString': 'BigCJK'}],
            'head': {'fontRevision': 1.0},
        }
        saved_objs = []
        with mock.patch.object(font_module, 'MAX_GLYPH_COUNT', 6), \
             mock.patch.object(font_module, 'load_font', return_value=font_obj), \
             mock.patch.object(font_module, 'save_font', side_effect=lambda obj, p, output_woff2=False: saved_objs.append(obj)), \
             mock.patch.object(font_module, 'build_opencc_char_table', return_value=[(ord('后'), ord('後')), (ord('来'), ord('來'))]), \
             mock.patch.object(font_module, 'build_opencc_word_table', return_value=[((ord('后'), ord('来')), (ord('後'), ord('來')))]):
            font_module.build_font('big.ttf', 'out.ttf', config='s2tw')

        out = saved_objs[0]
        # Unused Ext-B glyph removed cleanly, OpenCC glyphs + pseu0 retained within limit 6
        self.assertNotIn(str(ext_b_cp), out['cmap'])
        self.assertNotIn('g_ext_b', out['glyf'])
        self.assertLessEqual(len(out['glyph_order']), 6)
        self.assertIn('pseu0', out['glyf'])


class PreDeployFixTests(unittest.TestCase):
    def test_variant_dictionaries_exist(self):
        data_dir = Path(font_module.HERE) / 'opencc_data'
        for filename in ('Variants.txt', 'Var_tw.txt', 'Var_hk.txt'):
            self.assertTrue((data_dir / filename).is_file(), f'Missing variant table: {filename}')

    def test_static_family_preserves_cjk_fixes_extensions_and_deduplicates(self):
        self.assertEqual(static_family_module.sanitize_filename_part('思源黑體-Regular'), '思源黑體-Regular')
        self.assertEqual(static_family_module.sanitize_filename_part('../../bad..name'), 'bad_name')

        with tempfile.TemporaryDirectory() as directory:
            src_dir = Path(directory) / 'src'
            out_dir = Path(directory) / 'out'
            src_dir.mkdir()
            for fname in ('思源.ttf', '思源.woff2', '字型.ttc'):
                (src_dir / fname).write_bytes(b'dummy')

            called_outputs = []

            def fake_build_font(**kwargs):
                called_outputs.append(Path(kwargs['output_file']).name)

            with mock.patch.object(static_family_module, 'build_font', side_effect=fake_build_font):
                results = static_family_module.build_static_cjk_family(str(src_dir), str(out_dir))

            self.assertEqual(len(results), 3)
            self.assertEqual(set(called_outputs), {'字型_TC.ttf', '思源_TC.ttf', '思源_2_TC.ttf'})
            for name in called_outputs:
                self.assertTrue(name.endswith('.ttf'))

    def test_run90_save_font_json_raises_on_error_without_leaving_broken_file(self):
        with tempfile.TemporaryDirectory() as directory:
            out_path = Path(directory) / 'rotated.ttf'
            out_path.write_bytes(b'original-font')

            err = subprocess.CalledProcessError(1, ('otfccbuild',))
            with mock.patch.object(run90_module.subprocess, 'run', side_effect=err):
                with self.assertRaises(subprocess.CalledProcessError):
                    run90_module.save_font_json({'cmap': {}}, str(out_path))
            self.assertEqual(out_path.read_bytes(), b'original-font')

            missing_out = Path(directory) / 'missing_out.ttf'
            with mock.patch.object(run90_module.subprocess, 'run', return_value=subprocess.CompletedProcess(('otfccbuild',), 0)):
                with self.assertRaises(RuntimeError):
                    run90_module.save_font_json({'cmap': {}}, str(missing_out))
            self.assertFalse(missing_out.exists())
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['rotated.ttf'])

    def test_webfont_generate_css_template_escapes_special_chars(self):
        normal_css = webfont_module.generate_css_template('/tmp/MiniSpecimen.woff2', 'MiniSpecimen')
        self.assertIn("font-family: 'MiniSpecimen';", normal_css)
        self.assertIn("src: url('MiniSpecimen.woff2') format('woff2');", normal_css)

        tricky_css = webfont_module.generate_css_template("/tmp/a'b.woff2", "Bad'Font\\x\n\f*/body{}")
        self.assertIn("font-family: 'Bad\\'Font\\\\x *\\/body{}';", tricky_css)
        self.assertIn("src: url('a%27b.woff2') format('woff2');", tricky_css)
        self.assertNotIn("*/body{}", tricky_css)

    def test_ensure_gsub_feature_targets_merges_required_feature_without_duplicate(self):
        obj = {
            'GSUB': {
                'languages': {
                    'DFLT_dflt': {'requiredFeature': 'rlig_00001', 'features': ['rlig_00002', 'liga_00003']},
                },
                'features': {
                    'rlig_00001': ['req_lookup'],
                    'rlig_00002': ['opt_lookup'],
                    'liga_00003': ['liga_lookup'],
                },
                'lookups': {},
                'lookupOrder': ['req_lookup', 'opt_lookup', 'liga_lookup'],
            }
        }
        font_module.create_word2pseu_table(obj, ['liga', 'rlig'], [(['a', 'b'], 'pseu0')])
        dflt = obj['GSUB']['languages']['DFLT_dflt']
        self.assertEqual(dflt['requiredFeature'], 'rlig_00001')
        self.assertEqual(dflt['features'], ['liga_00003'])
        self.assertEqual(obj['GSUB']['features']['rlig_00001'], ['req_lookup', 'opt_lookup', 'word2pseu'])

    def test_apply_force_vertical_supports_indexed_feature_lists(self):
        obj = {
            'cmap': {str(ord('。')): 'period_h'},
            'cmap_rev': {'period_h': [str(ord('。'))]},
            'GSUB': {
                'features': {'vert_00001': ['vert_lookup']},
                'lookups': {
                    'vert_lookup': {
                        'type': 'gsub_single',
                        'subtables': [{'period_h': 'period_v'}],
                    }
                },
            },
        }
        font_module.apply_force_vertical(obj)
        self.assertEqual(obj['cmap'][str(ord('。'))], 'period_v')
        self.assertEqual(obj['cmap_rev']['period_v'], [str(ord('。'))])
        self.assertNotIn('period_h', obj['cmap_rev'])

    def test_clone_fallback_glyph_renames_colliding_glyphs(self):
        primary = {
            'glyf': {'.notdef': {}, 'gid10': {'contours': [[{'x': 0, 'y': 0, 'on': True}]]}},
            'glyph_order': ['.notdef', 'gid10'],
            'hmtx': {'gid10': {'advanceWidth': 500, 'lsb': 0}},
        }
        fallback = {
            'glyf': {'gid10': {'contours': [[{'x': 100, 'y': 200, 'on': True}]]}},
            'hmtx': {'gid10': {'advanceWidth': 1000, 'lsb': 50}},
        }
        cloned_map = {}
        cloned_name = font_module.clone_fallback_glyph(primary, fallback, 'gid10', cloned_map)
        self.assertEqual(cloned_name, 'fallback_gid10_1')
        self.assertEqual(primary['glyf']['gid10']['contours'][0][0]['x'], 0)
        self.assertEqual(primary['glyf']['fallback_gid10_1']['contours'][0][0]['x'], 100)
        self.assertEqual(primary['hmtx']['fallback_gid10_1']['advanceWidth'], 1000)

    def test_apply_variants_isolates_homograph_groups(self):
        obj = {
            'cmap': {
                str(ord('後')): 'g_hou_t',
                str(ord('面')): 'g_mian',
                str(ord('臺')): 'g_tai',
                str(ord('餘')): 'g_yu_t',
                str(ord('你')): 'g_ni',
            },
            'cmap_rev': {
                'g_hou_t': [str(ord('後'))],
                'g_mian': [str(ord('面'))],
                'g_tai': [str(ord('臺'))],
                'g_yu_t': [str(ord('餘'))],
                'g_ni': [str(ord('你'))],
            },
        }
        font_module.apply_variants(obj, config='s2t')
        self.assertNotIn(str(ord('后')), obj['cmap'])
        self.assertNotIn(str(ord('麵')), obj['cmap'])
        self.assertNotIn(str(ord('檯')), obj['cmap'])
        self.assertNotIn(str(ord('颱')), obj['cmap'])
        self.assertNotIn(str(ord('余')), obj['cmap'])
        self.assertEqual(obj['cmap'].get(str(ord('妳'))), 'g_ni')

        obj_noodle = {
            'cmap': {str(ord('麪')): 'g_noodle'},
            'cmap_rev': {'g_noodle': [str(ord('麪'))]},
        }
        font_module.apply_variants(obj_noodle, config='s2t')
        self.assertEqual(obj_noodle['cmap'].get(str(ord('麵'))), 'g_noodle')
        self.assertNotIn(str(ord('面')), obj_noodle['cmap'])

    def test_save_font_raises_when_woff2_compression_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            out_path = os.path.join(directory, 'out.ttf')
            prev_cwd = os.getcwd()
            os.chdir(directory)
            try:
                def fake_run(command, **kwargs):
                    Path(command[2]).write_bytes(b'built-ttf')
                    return subprocess.CompletedProcess(command, 0)

                class BrokenWoff2Font:
                    def save(self, _path):
                        raise OSError('woff2 encode error')
                    def close(self):
                        pass

                with mock.patch.object(font_module.subprocess, 'run', side_effect=fake_run), \
                     mock.patch.object(font_module, 'normalize_generated_font'), \
                     mock.patch.object(font_module, 'validate_font_output'), \
                     mock.patch.object(font_module, 'TTFont', return_value=BrokenWoff2Font()):
                    with self.assertRaises(OSError):
                        font_module.save_font({'cmap': {}, 'cmap_rev': {}}, out_path, output_woff2=True)
                self.assertFalse(Path(directory, 'out.woff2').exists())
            finally:
                os.chdir(prev_cwd)

    def test_static_family_weight_alias_prefix_and_woff2_stem_dedup(self):
        self.assertEqual(static_family_module.detect_weight_from_filename('MyFont-ExtraBold.ttf'), 'ExtraBold')
        self.assertEqual(static_family_module.detect_weight_from_filename('MyFont-SemiBold.otf'), 'SemiBold')

        with tempfile.TemporaryDirectory() as directory:
            src_dir = Path(directory) / 'src'
            fb_dir = Path(directory) / 'fb'
            out_dir = Path(directory) / 'out'
            src_dir.mkdir()
            fb_dir.mkdir()
            out_dir.mkdir()
            (src_dir / 'Font.ttf').write_bytes(b'ttf')
            (src_dir / 'Font.otf').write_bytes(b'otf')
            (fb_dir / 'Other-Regular.ttf').write_bytes(b'fb')

            with self.assertRaises(ValueError):
                static_family_module.collect_fallback_candidates(str(fb_dir), fallback_prefix='NotoSansTC')

            called = []
            with mock.patch.object(static_family_module, 'build_font', side_effect=lambda **kw: called.append(kw['output_file'])):
                results = static_family_module.build_static_cjk_family(str(src_dir), str(out_dir), output_woff2=True)
            stems = {Path(r['output_file']).stem for r in results}
            woff2s = {Path(r['woff2_file']).name for r in results}
            self.assertEqual(stems, {'Font_TC', 'Font_2_TC'})
            self.assertEqual(woff2s, {'Font_TC.woff2', 'Font_2_TC.woff2'})
            self.assertEqual(len(called), 2)

    def test_run90_composite_rotation_and_glyph_advance_width(self):
        # UPM=2000 -> center=(1000, 1000). Verify advanceWidth and composite math for cw rotation.
        base_pt = (400, 600)
        M = ((1.5, 0.0), (0.0, 0.5))
        T = (100, 200)
        # Original composite world point: M * base_pt + T = (700, 500)
        # CW around (1000, 1000): (y - 1000 + 1000, -(x - 1000) + 1000) = (500, 1300)
        font_obj = {
            'head': {'unitsPerEm': 2000},
            'OS/2': {},
            'hhea': {},
            'name': [{'nameID': 1, 'nameString': 'TestRot'}],
            'cmap': {str(ord('漢')): 'han_base', str(ord('字')): 'han_comp', str(ord('A')): 'latin_comp'},
            'hmtx': {
                'han_base': {'advanceWidth': 1200, 'lsb': 10},
                'han_comp': {'advanceWidth': 1200, 'lsb': 10},
                'latin_comp': {'advanceWidth': 900, 'lsb': 20},
            },
            'glyf': {
                'han_base': {'contours': [[{'x': base_pt[0], 'y': base_pt[1], 'on': True}]]},
                'han_comp': {'references': [{'glyph': 'han_base', 'x': T[0], 'y': T[1], 'a': M[0][0], 'b': M[0][1], 'c': M[1][0], 'd': M[1][1]}]},
                'latin_comp': {'references': [{'glyph': 'han_base', 'x': T[0], 'y': T[1], 'a': M[0][0], 'b': M[0][1], 'c': M[1][0], 'd': M[1][1]}]},
            },
        }
        saved = []
        with mock.patch.object(run90_module, 'load_font_json', return_value=font_obj), \
             mock.patch.object(run90_module, 'save_font_json', side_effect=lambda obj, out: saved.append(obj)):
            run90_module.process_rotation('in.ttf', 'out.ttf', direction='cw')

        out = saved[0]
        self.assertEqual(out['glyf']['han_base']['advanceWidth'], 2000)
        self.assertNotIn('advanceWidth', out['glyf']['latin_comp'])
        self.assertEqual(out['hmtx']['latin_comp']['advanceWidth'], 900)
        self.assertEqual(out['OS/2']['usWinAscent'], 2000)
        self.assertEqual(out['hhea']['ascent'], 2000)

        # Rotated han_base point: (600, 1600)
        rot_base_pt = (out['glyf']['han_base']['contours'][0][0]['x'], out['glyf']['han_base']['contours'][0][0]['y'])
        self.assertEqual(rot_base_pt, (600, 1600))

        # Both han_comp and han_base rotated -> transformed rot_base_pt must equal R_cw(700, 500) = (500, 1300)
        r_han = out['glyf']['han_comp']['references'][0]
        px = r_han['a'] * rot_base_pt[0] + r_han['b'] * rot_base_pt[1] + r_han['x']
        py = r_han['c'] * rot_base_pt[0] + r_han['d'] * rot_base_pt[1] + r_han['y']
        self.assertAlmostEqual(px, 500)
        self.assertAlmostEqual(py, 1300)

        # latin_comp NOT rotated while han_base IS rotated -> must recover original world point (700, 500)
        r_lat = out['glyf']['latin_comp']['references'][0]
        lx = r_lat['a'] * rot_base_pt[0] + r_lat['b'] * rot_base_pt[1] + r_lat['x']
        ly = r_lat['c'] * rot_base_pt[0] + r_lat['d'] * rot_base_pt[1] + r_lat['y']
        self.assertAlmostEqual(lx, 700)
        self.assertAlmostEqual(ly, 500)

    def test_vf_family_validates_wght_bounds_and_handles_missing_stat(self):
        from fontTools.fontBuilder import FontBuilder
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        from fontTools.ttLib.tables.TupleVariation import TupleVariation

        with tempfile.TemporaryDirectory() as directory:
            vf_path = Path(directory) / 'MiniVF.ttf'
            fb_dir = Path(directory) / 'fb'
            out_dir = Path(directory) / 'out'
            fb_dir.mkdir()
            (fb_dir / 'NotoSansTC-Regular.ttf').write_bytes(b'fb')
            (fb_dir / 'NotoSansTC-Black.ttf').write_bytes(b'fb')

            fb = FontBuilder(1000, isTTF=True)
            fb.setupGlyphOrder(['.notdef', 'A'])
            fb.setupCharacterMap({65: 'A'})
            glyf_map = {}
            metrics = {}
            for name in ('.notdef', 'A'):
                pen = TTGlyphPen(None)
                pen.moveTo((100, 0)); pen.lineTo((100, 700)); pen.lineTo((600, 700)); pen.lineTo((600, 0)); pen.closePath()
                glyf_map[name] = pen.glyph()
                metrics[name] = (700, 100)
            fb.setupGlyf(glyf_map)
            fb.setupHorizontalMetrics(metrics)
            fb.setupHorizontalHeader(ascent=850, descent=-150)
            fb.setupNameTable({'familyName': 'MiniVF', 'styleName': 'Regular'})
            fb.setupOS2()
            fb.setupPost()
            fb.setupFvar(axes=[('wght', 300, 400, 700, 'Weight')], instances=[])
            fb.setupGvar({'.notdef': [], 'A': [TupleVariation({'wght': (0.0, 1.0, 1.0)}, [(50, 0), (50, 0), (100, 0), (100, 0), (0, 0), (0, 0), (0, 0), (0, 0)])]})
            fb.font.save(str(vf_path))
            fb.font.close()

            inst_out = Path(directory) / 'inst_bold.ttf'
            vf_family_module.instantiate_variable_font(str(vf_path), str(inst_out), {'wght': 700})
            self.assertTrue(inst_out.is_file())

            with self.assertRaises(ValueError):
                vf_family_module.build_variable_cjk_family(
                    str(vf_path), str(out_dir), str(fb_dir), weights=['Black'],
                )


if __name__ == '__main__':
    unittest.main()
