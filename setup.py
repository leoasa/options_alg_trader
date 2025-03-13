from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setup(
    name="options_trader",
    version="0.1.0",
    author="Leo Asatoorian",
    author_email="your.email@example.com",
    description="A Python application for monitoring and trading options using the Alpaca API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/leoasa/options_alg_trader",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "options-cli=options_trader.cli_monitor:main",
            "options-monitor=options_trader.options_monitor:main",
        ],
    },
) 