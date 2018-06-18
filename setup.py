from setuptools import setup, find_packages

setup(
    name="rayures",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "stripe>=1.82.1"
    ],
)
