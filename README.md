# gssgitlab

gssgitlab is a shell wrapper for Gitlab to provide SSH GSS-API authenticated
access to the repositories.

The tool adds layer of Gitlab authorization on the top of the SSH GSS-API
authentication support, which originaly lacks ForcedCommand feature (used by
SSH Pubkey Gitlab access). gssgitlab acts as shell for `git` handling remote
logons for gitlab users and passing through local invocations for system
services. Also allows simple identity management functions for the system
administrator.

Project is heavily inspired by (Kgitlab)[https://github.com/iamjamestl/kgitlab]. 


## Motivation

Gitlab allows Kerberos (SPNEGO) authenticated access to repositories over
HTTPS. The SPNEGO support is officialy declared only for EE edition, also
works in CE (as of fall 2019), but there are few problems with it.

On Windows workstations with non-domain setup and/or with MIT Kerberos
installed, `git.exe` requires ticket in LSA cache, which can be provided by
`mit2ms.exe`, but given that MS ecosystem can be changed anytime it might cause
serious troubles in the future (possibly with the uprise of the Credential
Guard and related technologies). Also the method leaves two possibly
out-of-sync credential caches in the system.

Kgitlab project solves the SSH GSS-API in nice way (shell wrapper with realtime
configuration service), but there are also issues.

The main issue is that kgitlab requires credential delegation, which allows
Gitlab administrator (or an attacker) to steal kerberos tickets and thus
identity theft attack. Kgitlab completely lacks test suite or coverage so the
patching for non-Ruby developer is uneasy.


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

Add folowwing to `sshd_config` to match Gitlab SSH Pubkey constraints and
restart SSH service.

```
Match User git
	PasswordAuthentication no
	AllowTcpForwarding no
	X11Forwarding no
	AllowAgentForwarding no
	PermitTTY no
	PrintMotd no
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