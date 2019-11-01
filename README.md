# gssgitlab

gssgitlab is a shell wrapper for Gitlab to provide SSH GSS-API (aka Kerberos)
authenticated access to the repositories.

Project is heavily inspired by
[Kgitlab](https://github.com/iamjamestl/kgitlab).

Gitlab uses SSH Pubkey authentication with ForcedCommand to map keys to the
corresponding users/identities. With GSS-API/Kerberos authentication no such
feature exist, but can be emulated in the shell of the *git* user. This tool
allows Gitlab administrator to generate, register and map to kerberos
principals a "dummy" keys, so upon successfull GSS-API logon, gssgitlab (shell
for *git*) can lookup the keyid of the logged in user and spawn appropriate
gitlab-shell in the same way the ForcedCommand would normally do.


## Motivation

Gitlab allows Kerberos (SPNEGO) authenticated access to repositories over
HTTPS. The SPNEGO support is officialy declared only for EE edition, also
works in CE (as of fall 2019), but there are few problems with it.

On Windows workstations with non-domain setup and/or with MIT Kerberos
installed, *git.exe* requires ticket in LSA cache, which can be provided by
*mit2ms.exe*, but given that MS ecosystem can be changed anytime it might cause
serious troubles in the future (possibly with the uprise of the Credential
Guard and related technologies). Also the method leaves two possibly
out-of-sync credential caches in the system.

Kgitlab project adds SSH GSS-API support in a nice way (shell wrapper and
realtime configuration service), but there are also issues.

The main issue is that kgitlab requires credential delegation, which allows
Gitlab administrator (or an attacker) to steal kerberos tickets and thus
identity theft. Also kgitlab lacks test suite and coverage so the patching for
non-Ruby developer is uneasy.


## Instalation and usage

Clone the repository.

```
git clone https://github.com/bodik/gssgitlab /opt/gssgitlab
```

Change the GitLab shell user's shell to `/opt/gssgitlab/gssgitlabsh` by adding
following to `/etc/gitlab/gitlab.rb` and running `gitlab-ctl reconfigure`.

```
user['shell'] = "/opt/gssgitlab/gssgitlabsh"
```

Add following configuration to `sshd_config`, so sshd will export
authentication data and enforce same restrictions for *git* user as gitlab uses
for pubkey authentication.

```
ExposeAuthInfo yes
Match User git
	PasswordAuthentication no
	AllowTcpForwarding no
	X11Forwarding no
	AllowAgentForwarding no
	PermitTTY no
```


Register dummy keys for users and sync configuration for ssh and gssgitlab with
the following sequence:

```
# generate new dummy key
/opt/gssgitlab/gssgitlab.py newkey principal@REALM

# register the key to respective user in web ui

# regenerate configuration for ssh and gssgitlab
/opt/gssgitlab/gssgitlab.py syncdb
```

Then, when the user logs in with valid Kerberos credentials, and is listed in
the GitLab shell user's .k5login, and has an associated dummy SSH key, they
will be put into the GitLab shell for doing all the pulling and pushing that
they would be able to do with their normal SSH key. The ability to also
authenticate with a normal SSH key is preserved.


## Development

Development tools are not required for production usage.

```
cd /opt/gssgitlab

# ensure git settings on cloud nodes
ln -s ../../extra/git_hookprecommit.sh .git/hooks/pre-commit

# create venv for development tools
make venv
. venv/bin/activate

# install requirements and dependencies
make install-deps

# run qa, tests and coverage
make
```
