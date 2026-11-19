"""Isolated subprocess worker executing a single font generation job."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from typing import Dict, List, Optional
import zipfile

from ..font import build_font
from ..run90 import process_rotation
from ..static_family import build_static_cjk_family
from ..webfont import process_webfont
from ..vf_family import build_variable_cjk_family


def _update_phase(phase_file: Path, phase: str) -> None:
    clean_phase = str(phase or '').strip()[:256] or 'running'
    phase_file.write_text(clean_phase, encoding='utf-8')


def _classify_artifact(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith('.zip'):
        return 'archive'
    if lower.endswith('.woff2'):
        return 'woff2'
    if lower.endswith('.css'):
        return 'css'
    if lower.endswith(('.ttf', '.otf', '.ttc')):
        return 'font'
    return 'other'


def _package_zip(zip_path: Path, files: List[Path], base_dir: Optional[Path] = None) -> Path:
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in files:
            arcname = str(file_path.relative_to(base_dir)) if base_dir else file_path.name
            zf.write(file_path, arcname=arcname)
    return zip_path


def _register_outputs(outputs_dir: Path, candidates: List[Path], primary_path: Path) -> List[dict]:
    artifacts = []
    seen = set()
    ordered = [primary_path, *[p for p in candidates if p != primary_path]]
    for file_path in ordered:
        resolved = file_path.resolve()
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        artifacts.append({
            'filename': resolved.name,
            'size_bytes': resolved.stat().st_size,
            'kind': _classify_artifact(resolved.name),
            'primary': resolved == primary_path.resolve(),
        })
    if not artifacts:
        raise RuntimeError('字型任務未產生任何有效輸出檔案。')
    return artifacts


def _run_convert(spec: dict, outputs_dir: Path, phase_file: Path) -> List[dict]:
    params = spec['params']
    source_path = Path(spec['input_file'])
    stem = source_path.stem
    ext = source_path.suffix.lower()
    if ext == '.woff2':
        ext = '.ttf'
    elif ext == '.ttc':
        ext = '.ttf'
    elif ext not in ('.ttf', '.otf'):
        ext = '.ttf'

    output_font = outputs_dir / f"{stem}_TC{ext}"
    _update_phase(phase_file, 'compiling_opencc_font')

    build_font(
        input_file=str(source_path),
        output_file=str(output_font),
        name_header_file=spec.get('name_header_file'),
        font_version=params.get('font_version'),
        ttc_index=params.get('ttc_index'),
        config=params.get('config', 's2t'),
        fallback_font=spec.get('fallback_font'),
        no_punc=bool(params.get('no_punc', False)),
        force_vertical=bool(params.get('force_vertical', False)),
        font_name=params.get('font_name'),
        output_woff2=bool(params.get('output_woff2', False)),
        merge_mode=params.get('merge_mode', 'opencc'),
        fill_charset=params.get('fill_charset', 'none'),
        kobo_mode=bool(params.get('kobo_mode', False)),
    )

    produced = [output_font]
    woff2_path = output_font.with_suffix('.woff2')
    if params.get('output_woff2') and woff2_path.exists():
        produced.append(woff2_path)

    primary = output_font
    if len(produced) > 1:
        _update_phase(phase_file, 'packaging_bundle')
        primary = _package_zip(outputs_dir / f"{stem}_TC_bundle.zip", produced)
        produced.append(primary)

    return _register_outputs(outputs_dir, produced, primary)


def _run_rotate90(spec: dict, outputs_dir: Path, phase_file: Path) -> List[dict]:
    params = spec['params']
    source_path = Path(spec['input_file'])
    stem = source_path.stem
    ext = source_path.suffix.lower()
    if ext == '.ttc':
        ext = '.ttf'
    elif ext not in ('.ttf', '.otf'):
        ext = '.ttf'

    direction = params.get('direction', 'ccw')
    suffix = 'Rotated90' if direction == 'cw' else 'Rotated90CCW'
    output_font = outputs_dir / f"{stem}_{suffix}{ext}"

    _update_phase(phase_file, 'rotating_glyphs_90')
    process_rotation(
        input_path=str(source_path),
        output_path=str(output_font),
        ttc_index=params.get('ttc_index'),
        rotate_all=bool(params.get('rotate_all', False)),
        direction=direction,
        kobo_mode=bool(params.get('kobo_mode', False)),
    )

    return _register_outputs(outputs_dir, [output_font], output_font)


def _run_webfont(spec: dict, outputs_dir: Path, phase_file: Path) -> List[dict]:
    params = spec['params']
    source_path = Path(spec['input_file'])
    output_woff2 = outputs_dir / f"{source_path.stem}.woff2"

    _update_phase(phase_file, 'converting_woff2')
    final_woff2, css_path = process_webfont(
        input_path=str(source_path),
        output_path=str(output_woff2),
        font_family=params.get('font_family') or None,
    )

    produced = [Path(final_woff2), Path(css_path)]
    _update_phase(phase_file, 'packaging_bundle')
    bundle = _package_zip(outputs_dir / f"{source_path.stem}_webfont.zip", produced)
    produced.append(bundle)

    return _register_outputs(outputs_dir, produced, bundle)


def _collect_output_files(output_dir: Path) -> List[Path]:
    return sorted(
        p for p in output_dir.iterdir()
        if p.is_file() and p.suffix.lower() in ('.ttf', '.otf', '.woff2', '.css')
    )


def _run_static_family(spec: dict, outputs_dir: Path, phase_file: Path) -> List[dict]:
    params = spec['params']
    batch_dir = outputs_dir / 'family_files'
    batch_dir.mkdir(parents=True, exist_ok=True)

    _update_phase(phase_file, 'building_static_family')
    build_static_cjk_family(
        input_path=spec['input_dir'],
        output_dir=str(batch_dir),
        fallback_dir=spec.get('fallback_dir'),
        fallback_prefix=params.get('fallback_prefix') or None,
        config=params.get('config', 's2t'),
        merge_mode=params.get('merge_mode', 'universal'),
        fill_charset=params.get('fill_charset', 'hant-common'),
        no_punc=bool(params.get('no_punc', False)),
        force_vertical=bool(params.get('force_vertical', False)),
        output_woff2=bool(params.get('output_woff2', False)),
        family_name_prefix=params.get('family_name_prefix') or None,
        kobo_mode=bool(params.get('kobo_mode', False)),
    )

    files = _collect_output_files(batch_dir)
    if not files:
        raise RuntimeError('靜態字型家族未產生任何輸出檔案。')

    _update_phase(phase_file, 'packaging_bundle')
    bundle = _package_zip(outputs_dir / 'static_family_TC.zip', files, base_dir=batch_dir)
    shutil.rmtree(batch_dir, ignore_errors=True)
    return _register_outputs(outputs_dir, [bundle], bundle)


def _run_variable_family(spec: dict, outputs_dir: Path, phase_file: Path) -> List[dict]:
    params = spec['params']
    batch_dir = outputs_dir / 'vf_files'
    batch_dir.mkdir(parents=True, exist_ok=True)

    _update_phase(phase_file, 'instantiating_variable_family')
    build_variable_cjk_family(
        input_file=spec['input_file'],
        output_dir=str(batch_dir),
        fallback_dir=spec['fallback_dir'],
        fallback_prefix=params.get('fallback_prefix') or 'NotoSansTC',
        config=params.get('config', 's2t'),
        output_woff2=bool(params.get('output_woff2', False)),
        family_name_prefix=params.get('family_name_prefix') or None,
        weights=params.get('weights') or None,
        kobo_mode=bool(params.get('kobo_mode', False)),
    )

    files = _collect_output_files(batch_dir)
    if not files:
        raise RuntimeError('可變字型家族未產生任何輸出檔案。')

    _update_phase(phase_file, 'packaging_bundle')
    bundle = _package_zip(outputs_dir / 'variable_family_TC.zip', files, base_dir=batch_dir)
    shutil.rmtree(batch_dir, ignore_errors=True)
    return _register_outputs(outputs_dir, [bundle], bundle)


MODE_RUNNERS = {
    'convert': _run_convert,
    'rotate90': _run_rotate90,
    'webfont': _run_webfont,
    'static-family': _run_static_family,
    'variable-family': _run_variable_family,
}


def run_job_spec(spec_path: Path) -> int:
    """Run a job spec JSON file inside an isolated working directory."""
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    job_dir = Path(spec['job_dir'])
    outputs_dir = job_dir / 'outputs'
    outputs_dir.mkdir(parents=True, exist_ok=True)
    phase_file = job_dir / 'phase.txt'
    result_file = job_dir / 'result.json'

    os.chdir(job_dir)
    runner = MODE_RUNNERS[spec['mode']]
    try:
        artifacts = runner(spec, outputs_dir, phase_file)
    finally:
        shutil.rmtree(job_dir / 'inputs', ignore_errors=True)
    result_file.write_text(json.dumps({'artifacts': artifacts}, ensure_ascii=False, indent=2), encoding='utf-8')
    _update_phase(phase_file, 'completed')
    return 0


def main() -> None:
    """CLI entrypoint invoked by JobManager."""
    if len(sys.argv) != 2:
        print('Usage: python -m OpenCCFontGenerator.web.worker <spec.json>', file=sys.stderr)
        sys.exit(2)
    sys.exit(run_job_spec(Path(sys.argv[1])))


if __name__ == '__main__':
    main()
