from collections import defaultdict
from datetime import date
from itertools import chain, groupby
import json
import os
from os import path
import subprocess
import re
import tempfile

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None

HERE = path.abspath(path.dirname(__file__))

# Define the max entries size in a subtable.
SUBTABLE_MAX_COUNT = 4000

def grouper(iterable, n=SUBTABLE_MAX_COUNT):
    iterator = iter(iterable)
    while True:
        lst = []
        try:
            for _ in range(n):
                lst.append(next(iterator))
        except StopIteration:
            if lst:
                yield lst
            break
        yield lst

def grouper2(iterable, n=SUBTABLE_MAX_COUNT, key=None):
    for _, vx in groupby(iterable, key=key):
        for vs in grouper(vx, n):
            yield vs

# An opentype font can hold at most 65535 glyphs.
MAX_GLYPH_COUNT = 65535

def build_cmap_rev(obj):
    cmap_rev = defaultdict(list)
    for codepoint, glyph_name in obj['cmap'].items():
        cmap_rev[glyph_name].append(codepoint)
    return cmap_rev

def get_lookup_values(obj, table_name):
    '''Return lookup dictionaries for an OpenType table when present.'''
    table = obj.get(table_name)
    if not isinstance(table, dict):
        return ()
    lookups = table.get('lookups')
    if not isinstance(lookups, dict):
        return ()
    return lookups.values()

def load_font(path, ttc_index=None):
    '''Load a font as a JSON object.'''
    temp_ttf = None
    if path.lower().endswith('.woff2'):
        if TTFont is None:
            raise ImportError("Please install fonttools and brotli to support WOFF2: pip install fonttools brotli")
        print(f"Decompressing WOFF2 to temporary TTF: {path}")
        font = TTFont(path)
        fd, temp_ttf = tempfile.mkstemp(suffix='.ttf')
        os.close(fd)
        font.save(temp_ttf)
        path = temp_ttf

    ttc_index_args = () if ttc_index is None else ('--ttc-index', str(ttc_index))
    try:
        obj = json.loads(subprocess.check_output(
            ('otfccdump', path, *ttc_index_args)))
        obj['cmap_rev'] = build_cmap_rev(obj)
    finally:
        if temp_ttf and os.path.exists(temp_ttf):
            os.remove(temp_ttf)
            
    return obj

def save_font(obj, output_path, output_woff2=False):
    '''Save a font object to file.'''
    log_file = "opencc_gen_debug.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n--- Save Session: {date.today().isoformat()} ---\n")
        f.write(f"save_font called with output_path='{output_path}', output_woff2={output_woff2}\n")
        
        if 'cmap_rev' in obj:
            del obj['cmap_rev']
            
        f.write("Executing otfccbuild for TTF output...\n")
        result = subprocess.run(('otfccbuild', '-o', output_path),
                               input=json.dumps(obj), encoding='utf-8')
        
        if result.returncode == 0:
            f.write(f"TTF output successful: {output_path}\n")
        else:
            f.write(f"ERROR: otfccbuild failed with return code {result.returncode}\n")
        
        if output_woff2:
            f.write("WOFF2 output requested. Checking for fonttools...\n")
            if TTFont is None:
                f.write("CRITICAL ERROR: TTFont is None! fonttools or brotli is NOT installed in this environment.\n")
                return
                
            woff2_path = os.path.splitext(output_path)[0] + '.woff2'
            f.write(f"Target WOFF2 path: {woff2_path}\n")
            
            try:
                f.write(f"Compressing to WOFF2: {woff2_path} ...\n")
                # Using print here so user sees it in terminal too
                print(f"Compressing to WOFF2: {woff2_path} ...")
                font = TTFont(output_path)
                font.flavor = 'woff2'
                font.save(woff2_path)
                if os.path.exists(woff2_path):
                    f.write(f"WOFF2 compression completed successfully. File size: {os.path.getsize(woff2_path)} bytes\n")
                else:
                    f.write("ERROR: WOFF2 file was not created after font.save()\n")
            except Exception as e:
                f.write(f"CRITICAL ERROR: Failed to compress WOFF2: {str(e)}\n")
        else:
            f.write("output_woff2 is False, skipping WOFF2 compression.\n")

def codepoint_to_glyph_name(obj, codepoint):
    '''Convert a codepoint to a glyph name in a font.'''
    return obj['cmap'].get(str(codepoint))

def insert_empty_glyph(obj, name):
    '''Insert an empty glyph to a font with the given name.'''
    obj['glyf'][name] = {'advanceWidth': 0,
                         'advanceHeight': 1000, 'verticalOrigin': 880}
    obj['glyph_order'].append(name)

