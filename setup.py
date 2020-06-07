from pathlib import Path

from setuptools import find_packages, setup

here = Path(__file__).parent.resolve()

with open(here.joinpath("README.rst"), encoding="utf-8") as f:
    long_description = f.read()

# Find the version
with open(here.joinpath("sublime", "__init__.py")) as f:
    for line in f:
        if line.startswith("__version__"):
            version = eval(line.split()[-1])
            break

package_data_dirs = [
    here.joinpath("sublime", "ui", "icons"),
    here.joinpath("sublime", "dbus", "mpris_specs"),
]
package_data_files = []
for data_dir in package_data_dirs:
    for file in data_dir.iterdir():
        if not str(file).endswith(".svg"):
            continue
        package_data_files.append(str(file))

setup(
    name="sublime-music",
    version=version,
    url="https://gitlab.com/sumner/sublime-music",
    description="A native GTK *sonic client.",
    long_description=long_description,
    author="Sumner Evans",
    author_email="inquiries@sumnerevans.com",
    license="GPL3",
    classifiers=[
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        "Development Status :: 3 - Alpha",
        # Indicate who your project is intended for
        "Intended Audience :: End Users/Desktop",
        "Operating System :: POSIX",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="airsonic subsonic libresonic gonic music",
    packages=find_packages(exclude=["tests"]),
    package_data={
        "sublime": [
            "ui/app_styles.css",
            "ui/images/play-queue-play.png",
            "adapters/images/default-album-art.png",
            *package_data_files,
        ]
    },
    install_requires=[
        "bottle",
        "dataclasses-json",
        "deepdiff",
        "fuzzywuzzy",
        'osxmmkeys ; sys_platform=="darwin"',
        "peewee",
        "pychromecast",
        "PyGObject",
        "python-dateutil",
        "python-Levenshtein",
        "python-mpv",
        "pyyaml",
        "requests",
    ],
    extras_require={"keyring": ["keyring"]},
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and
    # allow pip to create the appropriate form of executable for the target
    # platform.
    entry_points={"console_scripts": ["sublime-music=sublime.__main__:main"]},
)
