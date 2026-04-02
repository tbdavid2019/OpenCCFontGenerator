import argparse

from .font import build_font


def main():
    parser = argparse.ArgumentParser(description='OpenCC Font Generator')

    parser.add_argument('-i', '--input-file', type=str,
                        required=True, help='path to the source font file')
    parser.add_argument('-o', '--output-file', type=str,
                        required=True, help='path to the generated font file')
    parser.add_argument('-n', '--name-header-file',
                        type=str, required=False, help='path to the name header configuration file (in JSON format, optional)')
    parser.add_argument('--font-name', type=str,
                        required=False, help='the new font family name (used if -n is not provided)')
    parser.add_argument('--ttc-index', type=int,
                        help='the font index in a TrueType Collection (TTC) file')
    parser.add_argument('--font-version', type=float, required=False,
                        help='the version of the generated font file (optional, defaults to keeping original)')
    parser.add_argument(
        '--twp', action=argparse.BooleanOptionalAction, default=False, help='whether to convert with Taiwanese phrases (shorthand for --config twp)')
    parser.add_argument(
        '--config', type=str, default='s2t', choices=['s2t', 'twp', 's2hk', 's2tw', 't2s'],
        help='OpenCC configuration to use (default: s2t)')
    parser.add_argument(
        '--fallback-font', type=str, required=False,
        help='path to a secondary font to pull missing glyphs from')
    parser.add_argument(
        '--no-punc', action='store_true', default=False,
        help='whether to skip conversion for punctuation and non-Han characters')
    parser.add_argument(
        '--force-vertical', action=argparse.BooleanOptionalAction, default=False,
        help='whether to force vertical layout by swapping glyphs in cmap')
    parser.add_argument(
        '--woff2', action='store_true', default=False,
        help='whether to additionally output WOFF2 format')

    args = parser.parse_args()

    # Handle legacy --twp flag
    config = args.config
    if args.twp:
        config = 'twp'

    build_font(
        input_file=args.input_file,
        output_file=args.output_file,
        name_header_file=args.name_header_file,
        font_version=args.font_version,
        ttc_index=args.ttc_index,
        config=config,
        fallback_font=args.fallback_font,
        no_punc=args.no_punc,
        force_vertical=args.force_vertical,
        font_name=args.font_name,
        output_woff2=args.woff2,
    )


if __name__ == '__main__':
    main()
