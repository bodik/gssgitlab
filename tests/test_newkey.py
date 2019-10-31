"""gssgitlab newkey tests module"""

import sys
import subprocess
from io import StringIO
from unittest.mock import patch

from gssgitlab import main as gssgitlab_main


def test_newkey():
    """Test newkey"""

    buf_stdout = StringIO()
    patch_stdout = patch.object(sys, 'stdout', buf_stdout)

    with patch_stdout:
        ret = gssgitlab_main(['newkey', 'principal@REALM'])

    assert ret == 0
    stdout = buf_stdout.getvalue()
    assert stdout.startswith('ssh-ed25519')
    assert 'gss:principal@REALM' in stdout


def test_newkey_invalid_principal():
    """Test newkey with invalid principal"""

    ret = gssgitlab_main(['newkey', 'invalid_principal'])

    assert ret == 1


def test_newkey_error_handling():
    """Test newkey code error handling"""

    def raising_run(*_args, check):
        raise subprocess.CalledProcessError(1, 'cmd')

    patch_run = patch.object(subprocess, 'run', raising_run)

    with patch_run:
        ret = gssgitlab_main(['newkey', 'principal@REALM'])

    assert ret == 1