def get_glyph_count(obj):
    '''Get the total numbers of glyph in a font.'''
    return len(obj['glyph_order'])

def build_codepoints_han():
    '''Build a set of codepoints of Han characters to be included.'''
    with open(path.join(HERE, 'cache/code_points_han.txt')) as f:
        s = set()
        for line in f:
            s.add(int(line))
        return s

def build_codepoints_font(obj):
    '''Build a set of all the codepoints in a font.'''
    return set(map(int, obj['cmap']))

def build_codepoints_non_han():
    '''Build a set of codepoints of the needed non-Han characters in the final font.'''
    return set(chain(
        range(0x0020, 0x00FF + 1),
        range(0x02B0, 0x02FF + 1),
        range(0x2002, 0x203B + 1),
        range(0x2E00, 0x2E7F + 1),
        range(0x2E80, 0x2EFF + 1),
        range(0x3000, 0x301C + 1),
        range(0x3100, 0x312F + 1),
        range(0x3190, 0x31BF + 1),
        range(0xFE10, 0xFE1F + 1),
        range(0xFE30, 0xFE4F + 1),
        range(0xFF01, 0xFF5E + 1),
        range(0xFF5F, 0xFF60 + 1),
        range(0xFF61, 0xFF64 + 1),
    ))

def build_opencc_char_table(codepoints_font, config='s2t', fallback_font_obj=None):
    entries = []
    
    cache_file = path.join(HERE, f'cache/convert_table_chars_{config}.txt')
    if config == 's2t':
        cache_file = path.join(HERE, 'cache/convert_table_chars.txt')
    elif config == 'twp':
        cache_file = path.join(HERE, 'cache/convert_table_chars_twp.txt')

    if not path.exists(cache_file):
        # Fallback to s2t if config not found
        cache_file = path.join(HERE, 'cache/convert_table_chars.txt')

    with open(cache_file) as f:
        for line in f:
            k, v = line.rstrip('\n').split('\t')
            codepoint_k = ord(k)
            codepoint_v = ord(v)
            
            # Key must be in font. Value must be in font OR in fallback font
            if codepoint_k in codepoints_font:
                if codepoint_v in codepoints_font:
                    entries.append((codepoint_k, codepoint_v))
                elif fallback_font_obj and str(codepoint_v) in fallback_font_obj['cmap']:
                    entries.append((codepoint_k, codepoint_v))

    return entries

def build_opencc_word_table(codepoints_font, config='s2t', fallback_font_obj=None):
    entries = []
    
    cache_file = path.join(HERE, f'cache/convert_table_words_{config}.txt')
    if config == 's2t':
        cache_file = path.join(HERE, 'cache/convert_table_words.txt')
    elif config == 'twp':
        cache_file = path.join(HERE, 'cache/convert_table_words_twp.txt')

    if not path.exists(cache_file):
        cache_file = path.join(HERE, 'cache/convert_table_words.txt')

    with open(cache_file) as f:
        for line in f:
            k, v = line.rstrip('\n').split('\t')
            codepoints_k = tuple(ord(c) for c in k)
            codepoints_v = tuple(ord(c) for c in v)
            
            # Check if all keys are in font
            if all(cp in codepoints_font for cp in codepoints_k):
                # Check if all values are in font or fallback
                valid_v = True
                for cp in codepoints_v:
                    if cp not in codepoints_font:
                        if not fallback_font_obj or str(cp) not in fallback_font_obj['cmap']:
                            valid_v = False
                            break
                if valid_v:
                    entries.append((codepoints_k, codepoints_v))

    return entries

def disassociate_codepoint_and_glyph_name(obj, codepoint, glyph_name):
    del obj['cmap'][codepoint]
    is_only_item = obj['cmap_rev'][glyph_name] == [codepoint]
    if is_only_item:
        del obj['cmap_rev'][glyph_name]
    else:
        obj['cmap_rev'][glyph_name].remove(codepoint)
    return is_only_item

def remove_codepoint(obj, codepoint):
    codepoint = str(codepoint)
    glyph_name = obj['cmap'].get(codepoint)
    if not glyph_name:
        return
    is_only_item = disassociate_codepoint_and_glyph_name(obj, codepoint, glyph_name)
    if is_only_item:
        remove_glyph(obj, glyph_name)

def remove_codepoints(obj, codepoints):
    for codepoint in codepoints:
        remove_codepoint(obj, codepoint)

