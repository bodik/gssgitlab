"""gssgitlab tests module"""

import os
import subprocess
import sys
from copy import deepcopy
from io import StringIO
from unittest.mock import patch

from gssgitlab import main as gssgitlab_main


def test_unknown_subcommand():
    """Test unknown subcommand"""

    patch_argv = patch.object(sys, 'argv', ['gssgitlab.py'])

    with patch_argv:
        ret = gssgitlab_main()

    assert ret == 1


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


def test_shell_local(tempdir):
    """
    Test execution as non-ssh session. if executed localy (without any SSH_ var
    in environment), gssgitlab should act like simple shell by passing all
    arguments through execv.

    To test such behavior, os.environ and os.execv has to be patched in order
    to trigger proper code and to allow the test to finish and perform asserts.
    Execution output is catched (stdout cannot be mocked) and evaluated against
    expected shell output.
    """

    def forking_execv(arg1, arg2):
        with open(f'{tempdir}/mocked_stdout', 'w') as ftmp:
            return subprocess.run([arg1] + arg2[1:], stdout=ftmp, check=True)

    patch_environ = patch.object(os, 'environ', {k: v for k, v in os.environ.items() if not k.startswith('SSH_')})
    patch_execv = patch.object(os, 'execv', forking_execv)

    with patch_environ, patch_execv:
        ret = gssgitlab_main(['shell', '-c', 'echo "shell executed $((1+1))"'])

    assert ret == 13
    with open(f'{tempdir}/mocked_stdout', 'r') as ftmp:
        assert ftmp.read() == 'shell executed 2\n'


def test_shell_ssh_invalid_authentication(tempdir):
    """
    Test execution as ssh session without proper authentication

    The test should not make it up to os.execv parts in any case, the function
    is patched anyway to handle such situation.
    """

    def raising_execv(_arg1, _arg2):
        assert False

    tempenv = {k: v for k, v in os.environ.items() if not k.startswith('SSH_')}
    tempenv['SSH_CONNECTION'] = 'dummy'
    patch_environ = patch.object(os, 'environ', tempenv)
    patch_execv = patch.object(os, 'execv', raising_execv)

    # test ssh session without authdata
    with patch_environ, patch_execv:
        ret = gssgitlab_main(['shell', 'original_command', 'original_argument'])
    assert ret == 10
    assert not os.path.exists(f'{tempdir}/mocked_stdout')


def test_shell_ssh_non_gss_authentication(tempdir):
    """Test execution with successfull non-gssapi authentication, should be passed and executed"""

    def forking_execv(arg1, arg2):
        with open(f'{tempdir}/mocked_stdout', 'w') as ftmp:
            return subprocess.run([arg1] + arg2[1:], stdout=ftmp, check=True)

    tempenv = {k: v for k, v in os.environ.items() if not k.startswith('SSH_')}
    tempenv['SSH_CONNECTION'] = 'dummy'
    patch_environ = patch.object(os, 'environ', tempenv)
    patch_execv = patch.object(os, 'execv', forking_execv)

    authdata_file = f'{tempdir}/authdata'
    with open(authdata_file, 'w') as ftmp:
        ftmp.write('amethod andummyauthdata\n')
    tempenv['SSH_USER_AUTH'] = authdata_file

    with patch_environ, patch_execv:
        ret = gssgitlab_main(['shell', '-c', 'echo "shell executed $((1+1))"'])

    assert ret == 13
    with open(f'{tempdir}/mocked_stdout', 'r') as ftmp:
        assert ftmp.read() == 'shell executed 2\n'


def test_shell_ssh_proper_gss_authentication(tempdir):
    """
    Test execution as ssh session with authentication

    If executed over ssh (with SSH_ vars in environment), gssgitlab should
    spawn configure gitlab-shell with keyid as argument.

    To test such behavior, os.environ, used gitlab-shell path and os.execv has
    to be patched in order to trigger proper code and to allow the test to
    finish and perform asserts. Execution output is catched (stdout cannot be
    mocked) and evaluated against expected output.
    """

    def forking_execv(arg1, arg2):
        with open(f'{tempdir}/mocked_stdout', 'w') as ftmp:
            return subprocess.run([arg1] + arg2[1:], stdout=ftmp, check=True)

    authdata_file = f'{tempdir}/authdata'
    with open(authdata_file, 'w') as ftmp:
        ftmp.write('gssapi-with-mic test@REALM\n')

    with open(f'{tempdir}/.k5keys', 'w') as ftmp:
        ftmp.write('test@REALM key-3\n')

    tempenv = {k: v for k, v in os.environ.items() if not k.startswith('SSH_')}
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

    assert ret == 11
    with open(f'{tempdir}/mocked_stdout', 'r') as ftmp:
        assert ftmp.read() == 'key-3\n'


def test_shell_ssh_non_mapped_gss_authentication(tempdir):
    """Test execution with non-mapped gss auth, eg. k5login and k5keys is out of sync"""

    def raising_execv(_arg1, _arg2):
        assert False

    tempenv = {k: v for k, v in os.environ.items() if not k.startswith('SSH_')}
    tempenv['SSH_CONNECTION'] = 'dummy'
    patch_environ = patch.object(os, 'environ', tempenv)
    patch_execv = patch.object(os, 'execv', raising_execv)

    authdata_file = f'{tempdir}/authdata'
    with open(authdata_file, 'w') as ftmp:
        ftmp.write('gssapi-with-mic non-mapped-principal@REALM\n')
    tempenv['SSH_USER_AUTH'] = authdata_file

    with open(f'{tempdir}/.k5keys', 'w') as ftmp:
        ftmp.write('test@REALM key-3\n')

    with patch_environ, patch_execv:
        ret = gssgitlab_main([
            '--gitlab_home', tempdir,
            '--gitlab_shell', '/bin/echo',
            'shell', 'original_command', 'echo original_argument'])

    assert ret == 12
