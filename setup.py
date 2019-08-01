import codecs
import os

from setuptools import find_packages, setup

here = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

# Find the version
with codecs.open(os.path.join(here, 'libremsonic/__init__.py'),
                 encoding='utf-8') as f:
    for line in f:
        if line.startswith('__version__'):
            version = eval(line.split()[-1])
            break

setup(
    name='libremsonic',
    version=version,
    url='https://gitlab.com/robozman/libremsonic',
    description='A native GTK *sonic client.',
    long_description=long_description,
    author='Sumner Evans',
    author_email='sumner.evans98@gmail.com',
    license='GPL3',
    classifiers=[
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - ALpha',

        # Indicate who your project is intended for
        'Intended Audience :: End Users/Desktop',
        'Operating System :: POSIX',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='airsonic subsonic libresonic music',
    packages=find_packages(exclude=['tests']),
    package_data={'libremsonic': ['ui/app_styles.css']},
    install_requires=[
        'deepdiff',
        'Deprecated',
        'fuzzywuzzy',
        'gobject',
        'pychromecast',
        'PyGObject',
        'python-dateutil',
        'python-Levenshtein',
        'python-mpv',
        'pyyaml',
        'requests',
    ],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and
    # allow pip to create the appropriate form of executable for the target
    # platform.
    entry_points={
        'console_scripts': [
            'libremsonic=libremsonic.__main__:main',
        ],
    },
)
