# aws-token-vending-machine

Create AWS Organizations sandbox accounts and mint temporary AWS credentials with one command.

It does two things:

1. `setup-sandbox` — creates (or verifies) an AWS Organizations member account in a chosen OU, attaches `AdministratorAccess` to an admin IAM user, and writes the initial password to a local file.
2. `creds` — mints temporary AWS credentials and writes them as a `KEY=value` env file (locally and optionally to a remote host over SSH). Default target is the sandbox account (`AssumeRole`). With `--target main` it mints credentials for the management account (`GetSessionToken`).

## Why

Working from long-term root or admin keys is risky. This tool keeps a single configured "vending machine" so each session uses short-lived credentials in an isolated sandbox account, while the management account stays mostly unused.

## Install

Requires Python 3.13+ and AWS credentials configured for your management (main) account.

```sh
git clone https://github.com/<you>/aws-token-vending-machine.git
cd aws-token-vending-machine
uv sync
```

Or install as a tool:

```sh
uv tool install .
```

## Configure

Copy `.env.example` to `.env` and fill in your values:

```sh
cp .env.example .env
$EDITOR .env
```

`.env` holds non-secret identifiers (account IDs, OU name, admin user name). It is git-ignored. All sensitive material — passwords and temporary credentials — is written to separate files that are also git-ignored.

## Use

### Mint sandbox credentials (default)

```sh
uv run aws-token-vending-machine creds
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
uv run aws-token-vending-machine creds --target main
```

This calls `sts:GetSessionToken` on your current credentials, returning short-lived credentials for the same (management) account.

If your IAM user has an MFA policy attached (a common pattern is to require MFA for any non-trivial action), `GetSessionToken` will fail without an MFA challenge. In that case pass:

- `--mfa-serial` — the ARN of your MFA device. You can find it in the IAM console under your user (Security credentials → Multi-factor authentication), or via `aws iam list-mfa-devices --user-name <you>`. For a virtual MFA device it looks like `arn:aws:iam::<main-account-id>:mfa/<your-user>`; for a hardware key it's a different ARN format. You can also set it once in `.env` as `AWS_EXPERIMENTS_MFA_SERIAL` so you don't have to pass it every time.
- `--mfa-code` — the 6-digit one-time code currently shown by your MFA app (Authy, 1Password, Google Authenticator, YubiKey, etc.). It must be the live code, not a previously-used one — `GetSessionToken` rejects already-consumed codes.

```sh
uv run aws-token-vending-machine creds --target main \
  --mfa-serial arn:aws:iam::<main-account-id>:mfa/<your-user> \
  --mfa-code 123456
```

The returned session credentials then satisfy MFA for the rest of their lifetime (`--duration-seconds`, default 2 hours), so you only enter the code once per session.

### Push credentials to a remote host over SSH

```sh
uv run aws-token-vending-machine creds \
  --remote-host <ssh-host> \
  --remote-path '~/tmp/lambda-deploy/.env'
```

The remote file is created if missing; existing AWS keys are updated; unrelated keys and comments are preserved.

### Create or verify the sandbox account

```sh
uv run aws-token-vending-machine setup-sandbox
```

This is idempotent: it finds-or-creates the OU, finds-or-creates the member account, ensures it lives in the right OU, attaches `AdministratorAccess`, and creates a login profile if missing. To rotate the admin password:

```sh
uv run aws-token-vending-machine setup-sandbox --admin-password '<new>' --rotate-password
```

## CLI reference

```text
aws-token-vending-machine setup-sandbox
  --account-email        default: $AWS_EXPERIMENTS_ACCOUNT_EMAIL
  --account-name         default: experiments
  --ou-name              default: Experiments
  --admin-user           default: experiments-admin
  --access-role-name     default: OrganizationAccountAccessRole
  --credentials-file     default: initial-admin-credentials.txt
  --admin-password       default: random
  --rotate-password      rotate even if a login profile exists
  --max-session-duration default: 7200

aws-token-vending-machine creds
  --target               sandbox | main   (default: sandbox)
  --region               default: eu-west-1
  --duration-seconds     default: 7200
  --output               default: experiments-env
  --remote-host          optional SSH host
  --remote-path          optional remote env path
  --mfa-serial           optional, main target only
  --mfa-code             required when --mfa-serial is set
```

## Layout

```text
aws_token_vending_machine/
  __main__.py       python -m aws_token_vending_machine
  cli.py            argparse entry point
  config.py         load AWS_EXPERIMENTS_* from .env
  credentials.py    AssumeRole (sandbox) / GetSessionToken (main)
  env_file.py       merge KEY=value into a local env file
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
