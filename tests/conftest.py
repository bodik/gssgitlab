"""pytest fixtures"""

import shutil
from tempfile import mkdtemp

import pytest


@pytest.fixture
def tempdir():
    """
    self cleaning temporary workdir
    pytest tmpdir fixture has issues https://github.com/pytest-dev/pytest/issues/1120
    """

    tmpdir = mkdtemp(prefix='gssgitlab-')
    yield tmpdir
    shutil.rmtree(tmpdir)
