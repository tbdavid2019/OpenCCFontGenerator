import json
import os
import subprocess
import tempfile
import sys

from .font import apply_kobo_compatibility

def load_font_json(path, ttc_index=None):
    '''Load a font as a JSON object via otfccdump.'''
    if ttc_index is None and str(path).lower().endswith(('.ttc', '.otc')):
        ttc_index = 0
    ttc_index_args = () if ttc_index is None else ('--ttc-index', str(ttc_index))
    print(f"Loading font via otfccdump: {path}")
    return json.loads(subprocess.check_output(
        ('otfccdump', path, *ttc_index_args)))

def save_font_json(obj, output_path):
    '''Save a font object to file via otfccbuild.'''
    print(f"Saving font via otfccbuild: {output_path}")
    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)
    suffix = os.path.splitext(output_path)[1] or '.ttf'
    fd, built_path = tempfile.mkstemp(dir=output_dir, suffix=suffix)
    os.close(fd)
    os.remove(built_path)

    try:
        subprocess.run(
            ('otfccbuild', '-o', built_path),
            input=json.dumps(obj),
            encoding='utf-8',
            check=True,
        )
        if not os.path.isfile(built_path) or os.path.getsize(built_path) == 0:
            raise RuntimeError(f"otfccbuild did not produce a valid output file: {output_path}")
        os.replace(built_path, output_path)
    finally:
        if os.path.exists(built_path):
            os.remove(built_path)

def _rotation_matrix(direction):
    if direction == 'cw':
        return ((0, 1), (-1, 0))
    return ((0, -1), (1, 0))


def _mat_mul(m1, m2):
    return (
        (m1[0][0] * m2[0][0] + m1[0][1] * m2[1][0], m1[0][0] * m2[0][1] + m1[0][1] * m2[1][1]),
        (m1[1][0] * m2[0][0] + m1[1][1] * m2[1][0], m1[1][0] * m2[0][1] + m1[1][1] * m2[1][1]),
    )


def _mat_vec(m, v):
    return (
        m[0][0] * v[0] + m[0][1] * v[1],
        m[1][0] * v[0] + m[1][1] * v[1],
    )


def _clean_number(value):
    if isinstance(value, (int, float)):
        rounded = round(value)
        if abs(value - rounded) < 1e-9:
            return int(rounded)
        return round(value, 6)
    return value


def _apply_composite_rotation(ref, glyph_rotated, comp_rotated, center_x, center_y, direction):
    '''Update a composite reference affine transform for rotated glyph and/or component.'''
    if not glyph_rotated and not comp_rotated:
        return

    A = _rotation_matrix(direction)
    A_inv = _rotation_matrix('ccw' if direction == 'cw' else 'cw')
    M = ((ref.get('a', 1), ref.get('b', 0)), (ref.get('c', 0), ref.get('d', 1)))
    T = (ref.get('x', 0), ref.get('y', 0))
    C = (center_x, center_y)

    AC = _mat_vec(A, C)
    t_rot = (C[0] - AC[0], C[1] - AC[1])
    AinvC = _mat_vec(A_inv, C)
    t_inv = (C[0] - AinvC[0], C[1] - AinvC[1])

    if glyph_rotated and comp_rotated:
        M_new = _mat_mul(_mat_mul(A, M), A_inv)
        Mt = _mat_vec(M, t_inv)
        inner = (Mt[0] + T[0], Mt[1] + T[1])
        A_inner = _mat_vec(A, inner)
        T_new = (A_inner[0] + t_rot[0], A_inner[1] + t_rot[1])
    elif glyph_rotated:
        M_new = _mat_mul(A, M)
        AT = _mat_vec(A, T)
        T_new = (AT[0] + t_rot[0], AT[1] + t_rot[1])
    else:
        M_new = _mat_mul(M, A_inv)
        Mt = _mat_vec(M, t_inv)
        T_new = (Mt[0] + T[0], Mt[1] + T[1])

    ref['a'] = _clean_number(M_new[0][0])
    ref['b'] = _clean_number(M_new[0][1])
    ref['c'] = _clean_number(M_new[1][0])
    ref['d'] = _clean_number(M_new[1][1])
    ref['x'] = _clean_number(T_new[0])
    ref['y'] = _clean_number(T_new[1])