def remove_associated_codepoints_of_glyph(obj, glyph_name):
    for codepoint in obj['cmap_rev'][glyph_name]:
        del obj['cmap'][codepoint]
    del obj['cmap_rev'][glyph_name]

def remove_glyph(obj, glyph_name):
    try:
        obj['glyph_order'].remove(glyph_name)
    except ValueError:
        pass
    try:
        del obj['glyf'][glyph_name]
    except KeyError:
        pass
    for table in ['hmtx', 'vmtx', 'VORG']:
        if table in obj and glyph_name in obj[table]:
            del obj[table][glyph_name]
    for lookup in get_lookup_values(obj, 'GSUB'):
        if lookup['type'] == 'gsub_single':
            for subtable in lookup['subtables']:
                for k, v in list(subtable.items()):
                    if glyph_name == k or glyph_name == v:
                        del subtable[k]
        elif lookup['type'] == 'gsub_alternate':
            for subtable in lookup['subtables']:
                for k, v in list(subtable.items()):
                    if glyph_name == k or glyph_name in v:
                        del subtable[k]
        elif lookup['type'] == 'gsub_ligature':
            for subtable in lookup['subtables']:
                def predicate(item): return glyph_name not in item['from'] and glyph_name != item['to']
                subtable['substitutions'][:] = filter(predicate, subtable['substitutions'])
    for lookup in get_lookup_values(obj, 'GPOS'):
        if lookup['type'] == 'gpos_single':
            for subtable in lookup['subtables']:
                subtable.pop(glyph_name, None)
        elif lookup['type'] == 'gpos_pair':
            for subtable in lookup['subtables']:
                subtable['first'].pop(glyph_name, None)
                subtable['second'].pop(glyph_name, None)

def get_reachable_glyphs(obj):
    reachable_glyphs = {'.notdef', '.null'}
    for glyph_name in obj['cmap'].values():
        reachable_glyphs.add(glyph_name)
        for lookup in get_lookup_values(obj, 'GSUB'):
            if lookup['type'] == 'gsub_single':
                for subtable in lookup['subtables']:
                    for k, v in subtable.items():
                        if glyph_name == k:
                            reachable_glyphs.add(v)
            elif lookup['type'] == 'gsub_alternate':
                for subtable in lookup['subtables']:
                    for k, vs in subtable.items():
                        if glyph_name == k:
                            reachable_glyphs.update(vs)
            elif lookup['type'] == 'gsub_ligature':
                for subtable in lookup['subtables']:
                    for item in subtable['substitutions']:
                        if glyph_name in item['from']:
                            reachable_glyphs.add(item['to'])
    return reachable_glyphs

def clean_unused_glyphs(obj):
    reachable_glyphs = get_reachable_glyphs(obj)
    all_glyphs = set(obj['glyph_order'])
    for glyph_name in all_glyphs - reachable_glyphs:
        remove_associated_codepoints_of_glyph(obj, glyph_name)
        remove_glyph(obj, glyph_name)

def insert_empty_feature(obj, feature_name):
    if 'GSUB' not in obj:
        obj['GSUB'] = {'languages': {'DFLT_dflt': {'features': []}}, 'features': {}, 'lookups': {}, 'lookupOrder': []}
    for table in obj['GSUB']['languages'].values():
        if feature_name not in table['features']:
            table['features'].append(feature_name)
    obj['GSUB']['features'][feature_name] = []

def create_word2pseu_table(obj, feature_name, conversions):
    def conversion_item_len(conversion_item): return len(conversion_item[0])
    subtables = [{'substitutions': [{'from': glyph_names_k, 'to': pseudo_glyph_name} for glyph_names_k, pseudo_glyph_name in subtable]}
                 for subtable in grouper2(conversions, key=conversion_item_len)]
    obj['GSUB']['features'][feature_name].append('word2pseu')
    obj['GSUB']['lookups']['word2pseu'] = {
        'type': 'gsub_ligature',
        'flags': {},
        'subtables': subtables
    }
    obj['GSUB']['lookupOrder'].append('word2pseu')

def create_char2char_table(obj, feature_name, conversions):
    subtables = [{k: v for k, v in subtable}
                 for subtable in grouper(conversions)]
    obj['GSUB']['features'][feature_name].append('char2char')
    obj['GSUB']['lookups']['char2char'] = {
        'type': 'gsub_single',
        'flags': {},
        'subtables': subtables
    }
    obj['GSUB']['lookupOrder'].append('char2char')

