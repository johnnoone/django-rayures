#!/usr/bin/env python3

from setuptools import setup, find_packages
import versioneer

setup(
    name="rayures",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "stripe>=1.82.1"
    ],
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass()
)
