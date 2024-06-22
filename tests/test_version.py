"""Test to catch invalid versions when releasing a new git tag"""

import os

from fluke5440b_async._version import __version__


def test_version():
    """
    Test the Git tag when using CI against the package version
    """
    if os.getenv("GIT_TAG"):
        assert os.getenv("GIT_TAG") == __version__
    else:
        assert True
