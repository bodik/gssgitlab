#!/usr/bin/env python3
"""
inspired by https://github.com/iamjamestl/kgitlab
"""

import logging
import os
import re
import subprocess
import sys
from argparse import ArgumentParser
from uuid import uuid4


def is_valid_principal(principal):
    """check if principal is valid"""
    return bool(re.match(r'^[a-z/]+@[A-Z\.\-]+$', principal))


def gitlab_psql(sql):
    """execute gitlab-psql query"""

    proc = subprocess.run(
        ['gitlab-psql', '--quiet', '--no-align', '--tuples-only', '--command', sql],
        capture_output=True,
        check=True,
        text=True)
    return [tuple(row.split('|')) for row in proc.stdout.splitlines()]


def do_generate_key(principal):
    """generate temporary ssh key"""

    if not is_valid_principal(principal):
        logging.error('principal not valid')
        return False

    tempkey_name = os.path.join('/dev/shm', 'gssgitlab-' + str(uuid4()))
    tempkey_name_pub = tempkey_name + '.pub'
    subprocess.run(
        ['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'gss:' + principal, '-f', tempkey_name],
        check=True)
    with open(tempkey_name_pub, 'r') as ftmp:
        public_key = ftmp.read().strip()
    os.unlink(tempkey_name)
    os.unlink(tempkey_name_pub)

    print(public_key)
    return 0


class GssGitlab:
    """gss gitlab shell"""

    def __init__(self):
        self.home = '/var/opt/gitlab'
        self.k5login = os.path.join(self.home, '.k5login')
        self.k5keys = os.path.join(self.home, '.k5keys')
        self.shell = '/opt/gitlab/embedded/service/gitlab-shell/bin/gitlab-shell'

    def do_exec_shell(self, args):
        """shell-exec subcommand"""

        # enforce gitlab-shell on ssh connection
        if 'SSH_CONNECTION' in os.environ:
            keyid = self._keyid_from_authdata()
            if keyid:
                if args:
                    os.putenv('SSH_ORIGINAL_COMMAND', ' '.join(args[1:]))
                os.execv(self.shell, [self.shell, keyid])
            return 1

        # otherwise preserve shell for local services running under git account
        os.execv('/bin/sh', ['/bin/sh'] + args)
        return 1

    def _keyid_from_authdata(self):
        """resolve keyid for principal from exposed authentication info"""

        if 'SSH_USER_AUTH' not in os.environ:
            return None

        try:
            with open(os.environ['SSH_USER_AUTH'], 'r') as ftmp:
                match = re.match(r'^gssapi-with-mic (?P<principal>.*)$', ftmp.read().strip())
                if (not match) or (not is_valid_principal(match.group('principal'))):
                    return None

            with open(self.k5keys, 'r') as ftmp:
                for line in ftmp.read().splitlines():
                    princ, keyid = line.split()
                    if princ == match.group('principal'):
                        return keyid
        except OSError:
            pass

        return None

    def do_generate_configs(self):
        """generate k5login and k5keys from keys registered in gitlab"""

        dbkeys = gitlab_psql("select id, title from keys where title like 'gss:%'")

        with open(self.k5keys, 'w') as ftmp:
            for keyid, princ in dbkeys:
                ftmp.write('%s key-%s\n' % (princ.replace('gss:', ''), keyid))

        with open(self.k5login, 'w') as ftmp:
            for keyid, princ in dbkeys:
                ftmp.write('%s\n' % princ.replace('gss:', ''))


def main():
    """main"""

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='subcommand')
    subparsers.add_parser('generate-key').add_argument('principal')
    subparsers.add_parser('exec-shell')
    subparsers.add_parser('generate-configs')
    args, unk_args = parser.parse_known_args()

    if args.subcommand == 'generate-key':
        return do_generate_key(args.principal)

    gssgitlab = GssGitlab()
    if args.subcommand == 'exec-shell':
        return gssgitlab.do_exec_shell(unk_args)
    if args.subcommand == 'generate-configs':
        return gssgitlab.do_generate_configs()

    logging.error('unknown subcommand')
    return -1


if __name__ == '__main__':
    sys.exit(main())
