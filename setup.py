from setuptools import find_packages, setup
setup(
name="machinic_tangle",
    version="0.1",
    description="",
    author="Galen Curwen-McAdams",
    author_email='',
    platforms=["any"],
    license="Mozilla Public License 2.0 (MPL 2.0)",
    include_package_data=True,
    data_files = [("", ["LICENSE.txt"])],
    url="",
    packages=find_packages(),
    install_requires=['kivy', 'ma_cli', 'lings', 'keli'],
    dependency_links=["https://github.com/galencm/ma-cli/tarball/master#egg=ma_cli-0.1",
                      "https://github.com/galencm/machinic-keli/tarball/master#egg=keli-0.1",
                      "https://github.com/galencm/machinic-lings/tarball/master#egg=lings-0.1"],
    entry_points = {'console_scripts': ['ma-ui-tangle = machinic_tangle.tangle_ui:main',
                                        'tangle-ui = machinic_tangle.tangle_ui:main',
                                        'tangle-associative = machinic_tangle.associative:main'
                                       ],
                            },
)
