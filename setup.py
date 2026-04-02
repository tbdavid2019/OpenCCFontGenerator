from itertools import chain
from opencc import OpenCC
from os import makedirs, path
from setuptools import setup, find_packages
from urllib.request import urlretrieve

here = path.abspath(path.dirname(__file__))
pkgroot = path.join(here, 'src/OpenCCFontGenerator')


def file_exists(filename):
    return path.exists(path.join(pkgroot, filename))


def download_data():
    '''
    Download necessary data for the package.
    '''

    if any(not file_exists(filename) for filename in (
        'cache/通用規範漢字表.txt',
        'opencc_data/STCharacters.txt',
        'opencc_data/STPhrases.txt',
        'opencc_data/TSCharacters.txt',
        'opencc_data/TSPhrases.txt',
        'opencc_data/TWPhrasesIT.txt',
        'opencc_data/TWPhrasesName.txt',
        'opencc_data/TWPhrasesOther.txt',
        'opencc_data/TWVariants.txt',
        'opencc_data/HKVariants.txt',
        'opencc_data/TWPhrases.txt',
    )):

        makedirs(path.join(pkgroot, 'cache'), exist_ok=True)
        makedirs(path.join(pkgroot, 'opencc_data'), exist_ok=True)

        urlretrieve('https://raw.githubusercontent.com/rime-aca/character_set/e7d009a8a185a83f62ad2c903565b8bb85719221/%E9%80%9A%E7%94%A8%E8%A6%8F%E7%AF%84%E6%BC%A2%E5%AD%97%E8%A1%A8.txt',
                    path.join(pkgroot, 'cache/通用規範漢字表.txt'))

        def download_opencc_file(filename):
            opencc_data_url_prefix = 'https://cdn.jsdelivr.net/npm/opencc-data@1.0.6/data/'
            urlretrieve(opencc_data_url_prefix + filename,
                        path.join(pkgroot, 'opencc_data', filename))

        for filename in (
            'STCharacters.txt',
            'STPhrases.txt',
            'TSCharacters.txt',
            'TSPhrases.txt',
            'TWPhrasesIT.txt',
            'TWPhrasesName.txt',
            'TWPhrasesOther.txt',
            'TWVariants.txt',
            'HKVariants.txt',
        ):
            download_opencc_file(filename)

        # Combine three TW phrases files into one
        with open(path.join(pkgroot, 'opencc_data/TWPhrasesIT.txt')) as f1, \
                open(path.join(pkgroot, 'opencc_data/TWPhrasesName.txt')) as f2, \
                open(path.join(pkgroot, 'opencc_data/TWPhrasesOther.txt')) as f3, \
                open(path.join(pkgroot, 'opencc_data/TWPhrases.txt'), 'w') as g:
            g.write(f1.read())
            g.write(f2.read())
            g.write(f3.read())