def rotate_glyph_90(glyph, center_x=500, center_y=500, direction='cw', rotated_glyphs=None, glyph_rotated=True):
    '''Rotate a single glyph 90 degrees around (center_x, center_y).'''

    # 順時針 90 度: (x, y) -> ((y - cy) + cx, -(x - cx) + cy)
    # 逆時針 90 度: (x, y) -> (-(y - cy) + cx, (x - cx) + cy)
    def rot(x, y):
        if direction == 'cw':
            return _clean_number((y - center_y) + center_x), _clean_number(-(x - center_x) + center_y)
        return _clean_number(-(y - center_y) + center_x), _clean_number((x - center_x) + center_y)

    # 處理輪廓 (Contours)
    if glyph_rotated and 'contours' in glyph:
        for contour in glyph['contours']:
            for point in contour:
                point['x'], point['y'] = rot(point['x'], point['y'])

    # 處理複合字元 (References)
    if 'references' in glyph:
        for ref in glyph['references']:
            comp_name = ref.get('glyph') or ref.get('name') or ref.get('to') or ref.get('refGlyph') or ref.get('glyphName')
            comp_rotated = bool(rotated_glyphs and comp_name in rotated_glyphs)
            _apply_composite_rotation(ref, glyph_rotated, comp_rotated, center_x, center_y, direction)

def build_cmap_rev(obj):
    cmap_rev = {}
    for codepoint, glyph_name in obj['cmap'].items():
        if glyph_name not in cmap_rev:
            cmap_rev[glyph_name] = []
        cmap_rev[glyph_name].append(int(codepoint))
    return cmap_rev

def build_codepoints_han():
    '''Build a set of codepoints of Han characters and Bopomofo from cache.'''
    here = os.path.dirname(__file__)
    cache_path = os.path.join(here, 'cache/code_points_han.txt')
    s = set()
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            for line in f:
                if line.strip():
                    s.add(int(line))
    else:
        print(f"Warning: {cache_path} not found. Han-only rotation might be incomplete.")
    
    # 加入注音符號範圍 (Zhuyin Fuhao)
    # 3100–312F: Bopomofo
    # 31A0–31BF: Bopomofo Extended
    s.update(range(0x3100, 0x312F + 1))
    s.update(range(0x31A0, 0x31BF + 1))
    
    return s

def process_rotation(input_path, output_path, ttc_index=None, center_x=None, center_y=None, rotate_all=False, direction='ccw', kobo_mode=False):
    font = load_font_json(input_path, ttc_index=ttc_index)
    units_per_em = int(font.get('head', {}).get('unitsPerEm') or 1000)
    cx = units_per_em / 2 if center_x is None else center_x
    cy = units_per_em / 2 if center_y is None else center_y

    cmap_rev = build_cmap_rev(font)
    han_codepoints = build_codepoints_han() if not rotate_all else set()

    def should_rotate(name):
        if rotate_all:
            return True
        # 檢查該字形對應的所有編碼中，是否有任何一個是漢字
        codepoints = cmap_rev.get(name, [])
        return any(cp in han_codepoints for cp in codepoints)

    print(f"Processing 90-degree {'clockwise' if direction == 'cw' else 'counter-clockwise'} rotation...")

    rotated_glyphs = {name for name in font['glyf'] if should_rotate(name)}
    count = len(rotated_glyphs)
    for name, glyph in font['glyf'].items():
        glyph_rotated = name in rotated_glyphs
        if glyph_rotated or 'references' in glyph:
            rotate_glyph_90(
                glyph,
                cx,
                cy,
                direction=direction,
                rotated_glyphs=rotated_glyphs,
                glyph_rotated=glyph_rotated,
            )

        if glyph_rotated:
            # otfccbuild reads advanceWidth from glyf entries to reconstruct hmtx
            glyph['advanceWidth'] = units_per_em
            if 'hmtx' in font and name in font['hmtx']:
                font['hmtx'][name]['advanceWidth'] = units_per_em
                font['hmtx'][name]['lsb'] = 0

    print(f"Rotated {count} glyphs.")

    # 修正字型全域度量 (OS/2, hhea) 以防止裁剪
    if 'OS/2' in font:
        font['OS/2']['sTypoAscender'] = units_per_em
        font['OS/2']['sTypoDescender'] = 0
        font['OS/2']['usWinAscent'] = units_per_em
        font['OS/2']['usWinDescent'] = 0

    if 'hhea' in font:
        font['hhea']['ascent'] = units_per_em
        font['hhea']['descent'] = 0

    # 修改名稱
    suffix = "Rotated90" if direction == 'cw' else "Rotated90CCW"
    for item in font['name']:
        if item['nameID'] in (1, 3, 4, 16):
            item['nameString'] += f" {suffix}"
            
    if kobo_mode:
        apply_kobo_compatibility(font)
            
    save_font_json(font, output_path)
    print(f"✅ Successfully created rotated font: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run90.py input.ttf output.ttf")
        sys.exit(1)
    process_rotation(sys.argv[1], sys.argv[2])
