"""gssgitlab syncdb tests module"""

import os
import subprocess
from copy import deepcopy
from unittest.mock import patch

from gssgitlab import main as gssgitlab_main


def test_syndb(tempdir):
    """
    Test syndb

    PATH is patched so the test does not require real gitlab installation
    """

    tempenv = deepcopy(os.environ)
    tempenv['PATH'] = './tests:' + tempenv['PATH']
    patch_environ = patch.object(os, 'environ', tempenv)

    with patch_environ:
        ret = gssgitlab_main(['--gitlab_home', tempdir, 'syncdb'])

    assert ret == 0
    with open(f'{tempdir}/.k5login') as ftmp:
        assert 'principal1@REALM' in ftmp.read()
    with open(f'{tempdir}/.k5keys') as ftmp:
        assert 'principal2@REALM key-2' in ftmp.read()


def test_syncdb_error_handling():
    """Test syncdb code error handling"""

    def raising_run(*_args, capture_output, check, text):
        raise subprocess.CalledProcessError(1, 'cmd')

    patch_run = patch.object(subprocess, 'run', raising_run)

    with patch_run:
        ret = gssgitlab_main(['syncdb'])

    assert ret == 1
