#!/usr/bin/env python3

from setuptools import setup, find_packages
import versioneer

setup(
    name="rayures",
    version=versioneer.get_version(),
    author="Xavier Barbosa",
    author_email="clint.northwood@gmail.com",
    url="https://lab.errorist.xyz/django/rayures",
    description="Integrate stripe into django application",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "stripe>=1.82.1"
    ],
    extras_require={
        'factories':  ["factory_boy>=2.11.1"],
    },
    license='MIT',
    classifiers=[
        "Development Status :: 4 - Beta",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content :: Content Management System",
        "Topic :: Office/Business :: Financial",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    cmdclass=versioneer.get_cmdclass()
)