def build_convert_tables():
    '''
    Build necessary convert tables from OpenCC data.
    '''

    configs = ['s2t', 'twp', 's2hk', 's2tw', 't2s']
    
    # Initialize OpenCC converters
    converters = {
        's2t': OpenCC('s2t').convert,
        'twp': OpenCC(path.join(pkgroot, 't2twp')).convert, # Note: this is actually t2twp, used in setup.py logic
        's2hk': OpenCC('s2hk').convert,
        's2tw': OpenCC('s2tw').convert,
        't2s': OpenCC('t2s').convert,
    }
    
    # Internal helpers used by original logic
    t2s = OpenCC('t2s').convert
    t2twp = converters['twp']

    def build_entries(config='s2t'):
        if config in ('s2t', 'twp'):
            with open(path.join(pkgroot, 'opencc_data/STCharacters.txt')) as f1, \
                    open(path.join(pkgroot, 'opencc_data/STPhrases.txt')) as f2, \
                    open(path.join(pkgroot, 'extra_convert_table.txt')) as f3:
                for line in chain(f1, f2, f3):
                    k, vx = line.rstrip('\n').split('\t')
                    v = vx.split(' ')[0]
                    v = t2twp(v) if config == 'twp' else v
                    yield k, v

            if config == 'twp':
                with open(path.join(pkgroot, 'opencc_data/TWVariants.txt')) as f:
                    for line in f:
                        k, vx = line.rstrip('\n').split('\t')
                        v = vx.split(' ')[0]
                        k = t2s(k)
                        yield k, v
                with open(path.join(pkgroot, 'opencc_data/TWPhrases.txt')) as f:
                    for line in f:
                        k, vx = line.rstrip('\n').split('\t')
                        v = vx.split(' ')[0]
                        k = t2s(k)
                        yield k, v
        
        elif config == 't2s':
            with open(path.join(pkgroot, 'opencc_data/TSCharacters.txt')) as f1, \
                    open(path.join(pkgroot, 'opencc_data/TSPhrases.txt')) as f2:
                for line in chain(f1, f2):
                    k, vx = line.rstrip('\n').split('\t')
                    v = vx.split(' ')[0]
                    yield k, v
        
        elif config == 's2hk':
            # Simplified to HK: s2t then t2hk
            s2t = OpenCC('s2t').convert
            t2hk = OpenCC('t2hk').convert
            with open(path.join(pkgroot, 'opencc_data/STCharacters.txt')) as f1, \
                    open(path.join(pkgroot, 'opencc_data/STPhrases.txt')) as f2:
                for line in chain(f1, f2):
                    k, vx = line.rstrip('\n').split('\t')
                    v = t2hk(s2t(k))
                    yield k, v
                    
        elif config == 's2tw':
            # Simplified to TW: s2t then t2tw
            s2t = OpenCC('s2t').convert
            t2tw = OpenCC('t2tw').convert
            with open(path.join(pkgroot, 'opencc_data/STCharacters.txt')) as f1, \
                    open(path.join(pkgroot, 'opencc_data/STPhrases.txt')) as f2:
                for line in chain(f1, f2):
                    k, vx = line.rstrip('\n').split('\t')
                    v = t2tw(s2t(k))
                    yield k, v

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

        if not path.exists(cache_words) or not path.exists(cache_chars):
            entries = build_entries(config=config)
            entries = dict(entries)
            entries = sorted(entries.items(), key=lambda k_v: (
                len(k_v[0]), k_v[0]), reverse=True)

            with open(cache_words, 'w') as f1, \
                    open(cache_chars, 'w') as f2:
                for k, v in entries:
                    if k != v: # Only save if different
                        print(k, v, sep='\t', file=f1 if len(k) > 1 else f2)

    for cfg in configs:
        go(cfg)


def build_codepoints():
    '''
    Determine the necessary codepoints for the font.
    '''

    if not file_exists('cache/code_points_han.txt'):
        s = set()

        with open(path.join(pkgroot, 'cache/通用規範漢字表.txt')) as f:
            for line in f:
                if line and not line.startswith('#'):
                    c = line[0]
                    s.add(ord(c))

        for filename in (
            'STCharacters.txt', 'STPhrases.txt', 'TSCharacters.txt', 'TSPhrases.txt',
            'TWVariants.txt', 'TWPhrases.txt', 'HKVariants.txt'
        ):
            with open(path.join(pkgroot, 'opencc_data', filename)) as f:
                for line in f:
                    k, vx = line.rstrip('\n').split('\t')
                    vs = vx.split(' ')
                    for c in k:
                        s.add(ord(c))
                    for v in vs:
                        for c in v:
                            s.add(ord(c))

        for c in '妳攞噉㗎冚喺冇哋啲嘢啱佢嘅咁嚟屌咗撚噏瞓𡃁嘥掹孭氹詏噃𨳍掟埞曱甴𥄫𨳊嚿閪冧嬲卌嗻𧨾':
            s.add(ord(c))

        with open(path.join(pkgroot, 'cache/code_points_han.txt'), 'w') as f:
            for cp in sorted(s):
                if cp > 128:  # remove letters in the dictionaries
                    print(cp, file=f)


download_data()
build_convert_tables()
build_codepoints()

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
    install_requires=[],
    entry_points={},
    project_urls={
        'Bug Reports': 'https://github.com/ayaka14732/opencc-font-generator/issues',
        'Source': 'https://github.com/ayaka14732/opencc-font-generator',
    },
    zip_safe=False,
)
