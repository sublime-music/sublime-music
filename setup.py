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
    here.joinpath("sublime", "adapters", "icons"),
    here.joinpath("sublime", "adapters", "images"),
    here.joinpath("sublime", "adapters", "subsonic", "icons"),
    here.joinpath("sublime", "dbus", "mpris_specs"),
    here.joinpath("sublime", "ui", "icons"),
    here.joinpath("sublime", "ui", "images"),
]
package_data_files = []
for data_dir in package_data_dirs:
    for file in data_dir.iterdir():
        package_data_files.append(str(file))

setup(
    name="sublime-music",
    version=version,
    url="https://gitlab.com/sublime-music/sublime-music",
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
        "Programming Language :: Python :: 3.8",
    ],
    keywords="airsonic subsonic libresonic gonic music",
    packages=find_packages(exclude=["tests"]),
    package_data={"sublime": ["ui/app_styles.css", *package_data_files]},
    install_requires=[
        "dataclasses-json",
        "deepdiff",
        "fuzzywuzzy",
        'osxmmkeys ; sys_platform=="darwin"',
        "peewee",
        "PyGObject",
        "python-dateutil",
        "python-Levenshtein",
        "python-mpv",
        "requests",
        "semver",
    ],
    extras_require={
        "keyring": ["keyring"],
        "chromecast": ["pychromecast"],
        "server": ["bottle"],
    },
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and
    # allow pip to create the appropriate form of executable for the target
    # platform.
    entry_points={"console_scripts": ["sublime-music=sublime.__main__:main"]},
)
