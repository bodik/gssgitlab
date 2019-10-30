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


GITLAB_HOME = '/var/opt/gitlab'
GITLAB_SHELL = '/opt/gitlab/embedded/service/gitlab-shell/bin/gitlab-shell'


def is_valid_principal(principal):
    """check if principal is valid"""
    return bool(re.match(r'^[a-z/]+@[A-Z\.\-]+$', principal))


def gitlab_psql(sql):
    """execute gitlab psql and return result set"""

    try:
        proc = subprocess.run(
            ['gitlab-psql', '--quiet', '--no-align', '--tuples-only', '--command', sql],
            capture_output=True,
            check=True,
            text=True)
        if proc.stdout:
            return [tuple(row.split('|')) for row in proc.stdout.splitlines()]
    except subprocess.SubprocessError:
        logging.error('gitlab-psql failed')
    return []


def keyid_from_authdata():
    """resolve keyid for principal from exposed authentication info"""

    if 'SSH_USER_AUTH' not in os.environ:
        return None

    try:
        with open(os.environ['SSH_USER_AUTH'], 'r') as ftmp:
            match = re.match('gssapi-with-mic (?P<principal>.*)', ftmp.read())
            if (not match) or (not is_valid_principal(match.group('principal'))):
                return None
    except OSError:
        return None

    try:
        with open(os.path.join(GITLAB_HOME, '.k5keys')) as ftmp:
            for line in ftmp.read().splitlines():
                princ, keyid = line.split(' ')
                if princ == match.group('principal'):
                    return keyid
    except OSError:
        return None

    return None


def exec_shell(command=None):
    """shell-exec subcommand"""

    # over ssh connection, we must enforce gitlab-shell
    if 'SSH_CONNECTION' in os.environ:
        keyid = keyid_from_authdata()
        if keyid:
            if command:
                os.putenv('SSH_ORIGINAL_COMMAND', command)
            os.execv(GITLAB_SHELL, [GITLAB_SHELL, keyid])
        return 1

    # otherwise preserve shell for local services running under git account
    if command:
        os.execv('/bin/sh', ['/bin/sh', '-c', command])
    os.execv('/bin/sh', ['/bin/sh'])
    return 1


def generate_key(principal):
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


def generate_configs():
    """generate k5login and k5keys from keys registered in gitlab"""

    dbkeys = gitlab_psql("select id, title from keys where title like 'gss:%'")

    with open(os.path.join(GITLAB_HOME, '.k5keys'), 'w') as ftmp:
        for keyid, princ in dbkeys:
            ftmp.write('%s key-%s\n' % (princ.replace('gss:', ''), keyid))

    with open(os.path.join(GITLAB_HOME, '.k5login'), 'w') as ftmp:
        for keyid, princ in dbkeys:
            ftmp.write('%s\n' % princ.replace('gss:', ''))


def parse_arguments():
    """parse arguments"""

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='subcommand')

    exec_shell_parser = subparsers.add_parser('exec-shell')
    exec_shell_parser.add_argument('-c', dest='command')

    generate_key_parser = subparsers.add_parser('generate-key')
    generate_key_parser.add_argument('principal')

    subparsers.add_parser('generate-configs')

    return parser.parse_args()


def main():
    """main"""

    args = parse_arguments()
    if args.subcommand == 'exec-shell':
        return exec_shell(args.command)
    if args.subcommand == 'generate-key':
        return generate_key(args.principal)
    if args.subcommand == 'generate-configs':
        return generate_configs()
    logging.error('unknown subcommand')
    return -1


if __name__ == '__main__':
    sys.exit(main())
