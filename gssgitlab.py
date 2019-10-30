#!/usr/bin/env python3
"""
gssgitlab provides shell replacement for git user on
gitlab server allowing users to seamlesly use GSSAPI authentication over ssh.
inspired by https://github.com/iamjamestl/kgitlab
"""

import logging
import os
import re
import subprocess
import sys
from argparse import ArgumentParser
from uuid import uuid4


__version__ = '0.3-dev'


class GssGitlab:
    """gss gitlab shell"""

    def __init__(self, gitlab_home, gitlab_shell):
        self.k5login = f'{gitlab_home}/.k5login'
        self.k5keys = f'{gitlab_home}/.k5keys'
        self.shell = gitlab_shell

    @staticmethod
    def is_valid_principal(principal):
        """check if principal is valid"""
        return bool(re.match(r'^[a-z][a-z0-9/_\.\-]*@[A-Z\.\-]+$', principal))

    def do_newkey(self, principal):
        """
        Generate dummy ssh key used for mapping kerberos principal to gitlab
        key/user identity. The actual key is not used (only registered keyid),
        but it's easier to generate temporary one to get public part than to
        fake the process some other way.
        """

        if not self.is_valid_principal(principal):
            logging.error('principal not valid')
            return 1

        tempkey_name = f'/dev/shm/gssgitlab-{uuid4()}'
        subprocess.run(
            ['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', f'gss:{principal}', '-f', tempkey_name],
            check=True)
        with open(f'{tempkey_name}.pub', 'r') as ftmp:
            public_key = ftmp.read().strip()
        os.unlink(tempkey_name)
        os.unlink(f'{tempkey_name}.pub')

        print(public_key)
        return 0

    def do_syncdb(self):
        """generate k5login and k5keys from keys registered in gitlab"""

        proc = subprocess.run(
            [
                'gitlab-psql', '--quiet', '--no-align', '--tuples-only',
                '--command', "select id, title from keys where title like 'gss:%'"
            ],
            capture_output=True, check=True, text=True)
        dbkeys = [tuple(row.split('|')) for row in proc.stdout.splitlines()]

        with open(self.k5login, 'w') as fk5login:
            with open(self.k5keys, 'w') as fk5keys:
                for keyid, princ in dbkeys:
                    princitem = princ.replace('gss:', '')
                    if self.is_valid_principal(princitem):
                        fk5keys.write(f'{princitem} key-{keyid}\n')
                        fk5login.write(f'{princitem}\n')
                        print(f'added {princitem}')

        return 0

    def do_shell(self, args):
        """
        shell-exec subcommand

        For ssh connections check authentication method and credential data.
            - Die for unknown methods.
            - For GSS-API resolve keyid and spawn gitlab-shell or die (k5login and k5keys are out-of-sync)
            - For any other method or non-ssh connections pass the shell
                - configuration does not allow Password authentication
                - forcedcommand confines logon to gitlab-shell only
        """

        # on ssh connection
        if 'SSH_CONNECTION' in os.environ:
            method, keyid = self._get_authdata()

            if not method:
                return 10

            if method == 'gssapi-with-mic':
                if keyid:
                    if args:
                        # during execution, the first argument is '-c' which needs to be stripped out
                        os.environ['SSH_ORIGINAL_COMMAND'] = ' '.join(args[1:])
                    os.execv(self.shell, [self.shell, keyid])
                    return 11
                return 12

        # otherwise pass to shell, either for standard forcedcommand or local services under git account
        os.execv('/bin/sh', ['/bin/sh'] + args)
        return 13

    def _get_authdata(self):
        """
        resolves keyid for gssapi authenticated principal from exposed authentication info

        Returns:
           tuple of (str method, str keyid)
        """

        try:
            with open(os.environ['SSH_USER_AUTH'], 'r') as ftmp:
                method, authdata = ftmp.read().strip().split(maxsplit=1)
            if (method == 'gssapi-with-mic') and self.is_valid_principal(authdata):
                with open(self.k5keys, 'r') as ftmp:
                    keydb = dict([line.split() for line in ftmp])
                    return method, keydb.get(authdata)
            else:
                return method, None
        except (KeyError, OSError, ValueError):
            pass
        return None, None


def parse_arguments(argv=None):
    """parse arguments"""

    parser = ArgumentParser()
    parser.add_argument('--gitlab_home', default='/var/opt/gitlab')
    parser.add_argument('--gitlab_shell', default='/opt/gitlab/embedded/service/gitlab-shell/bin/gitlab-shell')

    subparsers = parser.add_subparsers(dest='subcommand')
    subparsers.add_parser('newkey').add_argument('principal')
    subparsers.add_parser('syncdb')
    subparsers.add_parser('shell')

    return parser.parse_known_args(argv)


def main(argv=None):
    """main"""

    args, unk_args = parse_arguments(argv)
    gssgitlab = GssGitlab(args.gitlab_home, args.gitlab_shell)

    if args.subcommand == 'newkey':
        return gssgitlab.do_newkey(args.principal)
    if args.subcommand == 'shell':
        return gssgitlab.do_shell(unk_args)
    if args.subcommand == 'syncdb':
        return gssgitlab.do_syncdb()

    logging.error('unknown subcommand')
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
