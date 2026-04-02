import json
import os
import subprocess
import tempfile
import sys

def load_font_json(path, ttc_index=None):
    '''Load a font as a JSON object via otfccdump.'''
    ttc_index_args = () if ttc_index is None else ('--ttc-index', str(ttc_index))
    print(f"Loading font via otfccdump: {path}")
    return json.loads(subprocess.check_output(
        ('otfccdump', path, *ttc_index_args)))

def save_font_json(obj, output_path):
    '''Save a font object to file via otfccbuild.'''
    print(f"Saving font via otfccbuild: {output_path}")
    subprocess.run(('otfccbuild', '-o', output_path),
                   input=json.dumps(obj), encoding='utf-8')

def rotate_glyph_90(glyph, center_x=500, center_y=500, direction='cw'):
    '''Rotate a single glyph 90 degrees around (center_x, center_y).'''
    
    # 順時針 90 度: (x, y) -> ((y - cy) + cx, -(x - cx) + cy)
    # 逆時針 90 度: (x, y) -> (-(y - cy) + cx, (x - cx) + cy)
    def rot(x, y):
        if direction == 'cw':
            return (y - center_y) + center_x, -(x - center_x) + center_y
        else:
            return -(y - center_y) + center_x, (x - center_x) + center_y

    # 處理輪廓 (Contours)
    if 'contours' in glyph:
        for contour in glyph['contours']:
            for point in contour:
                point['x'], point['y'] = rot(point['x'], point['y'])
                
    # 處理複合字元 (References)
    if 'references' in glyph:
        for ref in glyph['references']:
            # 1. 旋轉組件的偏移位置 (x, y)
            orig_x = ref.get('x', 0)
            orig_y = ref.get('y', 0)
            ref['x'], ref['y'] = rot(orig_x, orig_y)
            
            # 2. 旋轉組件的變換矩陣 (Scale/Skew)
            a = ref.get('a', 1)
            b = ref.get('b', 0)
            c = ref.get('c', 0)
            d = ref.get('d', 1)
            
            if direction == 'cw':
                ref['a'], ref['b'], ref['c'], ref['d'] = d, -c, b, a
            else:
                ref['a'], ref['b'], ref['c'], ref['d'] = d, c, -b, a

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

def process_rotation(input_path, output_path, ttc_index=None, center_x=500, center_y=500, rotate_all=False, direction='ccw'):
    font = load_font_json(input_path, ttc_index=ttc_index)
    
    cmap_rev = build_cmap_rev(font)
    han_codepoints = build_codepoints_han() if not rotate_all else set()

    def should_rotate(name):
        if rotate_all:
            return True
        # 檢查該字形對應的所有編碼中，是否有任何一個是漢字
        codepoints = cmap_rev.get(name, [])
        return any(cp in han_codepoints for cp in codepoints)

    print(f"Processing 90-degree {'clockwise' if direction == 'cw' else 'counter-clockwise'} rotation...")
    
    count = 0
    for name, glyph in font['glyf'].items():
        if should_rotate(name):
            rotate_glyph_90(glyph, center_x, center_y, direction=direction)
            count += 1
        
        # 調整度量: 寬度統一設為 1000
        if 'hmtx' in font and name in font['hmtx']:
            font['hmtx'][name]['advanceWidth'] = 1000
            font['hmtx'][name]['lsb'] = 0
            
    print(f"Rotated {count} glyphs.")
            
    # 修正字型全域度量 (OS/2, hhea) 以防止裁剪
    if 'OS/2' in font:
        font['OS/2']['sTypoAscender'] = 1000
        font['OS/2']['sTypoDescender'] = 0
        font['OS/2']['usWinAscent'] = 1000
        font['OS/2']['usWinDescent'] = 0
        
    if 'hhea' in font:
        font['hhea']['ascent'] = 1000
        font['hhea']['descent'] = 0

    # 修改名稱
    suffix = "Rotated90" if direction == 'cw' else "Rotated90CCW"
    for item in font['name']:
        if item['nameID'] in (1, 3, 4, 16):
            item['nameString'] += f" {suffix}"
            
    save_font_json(font, output_path)
    print(f"✅ Successfully created rotated font: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run90.py input.ttf output.ttf")
        sys.exit(1)
    process_rotation(sys.argv[1], sys.argv[2])
