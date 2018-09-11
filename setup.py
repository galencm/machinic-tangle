from setuptools import find_packages, setup

setup(
    name="machinic_tangle",
    version="0.1",
    description="",
    author="Galen Curwen-McAdams",
    author_email="",
    platforms=["any"],
    license="Mozilla Public License 2.0 (MPL 2.0)",
    include_package_data=True,
    url="",
    packages=find_packages(),
    install_requires=[
        "kivy",
        "ma_cli",
        "lings",
        "keli",
        "lxml",
        "jinja2",
        "netifaces",
        "textx",
    ],
    dependency_links=[
        "https://github.com/galencm/ma-cli/tarball/master#egg=ma_cli-0.1",
        "https://github.com/galencm/machinic-keli/tarball/master#egg=keli-0.1",
        "https://github.com/galencm/machinic-lings/tarball/master#egg=lings-0.1",
    ],
    entry_points={
        "console_scripts": [
            "ma-ui-tangle = machinic_tangle.tangle_ui:main",
            "tangle-ui = machinic_tangle.tangle_ui:main",
            "tangle-associative = machinic_tangle.associative:main",
            "tangle-things = machinic_tangle.tangle_things:main",
            "tangle-bridge = machinic_tangle.bridge_cli:main",
            "lings-path-add = machinic_tangle.paths_add:main",
        ]
    },
)
