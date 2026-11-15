from itertools import chain
from opencc import OpenCC
from os import makedirs, path
from setuptools import setup, find_packages
from urllib.request import urlretrieve

here = path.abspath(path.dirname(__file__))
pkgroot = path.join(here, 'src/OpenCCFontGenerator')
OPENCC_DATA_VERSION = '1.4.2'
OPENCC_DATA_VERSION_FILE = 'opencc_data/.opencc_data_version'
CACHE_VERSION_FILE = 'cache/.cache_version'


def file_exists(filename):
    return path.exists(path.join(pkgroot, filename))


def iter_opencc_dict(filepath):
    '''Yield (key, values_str) pairs from an OpenCC text dictionary, ignoring comments and blanks.'''
    with open(filepath, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            k, vx = line.split('\t', 1)
            yield k, vx


def _version_file_matches(relative_path, expected_version):
    version_path = path.join(pkgroot, relative_path)
    if not path.exists(version_path):
        return False
    with open(version_path, encoding='utf-8') as f:
        return f.read().strip() == expected_version


def is_opencc_data_current():
    return _version_file_matches(OPENCC_DATA_VERSION_FILE, OPENCC_DATA_VERSION)


def is_cache_current():
    return _version_file_matches(CACHE_VERSION_FILE, OPENCC_DATA_VERSION)


def download_data():
    '''
    Download necessary data for the package.
    Returns True if data was downloaded or refreshed.
    '''
    required_files = (
        'cache/通用規範漢字表.txt',
        'opencc_data/STCharacters.txt',
        'opencc_data/STPhrases.txt',
        'opencc_data/STPhrases_GeneratedFromRegionalPhrases.txt',
        'opencc_data/TSCharacters.txt',
        'opencc_data/TSPhrases.txt',
        'opencc_data/TWPhrases.txt',
        'opencc_data/TWVariants.txt',
        'opencc_data/TWVariantsPhrases.txt',
        'opencc_data/HKVariants.txt',
        'opencc_data/HKVariantsPhrases.txt',
    )

    if not is_opencc_data_current() or any(not file_exists(filename) for filename in required_files):

        makedirs(path.join(pkgroot, 'cache'), exist_ok=True)
        makedirs(path.join(pkgroot, 'opencc_data'), exist_ok=True)

        urlretrieve('https://raw.githubusercontent.com/rime-aca/character_set/e7d009a8a185a83f62ad2c903565b8bb85719221/%E9%80%9A%E7%94%A8%E8%A6%8F%E7%AF%84%E6%BC%A2%E5%AD%97%E8%A1%A8.txt',
                    path.join(pkgroot, 'cache/通用規範漢字表.txt'))

        def download_opencc_file(filename):
            opencc_data_url_prefix = f'https://cdn.jsdelivr.net/npm/opencc-data@{OPENCC_DATA_VERSION}/data/'
            urlretrieve(opencc_data_url_prefix + filename,
                        path.join(pkgroot, 'opencc_data', filename))

        for filename in (
            'STCharacters.txt',
            'STPhrases.txt',
            'STPhrases_GeneratedFromRegionalPhrases.txt',
            'TSCharacters.txt',
            'TSPhrases.txt',
            'TWPhrases.txt',
            'TWVariants.txt',
            'TWVariantsPhrases.txt',
            'HKVariants.txt',
            'HKVariantsPhrases.txt',
        ):
            download_opencc_file(filename)

        with open(path.join(pkgroot, OPENCC_DATA_VERSION_FILE), 'w', encoding='utf-8') as vf:
            vf.write(OPENCC_DATA_VERSION + '\n')
        return True
    return False


def build_convert_tables(force=False):
    '''
    Build necessary convert tables from OpenCC data.
    '''

    configs = ['s2t', 'twp', 's2hk', 's2tw', 't2s']
    
    # Initialize OpenCC converters
    converters = {
        's2t': OpenCC('s2t').convert,
        'twp': OpenCC(path.join(pkgroot, 't2twp.json')).convert, # Note: this is actually t2twp, used in setup.py logic
        's2hk': OpenCC('s2hk').convert,
        's2tw': OpenCC('s2tw').convert,
        't2s': OpenCC('t2s').convert,
    }
    
    # Internal helpers used by original logic
    t2s = OpenCC('t2s').convert
    t2twp = converters['twp']
    t2hk = OpenCC('t2hk').convert
    t2tw = OpenCC('t2tw').convert

    def build_entries(config='s2t'):
        if config in ('s2t', 'twp'):
            for dict_file in (
                'opencc_data/STCharacters.txt',
                'opencc_data/STPhrases.txt',
                'opencc_data/STPhrases_GeneratedFromRegionalPhrases.txt',
                'extra_convert_table.txt',
            ):
                for k, vx in iter_opencc_dict(path.join(pkgroot, dict_file)):
                    v = vx.split(' ')[0]
                    v = t2twp(v) if config == 'twp' else v
                    yield k, v

            if config == 'twp':
                for k, vx in iter_opencc_dict(path.join(pkgroot, 'opencc_data/TWVariants.txt')):
                    yield k, vx.split(' ')[0]
                for dict_file in (
                    'opencc_data/TWVariantsPhrases.txt',
                    'opencc_data/TWPhrases.txt',
                ):
                    for k, vx in iter_opencc_dict(path.join(pkgroot, dict_file)):
                        v = vx.split(' ')[0]
                        yield k, v
                        sk = t2s(k)
                        if sk != k:
                            yield sk, v
        
        elif config == 't2s':
            for dict_file in ('opencc_data/TSCharacters.txt', 'opencc_data/TSPhrases.txt'):
                for k, vx in iter_opencc_dict(path.join(pkgroot, dict_file)):
                    v = vx.split(' ')[0]
                    yield k, v
        
        elif config == 's2hk':
            for dict_file in (
                'opencc_data/STCharacters.txt',
                'opencc_data/STPhrases.txt',
                'opencc_data/STPhrases_GeneratedFromRegionalPhrases.txt',
            ):
                for k, vx in iter_opencc_dict(path.join(pkgroot, dict_file)):
                    v = t2hk(vx.split(' ')[0])
                    yield k, v
            for k, vx in iter_opencc_dict(path.join(pkgroot, 'extra_convert_table.txt')):
                yield k, vx.split(' ')[0]
            for k, vx in iter_opencc_dict(path.join(pkgroot, 'opencc_data/HKVariants.txt')):
                yield k, vx.split(' ')[0]
            for k, vx in iter_opencc_dict(path.join(pkgroot, 'opencc_data/HKVariantsPhrases.txt')):
                v = vx.split(' ')[0]
                yield k, v
                sk = t2s(k)
                if sk != k:
                    yield sk, v

        elif config == 's2tw':
            for dict_file in (
                'opencc_data/STCharacters.txt',
                'opencc_data/STPhrases.txt',
                'opencc_data/STPhrases_GeneratedFromRegionalPhrases.txt',
            ):
                for k, vx in iter_opencc_dict(path.join(pkgroot, dict_file)):
                    v = t2tw(vx.split(' ')[0])
                    yield k, v
            for k, vx in iter_opencc_dict(path.join(pkgroot, 'extra_convert_table.txt')):
                yield k, vx.split(' ')[0]
            for k, vx in iter_opencc_dict(path.join(pkgroot, 'opencc_data/TWVariants.txt')):
                yield k, vx.split(' ')[0]
            for k, vx in iter_opencc_dict(path.join(pkgroot, 'opencc_data/TWVariantsPhrases.txt')):
                v = vx.split(' ')[0]
                yield k, v
                sk = t2s(k)
                if sk != k:
                    yield sk, v

    def go(config='s2t'):
        cache_words = path.join(pkgroot, f'cache/convert_table_words_{config}.txt')
        cache_chars = path.join(pkgroot, f'cache/convert_table_chars_{config}.txt')
        
        # Legacy filenames for compatibility
        if config == 's2t':
            cache_words = path.join(pkgroot, 'cache/convert_table_words.txt')
            cache_chars = path.join(pkgroot, 'cache/convert_table_chars.txt')
        elif config == 'twp':
            cache_words = path.join(pkgroot, 'cache/convert_table_words_twp.txt')
            cache_chars = path.join(pkgroot, 'cache/convert_table_chars_twp.txt')

        if force or not path.exists(cache_words) or not path.exists(cache_chars):
            entries = dict(build_entries(config=config))
            single_char_keys = {k for k, v in entries.items() if len(k) == 1 and k != v}
            diff_phrases = {k for k, v in entries.items() if len(k) > 1 and k != v}
            sorted_entries = sorted(entries.items(), key=lambda k_v: (
                len(k_v[0]), k_v[0]), reverse=True)

            with open(cache_words, 'w', encoding='utf-8') as f1, \
                    open(cache_chars, 'w', encoding='utf-8') as f2:
                for k, v in sorted_entries:
                    if len(k) == 1:
                        if k != v:
                            print(k, v, sep='\t', file=f2)
                    else:
                        if k != v or any(c in single_char_keys for c in k) or any(
                            k[i:j] in diff_phrases
                            for i in range(len(k))
                            for j in range(i + 2, len(k) + 1)
                        ):
                            print(k, v, sep='\t', file=f1)

    for cfg in configs:
        go(cfg)


def build_codepoints(force=False):
    '''
    Determine the necessary codepoints for the font.
    '''

    if force or not file_exists('cache/code_points_han.txt'):
        s = set()

        with open(path.join(pkgroot, 'cache/通用規範漢字表.txt'), encoding='utf-8') as f:
            for line in f:
                if line and not line.startswith('#'):
                    c = line[0]
                    s.add(ord(c))

        for filename in (
            'STCharacters.txt', 'STPhrases.txt', 'STPhrases_GeneratedFromRegionalPhrases.txt',
            'TSCharacters.txt', 'TSPhrases.txt',
            'TWVariants.txt', 'TWVariantsPhrases.txt', 'TWPhrases.txt',
            'HKVariants.txt', 'HKVariantsPhrases.txt',
        ):
            for k, vx in iter_opencc_dict(path.join(pkgroot, 'opencc_data', filename)):
                vs = vx.split(' ')
                for c in k:
                    s.add(ord(c))
                for v in vs:
                    for c in v:
                        s.add(ord(c))

        for c in '妳攞噉㗎冚喺冇哋啲嘢啱佢嘅咁嚟屌咗撚噏瞓𡃁嘥掹孭氹詏噃𨳍掟埞曱甴𥄫𨳊嚿閪冧嬲卌嗻𧨾':
            s.add(ord(c))

        with open(path.join(pkgroot, 'cache/code_points_han.txt'), 'w', encoding='utf-8') as f:
            for cp in sorted(s):
                if cp > 128:  # remove letters in the dictionaries
                    print(cp, file=f)


data_updated = download_data()
cache_force = data_updated or not is_cache_current()
build_convert_tables(force=cache_force)
build_codepoints(force=cache_force)
if cache_force:
    with open(path.join(pkgroot, CACHE_VERSION_FILE), 'w', encoding='utf-8') as vf:
        vf.write(OPENCC_DATA_VERSION + '\n')

with open(path.join(here, 'README.md')) as f:
    long_description = f.read()

setup(
    name='OpenCCFontGenerator',
    version='0.0.1',
    description='The OpenCC Font Generator',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/ayaka14732/opencc-font-generator',
    author='ayaka14732',
    author_email='ayaka@mail.shn.hk',
    classifiers=[
                'Development Status :: 4 - Beta',
                'Intended Audience :: Developers',
                'Topic :: Software Development :: Libraries :: Python Modules',
                'Topic :: Text Processing :: Linguistic',
                'Natural Language :: Chinese (Simplified)',
                'Natural Language :: Chinese (Traditional)',
                'Programming Language :: Python :: 3',
                'Programming Language :: Python :: 3.8',
                'Programming Language :: Python :: 3.9',
                'Programming Language :: Python :: 3.10',
    ],
    keywords='chinese nlp natural-language-processing',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    package_data={
        'OpenCCFontGenerator': ['cache/*', 'opencc_data/*', 'extra_convert_table.txt', 't2twp.json'],
    },
    include_package_data=True,
    python_requires='>=3.8, <4',
    install_requires=[
        'opencc>=1.4.2',
        'fonttools>=4.62.1',
        'brotli',
    ],
    entry_points={},
    project_urls={
        'Bug Reports': 'https://github.com/ayaka14732/opencc-font-generator/issues',
        'Source': 'https://github.com/ayaka14732/opencc-font-generator',
    },
    zip_safe=False,
)
