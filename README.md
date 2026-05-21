# aws-sandbox-cli

Personal CLI for working out of an AWS Organizations sandbox account: create the sandbox once, then mint short-lived credentials whenever you need them.

> **Not the same as [aws-workshop-credentials](https://github.com/alexeygrigorev/aws-workshop-credentials).** That one is a Lambda service that vends credentials to many workshop participants over HTTP. This one is a local CLI for your own daily work.

It does two things:

1. `setup-sandbox` — creates (or verifies) an AWS Organizations member account in a chosen OU, attaches `AdministratorAccess` to an admin IAM user, and writes the initial password to a local file.
2. `creds` — mints temporary AWS credentials and writes them as a `KEY=value` env file (locally and optionally to a remote host over SSH). Default target is the sandbox account (`AssumeRole`). With `--target main` it mints credentials for the management account (`GetSessionToken`).

## Why

Working from long-term root or admin keys is risky. This tool keeps a single configured CLI so each session uses short-lived credentials in an isolated sandbox account, while the management account stays mostly unused.

## Install

Requires Python 3.13+ and AWS credentials configured for your management (main) account.

```sh
git clone https://github.com/alexeygrigorev/aws-sandbox-cli.git
cd aws-sandbox-cli
uv sync
```

Or install as a tool:

```sh
uv tool install .
```

This installs two console scripts: `aws-sandbox-cli` and the short alias `asc`.

## Configure

Copy `.env.example` to `.env` and fill in your values:

```sh
cp .env.example .env
$EDITOR .env
```

`.env` holds non-secret identifiers (account IDs, OU name, admin user name). It is git-ignored. All sensitive material — passwords and temporary credentials — is written to separate files that are also git-ignored.

## Use

A `Makefile` wraps the common invocations:

```sh
make creds          # interactive: pick remote host + folder, drop .env there
make creds-local    # local env file only, no remote prompt
make creds-main     # GetSessionToken for the management account
make setup-sandbox  # create or verify the AWS Organizations sandbox account
```

Or call the CLI directly:

### Mint sandbox credentials (default)

```sh
uv run aws-sandbox-cli creds
```

This calls `sts:AssumeRole` into the sandbox `OrganizationAccountAccessRole` and writes an env file (default: `experiments-env`):

```text
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...
AWS_DEFAULT_REGION=eu-west-1
AWS_REGION=eu-west-1
AWS_ACCOUNT_ID=<sandbox-account-id>
AWS_CREDENTIAL_EXPIRATION=<iso8601>
```

Load it into your shell:

```sh
set -a; . ./experiments-env; set +a
aws sts get-caller-identity
```

### Mint main-account credentials

```sh
uv run aws-sandbox-cli creds --target main
```

This calls `sts:GetSessionToken` on your current credentials, returning short-lived credentials for the same (management) account.

### Push credentials to a remote host over SSH

By default, `creds` prompts you interactively for where to push the env file:

```sh
uv run aws-sandbox-cli creds
```

You'll be prompted to:

1. Pick a host from `~/.ssh/config` (or type a custom one).
2. Navigate the remote filesystem with arrow keys. Each menu shows the current directory's subfolders plus `../` (up) and `[write .env here: <path>/.env]` (commit). The same SSH connection is reused for navigation and writing, so it's fast.

The file is always named `.env` in the folder you pick. Existing AWS keys are updated; unrelated keys and comments are preserved.

To skip the prompt and only write the local env file:

```sh
uv run aws-sandbox-cli creds --no-remote
```

Non-interactive remote (for scripts and CI — the prompt is also auto-skipped when stdin isn't a TTY):

```sh
uv run aws-sandbox-cli creds \
  --remote-host <ssh-host> \
  --remote-path '~/tmp/lambda-deploy/.env'
```

### Create or verify the sandbox account

```sh
uv run aws-sandbox-cli setup-sandbox
```

This is idempotent: it finds-or-creates the OU, finds-or-creates the member account, ensures it lives in the right OU, attaches `AdministratorAccess`, and creates a login profile if missing. To rotate the admin password:

```sh
uv run aws-sandbox-cli setup-sandbox --admin-password '<new>' --rotate-password
```

## CLI reference

```text
aws-sandbox-cli setup-sandbox
  --account-email        default: $AWS_EXPERIMENTS_ACCOUNT_EMAIL
  --account-name         default: experiments
  --ou-name              default: Experiments
  --admin-user           default: experiments-admin
  --access-role-name     default: OrganizationAccountAccessRole
  --credentials-file     default: initial-admin-credentials.txt
  --admin-password       default: random
  --rotate-password      rotate even if a login profile exists
  --max-session-duration default: 7200

aws-sandbox-cli creds
  --target               sandbox | main   (default: sandbox)
  --region               default: eu-west-1
  --duration-seconds     default: 7200
  --output               default: experiments-env
  --no-remote            skip the interactive remote-host/folder picker
  --remote-host          optional SSH host (skips interactive picker)
  --remote-path          optional remote env path
```

## Layout

```text
aws_sandbox_cli/
  __main__.py       python -m aws_sandbox_cli
  cli.py            argparse entry point
  config.py         load AWS_EXPERIMENTS_* from .env
  credentials.py    AssumeRole (sandbox) / GetSessionToken (main)
  env_file.py       merge KEY=value into a local env file
  interactive.py    SSH-host + remote-folder picker (paramiko + questionary)
  remote.py         merge KEY=value into a remote env file over SSH
  setup.py          AWS Organizations account + admin user
```

## Required IAM permissions

The credentials you run this with (typically your management-account admin) need:

- `organizations:*` for `setup-sandbox` (or the read-only equivalents plus `CreateAccount`, `MoveAccount`, `CreateOrganizationalUnit`)
- `sts:AssumeRole` on the sandbox `OrganizationAccountAccessRole` for `creds --target sandbox`
- `sts:GetSessionToken` for `creds --target main`

## License

MIT — see [LICENSE](LICENSE).
