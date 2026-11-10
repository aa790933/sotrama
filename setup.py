from setuptools import find_packages, setup

from sotrama import __version__

setup(
    name="sotrama",
    version=__version__,
    description="Algerian localization and public works extensions for Frappe",
    author="Sotrama",
    author_email="noreply@github.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[],
)