def create_pseu2word_table(obj, feature_name, conversions):
    def conversion_item_len(conversion_item): return len(conversion_item[1])
    subtables = [{k: v for k, v in subtable}
                 for subtable in grouper2(conversions, key=conversion_item_len)]
    obj['GSUB']['features'][feature_name].append('pseu2word')
    obj['GSUB']['lookups']['pseu2word'] = {
        'type': 'gsub_multiple',
        'flags': {},
        'subtables': subtables
    }
    obj['GSUB']['lookupOrder'].append('pseu2word')

def modify_metadata(obj, name_header_file=None, font_version=None, font_name=None):
    if name_header_file and str(name_header_file).endswith('.json'):
        style = next(item['nameString']
                     for item in obj['name'] if item['nameID'] == 17)
        today = date.today().strftime('%b %d, %Y')
        if font_version is not None:
            name_header = build_name_header(name_header_file, style, str(font_version), today)
        else:
            name_header = build_name_header(name_header_file, style, "1.0", today)
        obj['name'] = name_header
    else:
        original_families = list(set(item['nameString'] for item in obj['name'] if item['nameID'] in (1, 16)))
        original_families.sort(key=len, reverse=True)
        if not font_name:
            font_name = f"{original_families[0]} TC" if original_families else "OpenCC TC"
        for item in obj['name']:
            for orig_fam in original_families:
                orig_fam_ps = orig_fam.replace(" ", "")
                font_name_ps = font_name.replace(" ", "")
                safe_font_name_ps = re.sub(r'[^A-Za-z0-9-]', '', font_name_ps)
                if not safe_font_name_ps:
                    safe_font_name_ps = "TC"
                if item['nameID'] in (1, 3, 4, 16):
                    if orig_fam in item['nameString']:
                        item['nameString'] = item['nameString'].replace(orig_fam, font_name)
                elif item['nameID'] == 6:
                    if orig_fam_ps in item['nameString']:
                        item['nameString'] = item['nameString'].replace(orig_fam_ps, safe_font_name_ps)
                    elif orig_fam in item['nameString']:
                        item['nameString'] = item['nameString'].replace(orig_fam, safe_font_name_ps).replace(" ", "-")
    if font_version is not None:
        obj['head']['fontRevision'] = font_version

def build_name_header(name_header_file, style, version, date):
    with open(name_header_file) as f:
        name_header = json.load(f)
    for item in name_header:
        item['nameString'] = item['nameString'] \
            .replace('<Typographic Subfamily Name>', style) \
            .replace('<Version>', version) \
            .replace('<Date>', date)
    return name_header

def apply_force_vertical(obj):
    if 'GSUB' not in obj or 'features' not in obj['GSUB'] or 'lookups' not in obj['GSUB']:
        return
    vert_lookups = []
    for feature_tag, feature in obj['GSUB']['features'].items():
        if feature_tag.strip() in ('vert', 'vrt2'):
            vert_lookups.extend(feature['lookups'])
    if not vert_lookups:
        return
    mapping = {}
    for lookup_id in vert_lookups:
        lookup = obj['GSUB']['lookups'].get(lookup_id)
        if not lookup or lookup['type'] != 'gsub_single':
            continue
        for subtable in lookup['subtables']:
            mapping.update(subtable)
    if not mapping:
        return
    for codepoint, glyph_name in list(obj['cmap'].items()):
        if glyph_name in mapping:
            vertical_glyph = mapping[glyph_name]
            obj['cmap'][codepoint] = vertical_glyph
            if glyph_name in obj['cmap_rev'] and codepoint in obj['cmap_rev'][glyph_name]:
                obj['cmap_rev'][glyph_name].remove(codepoint)
                if not obj['cmap_rev'][glyph_name]:
                    del obj['cmap_rev'][glyph_name]
            if vertical_glyph not in obj['cmap_rev']:
                obj['cmap_rev'][vertical_glyph] = []
            if codepoint not in obj['cmap_rev'][vertical_glyph]:
                obj['cmap_rev'][vertical_glyph].append(codepoint)

