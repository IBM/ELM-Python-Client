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
    version="0.20.0",
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
    ],
    packages=["elmclient", "elmclient.examples","elmclient.tests"],
    include_package_data=True,
#    install_requires=['CacheControl==0.12.6','anytree==2.8.0',"colorama==0.4.4","cryptography==3.4.4",'lark_parser==0.12.0','lockfile==0.12.2','lxml==4.7.1',"openpyxl == 3.0.9","python-dateutil==2.8.2", "pytz==2021.3", "requests>=2.24.0","requests_toolbelt>=0.9.1",'tqdm==4.56.2','urllib3==1.25.11', "bump2version", "twine"],
    install_requires=['CacheControl','anytree',"colorama","cryptography",'lark_parser','lockfile','lxml',"openpyxl","python-dateutil", "pytz", "requests","requests_toolbelt",'tqdm','urllib3', "bump2version", "twine",'filelock'],
    entry_points={
        "console_scripts": [
            "oslcquery=elmclient.examples.oslcquery:main",
            "batchquery=elmclient.examples.batchquery:main",
            "represt=elmclient.examples.represt:main",
            "reqif_io=elmclient.examples.reqif_io:main",
            "log2seq=elmclient.examples.log2seq:main",
        ]
    },
)
