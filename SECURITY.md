# Security Policy

Setlist is a personally maintained project intended for a small public homelab
deployment. Security fixes are welcome.

## Supported version

The latest published release and the current default branch are supported.
Older releases, commits, forks, and modified deployments may not receive fixes.

## Reporting a vulnerability

Please do not disclose an unpatched vulnerability, working exploit, secret, or
private deployment detail in a public issue.

Use GitHub's **Report a vulnerability** flow on the repository's Security page
when private vulnerability reporting is available. If it is not available,
open a minimal issue asking the maintainer for a private contact method; do not
include exploit instructions or sensitive evidence in that issue.

Include, when safe:

- the affected route, component, or revision;
- the expected and observed behavior;
- the practical impact;
- minimal reproduction steps;
- any suggested mitigation.

There is no guaranteed response-time SLA for this personal homelab project.
Reports that affect authentication, authorization, CSRF, secret exposure,
trusted-proxy handling, or remote code execution should be treated as urgent.

## Deployment responsibilities

Operators are responsible for:

- terminating public traffic with HTTPS;
- keeping FastAPI and PostgreSQL off public host ports;
- using unique secrets and rotating them after suspected disclosure;
- restricting `TRUSTED_PROXY_CIDRS` and `CORS_ORIGINS`;
- keeping containers, Python packages, npm packages, and the host patched;
- backing up and protecting PostgreSQL data and reverse-proxy logs;
- adding a shared external rate limiter before running multiple API replicas.

The built-in guest limiter is in-process and is not a distributed
denial-of-service defense.

## If a secret is exposed

Removing a secret from the latest commit is not enough.

1. Revoke or rotate the credential immediately.
2. Rotate `SESSION_SECRET` to invalidate all administrator sessions when
   session integrity may be affected.
3. Replace `ADMIN_PASSWORD_HASH` and the administrator password when relevant.
4. Change the database password and update all dependent services when
   relevant.
5. Review Git history, CI logs, container layers, and deployment logs.
6. Rewrite public history only after rotation, and coordinate with anyone who
   has cloned the repository.

Run `python scripts/check_secrets.py` before publishing changes. It detects
several high-confidence credential signatures in the working tree and Git
history, but it cannot prove that a repository contains no secrets.
