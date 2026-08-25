#!/usr/bin/env python3

from setuptools import Extension
from setuptools import setup

setup(
    ext_modules=[
        Extension(
            "getdents._getdents",
            sources=["getdents/_getdents.c"],
            include_dirs=["getdents/"],
        ),
    ],
    headers=["getdents/shuffle.h"],
)
