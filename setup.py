##
## © Copyright 2021- IBM Inc. All rights reserved
# SPDX-License-Identifier: MIT
##


import pathlib
from setuptools import find_packages,setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="elmclient",
    version="0.33.0",
    description="Python client for ELM with examples of OSLC Query, ReqIF import/export, Reportable REST, and more",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/IBM/ELM-Python-Client",
    author="Ian Barnard",
#    author_email="ian.barnard@uk.ibm.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    packages=["elmclient", "elmclient.examples","elmclient.tests"],
    include_package_data=True,
    install_requires=['CacheControl','anytree',"colorama","cryptography",'lark_parser','lockfile','lxml',"openpyxl","python-dateutil", "pytz", "requests","requests_toolbelt",'tqdm','urllib3', "bump2version", "twine",'filelock'],
    entry_points={
        "console_scripts": [
            "oslcquery=elmclient.examples.oslcquery:main",
            "batchquery=elmclient.examples.batchquery:main",
            "represt=elmclient.examples.represt:main",
            "reqif_io=elmclient.examples.reqif_io:main",
            "log2seq=elmclient.examples.log2seq:main",
            "validate=elmclient.examples.validate:main",
        ]
    },
)