def merge_fallback_glyphs(primary_obj, fallback_obj, missing_codepoints):
    '''Merge missing glyphs from fallback font into primary font.'''
    for cp in missing_codepoints:
        cp_str = str(cp)
        if cp_str in fallback_obj['cmap']:
            glyph_name = fallback_obj['cmap'][cp_str]
            # Ensure unique name in primary
            new_glyph_name = f"fallback_{glyph_name}_{cp_str}"
            
            if new_glyph_name not in primary_obj['glyf']:
                primary_obj['glyf'][new_glyph_name] = fallback_obj['glyf'][glyph_name]
                primary_obj['glyph_order'].append(new_glyph_name)
                
                # Copy metrics
                for table in ['hmtx', 'vmtx', 'VORG']:
                    if table in fallback_obj and glyph_name in fallback_obj[table]:
                        if table not in primary_obj: primary_obj[table] = {}
                        primary_obj[table][new_glyph_name] = fallback_obj[table][glyph_name]

            # Update primary cmap
            primary_obj['cmap'][cp_str] = new_glyph_name
            if new_glyph_name not in primary_obj['cmap_rev']:
                primary_obj['cmap_rev'][new_glyph_name] = []
            primary_obj['cmap_rev'][new_glyph_name].append(cp_str)

def build_font(input_file, output_file, name_header_file=None, font_version=None, ttc_index=None, config='s2t', fallback_font=None, no_punc=False, force_vertical=False, font_name=None, twp=False, output_woff2=False):
    # Handle legacy twp flag if passed as boolean
    if twp and config == 's2t':
        config = 'twp'
        
    font = load_font(input_file, ttc_index=ttc_index)
    fallback_font_obj = None
    if fallback_font:
        print(f"Loading fallback font: {fallback_font}")
        fallback_font_obj = load_font(fallback_font)

    codepoints_font = build_codepoints_font(font)
    
    # Identify what characters are missing and see if they are in fallback
    entries_char_all = build_opencc_char_table(codepoints_font, config=config, fallback_font_obj=fallback_font_obj)
    entries_word_all = build_opencc_word_table(codepoints_font, config=config, fallback_font_obj=fallback_font_obj)

    # If we have fallback font, perform merging for missing characters
    if fallback_font_obj:
        needed_cps = set()
        for k, v in entries_char_all: needed_cps.add(v)
        for ks, vs in entries_word_all: 
            for v in vs: needed_cps.add(v)
        
        missing_cps = [cp for cp in needed_cps if cp not in codepoints_font]
        if missing_cps:
            print(f"Merging {len(missing_cps)} glyphs from fallback font...")
            merge_fallback_glyphs(font, fallback_font_obj, missing_cps)
            # Re-update codepoints_font after merging
            codepoints_font = build_codepoints_font(font)

    # Re-calculate entries after potential fallback merge to ensure codepoint_to_glyph_name works
    entries_char = build_opencc_char_table(codepoints_font, config=config)
    entries_word = build_opencc_word_table(codepoints_font, config=config)

    if no_punc:
        codepoints_non_han = build_codepoints_non_han()
        entries_char = [(k, v) for k, v in entries_char if k not in codepoints_non_han]
        entries_word = [(ks, vs) for ks, vs in entries_word if not any(k in codepoints_non_han for k in ks)]

    if force_vertical:
        apply_force_vertical(font)

    codepoints_final = (build_codepoints_non_han() | build_codepoints_han()) & codepoints_font
    remove_codepoints(font, codepoints_font - codepoints_final)
    clean_unused_glyphs(font)

    available_glyph_count = MAX_GLYPH_COUNT - get_glyph_count(font)
    assert available_glyph_count >= len(entries_word)

    word2pseu_table = []
    char2char_table = []
    pseu2word_table = []

    for i, (codepoints_k, codepoints_v) in enumerate(entries_word):
        pseudo_glyph_name = 'pseu%X' % i
        glyph_names_k = [codepoint_to_glyph_name(font, codepoint) for codepoint in codepoints_k]
        glyph_names_v = [codepoint_to_glyph_name(font, codepoint) for codepoint in codepoints_v]
        insert_empty_glyph(font, pseudo_glyph_name)
        word2pseu_table.append((glyph_names_k, pseudo_glyph_name))
        pseu2word_table.append((pseudo_glyph_name, glyph_names_v))

    for codepoint_k, codepoint_v in entries_char:
        glyph_name_k = codepoint_to_glyph_name(font, codepoint_k)
        glyph_name_v = codepoint_to_glyph_name(font, codepoint_v)
        char2char_table.append((glyph_name_k, glyph_name_v))

    feature_name = f'liga_{config}' if config != 's2t' else 'liga_s2t'
    insert_empty_feature(font, feature_name)
    create_word2pseu_table(font, feature_name, word2pseu_table)
    create_char2char_table(font, feature_name, char2char_table)
    create_pseu2word_table(font, feature_name, pseu2word_table)

    modify_metadata(font, name_header_file, font_version, font_name=font_name)
    save_font(font, output_file, output_woff2=output_woff2)
