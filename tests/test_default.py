"""gssgitlab tests module"""

import os
import subprocess
import sys
from copy import deepcopy
from io import FileIO, StringIO
from unittest.mock import patch

from gssgitlab import main as gssgitlab_main


def test_unknown_subcommand():
    """test unknown subcommand"""

    patch_argv = patch.object(sys, 'argv', ['gssgitlab.py'])

    with patch_argv:
        ret = gssgitlab_main()

    assert ret == 1


def test_newkey():
    """test newkey"""

    buf_stdout = StringIO()
    patch_stdout = patch.object(sys, 'stdout', buf_stdout)

    with patch_stdout:
        ret = gssgitlab_main(['newkey', 'principal@REALM'])

    assert ret == 0
    stdout = buf_stdout.getvalue()
    assert stdout.startswith('ssh-ed25519')
    assert 'gss:principal@REALM' in stdout


def test_newkey_invalid_principal():
    """test newkey invalid principal"""

    ret = gssgitlab_main(['newkey', 'invalid_principal'])

    assert ret == 1


def test_syndb(tempdir):
    """test syndb"""

    tempenv = deepcopy(os.environ)
    tempenv['PATH'] = './tests:' + tempenv['PATH']
    patch_environ = patch.object(os, 'environ', tempenv)

    with patch_environ:
        ret = gssgitlab_main(['--gitlab_home', tempdir, 'syncdb'])

    assert ret == 0
    with open(os.path.join(tempdir, '.k5login')) as ftmp:
        assert 'principal1@REALM' in ftmp.read()
    with open(os.path.join(tempdir, '.k5keys')) as ftmp:
        assert 'principal2@REALM key-2' in ftmp.read()


def test_shell_local(tempdir):
    """
    test execution as non-ssh session. if executed localy (without any SSH_ var
    in environment), gssgitlab should act like simple shell by passing all
    arguments through execv.
    
    to test such behavior, os.environ and os.execv has to be patched in order
    to trigger proper code and to allow the test to finish and perform asserts.
    execution output is catched (stdout cannot be mocked) and evaluated against
    expected shell output.
    """

    def forking_execv(arg1, arg2):
        with open(os.path.join(tempdir, 'mocked_stdout'), 'w') as ftmp:
            return subprocess.run([arg1] + arg2[1:], stdout=ftmp)

    patch_environ = patch.object(os, 'environ', {k: v for k,v in os.environ.items() if not k.startswith('SSH_')})
    patch_execv = patch.object(os, 'execv', forking_execv)

    with patch_environ, patch_execv:
        ret = gssgitlab_main(['shell', '-c', 'echo "shell executed $((1+1)) args:$@"'])

    assert ret == 12
    with open(os.path.join(tempdir, 'mocked_stdout'), 'r') as ftmp:
        assert 'shell executed 2 args:\n' == ftmp.read()


def test_shell_ssh(tempdir):
    """
    test execution as ssh session with authentication

    test execution as ssh session. if executed over ssh (with SSH_ vars in
    environment), gssgitlab should spawn configure gitlab-shell with keyid as
    argument.
    
    to test such behavior, os.environ, used gitlab-shell path and os.execv has
    to be patched in order to trigger proper code and to allow the test to
    finish and perform asserts. execution output is catched (stdout cannot be
    mocked) and evaluated against expected output.
    """

    def forking_execv(arg1, arg2):
        with open(os.path.join(tempdir, 'mocked_stdout'), 'w') as ftmp:
            return subprocess.run([arg1] + arg2[1:], stdout=ftmp)

    authdata_file = os.path.join(tempdir, 'authdata')
    with open(authdata_file, 'w') as ftmp:
        ftmp.write('gssapi-with-mic test@REALM\n')

    with open(os.path.join(tempdir, '.k5keys'), 'w') as ftmp:
        ftmp.write('test@REALM key-3\n')

    tempenv = {k: v for k,v in os.environ.items() if not k.startswith('SSH_')}
    tempenv['SSH_CONNECTION'] = 'dummy'
    tempenv['SSH_USER_AUTH'] = authdata_file

    patch_environ = patch.object(os, 'environ', tempenv)
    patch_execv = patch.object(os, 'execv', forking_execv)

    with patch_environ, patch_execv:
        ret = gssgitlab_main([
            '--gitlab_home', tempdir,
            '--gitlab_shell', '/bin/echo',
            'shell', 'original_command', 'original_argument'])

        assert os.environ.get('SSH_ORIGINAL_COMMAND') == 'original_argument'

    assert ret == 10
    with open(os.path.join(tempdir, 'mocked_stdout'), 'r') as ftmp:
        assert 'key-3\n' == ftmp.read()


def test_shell_ssh_not_authenticated(tempdir):
    """test execution as ssh session without proper authentication"""

    def forking_execv(arg1, arg2):
        with open(os.path.join(tempdir, 'mocked_stdout'), 'w') as ftmp:
            return subprocess.run([arg1] + arg2[1:], stdout=ftmp)

    tempenv = {k: v for k,v in os.environ.items() if not k.startswith('SSH_')}
    tempenv['SSH_CONNECTION'] = 'dummy'
    patch_environ = patch.object(os, 'environ', tempenv)
    patch_execv = patch.object(os, 'execv', forking_execv)

    # test ssh session without auth
    with patch_environ, patch_execv:
        ret = gssgitlab_main(['shell', 'original_command', 'original_argument'])
    assert ret == 11
    assert not os.path.exists(os.path.join(tempdir, 'mocked_stdout'))

    # test ssh session with invalid auth data
    tempenv['SSH_USER_AUTH'] = '/tmp/invalid'
    with patch_environ, patch_execv:
        ret = gssgitlab_main(['shell', 'original_command', 'original_argument'])
    assert ret == 11

    # test ssh session without non-gssapi authentication
    authdata_file = os.path.join(tempdir, 'authdata')
    with open(authdata_file, 'w') as ftmp:
        ftmp.write('password\n')

    tempenv['SSH_USER_AUTH'] = authdata_file
    with patch_environ, patch_execv:
        ret = gssgitlab_main(['shell', 'original_command', 'original_argument'])
    assert ret == 11
