"""Unified CLI for the AWS token vending machine."""


import argparse
import pathlib
import sys

from aws_token_vending_machine.config import env, load_experiments_config
from aws_token_vending_machine.credentials import (
    DEFAULT_DURATION_SECONDS,
    DEFAULT_OUTPUT_FILE,
    DEFAULT_REGION,
    CredentialsRequest,
    write_credentials,
)
from aws_token_vending_machine.setup import ADMIN_POLICY_ARN, SetupConfig, run_setup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aws-token-vending-machine",
        description="Create AWS Organizations sandbox accounts and mint temporary credentials.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    creds = subparsers.add_parser(
        "creds",
        help="Mint temporary AWS credentials (default target: sandbox).",
    )
    creds.add_argument(
        "--target",
        choices=["sandbox", "main"],
        default="sandbox",
        help="sandbox: AssumeRole into the experiments account. main: GetSessionToken from the caller (management) account.",
    )
    creds.add_argument("--region", default=env("AWS_EXPERIMENTS_REGION", DEFAULT_REGION))
    creds.add_argument("--duration-seconds", type=int, default=DEFAULT_DURATION_SECONDS)
    creds.add_argument("--output", default=DEFAULT_OUTPUT_FILE)
    creds.add_argument("--remote-host", default=None)
    creds.add_argument("--remote-path", default=None)
    creds.add_argument(
        "--no-remote",
        action="store_true",
        help="Skip the interactive SSH-host + remote-folder picker; only write the local env file.",
    )
    creds.add_argument("--mfa-serial", default=env("AWS_EXPERIMENTS_MFA_SERIAL", None) or None)
    creds.add_argument("--mfa-code", default=None)

    setup = subparsers.add_parser(
        "setup-sandbox",
        help="Create or verify the AWS Organizations sandbox account and admin user.",
    )
    setup.add_argument("--account-email", default=env("AWS_EXPERIMENTS_ACCOUNT_EMAIL", ""))
    setup.add_argument("--account-name", default=env("AWS_EXPERIMENTS_ACCOUNT_NAME", "experiments"))
    setup.add_argument("--ou-name", default=env("AWS_EXPERIMENTS_OU_NAME", "Experiments"))
    setup.add_argument("--admin-user", default=env("AWS_EXPERIMENTS_ADMIN_USER", "experiments-admin"))
    setup.add_argument(
        "--access-role-name",
        default=env("AWS_EXPERIMENTS_ACCESS_ROLE_NAME", "OrganizationAccountAccessRole"),
    )
    setup.add_argument(
        "--credentials-file",
        default=env("AWS_EXPERIMENTS_CREDENTIALS_FILE", "initial-admin-credentials.txt"),
    )
    setup.add_argument("--admin-password", default=None)
    setup.add_argument("--rotate-password", action="store_true")
    setup.add_argument(
        "--max-session-duration",
        type=int,
        default=int(env("AWS_EXPERIMENTS_MAX_SESSION_DURATION", "7200")),
    )

    return parser


def run_creds(args: argparse.Namespace) -> int:
    ssh_client = None
    remote_host = args.remote_host
    remote_path = args.remote_path

    should_prompt = (
        not args.no_remote
        and not remote_host
        and sys.stdin.isatty()
    )
    if should_prompt:
        from aws_token_vending_machine.interactive import prompt_remote_target

        ssh_client, remote_host, remote_path = prompt_remote_target()

    request = CredentialsRequest(
        target=args.target,
        region=args.region,
        duration_seconds=args.duration_seconds,
        output=pathlib.Path(args.output),
        remote_host=remote_host,
        remote_path=remote_path,
        mfa_serial=args.mfa_serial,
        mfa_code=args.mfa_code,
    )
    try:
        expiration = write_credentials(request, ssh_client=ssh_client)
    finally:
        if ssh_client is not None:
            ssh_client.close()

    print(f"Target:  {request.target}")
    print(f"Wrote:   {request.output}")
    if request.remote_host:
        print(f"Remote:  {request.remote_host}:{request.remote_path}")
    print(f"Expires: {expiration}")
    return 0


def run_setup_command(args: argparse.Namespace) -> int:
    if not args.account_email:
        raise SystemExit("AWS_EXPERIMENTS_ACCOUNT_EMAIL is required in .env or --account-email")
    config = SetupConfig(
        account_email=args.account_email,
        account_name=args.account_name,
        ou_name=args.ou_name,
        admin_user=args.admin_user,
        access_role_name=args.access_role_name,
        credentials_file=pathlib.Path(args.credentials_file),
        admin_password=args.admin_password,
        rotate_password=args.rotate_password,
        max_session_duration=args.max_session_duration,
    )
    result = run_setup(config)

    print("## Result")
    print()
    print(f"- Management account ID: `{result.organization['MasterAccountId']}`")
    print(f"- Management account email: `{result.organization['MasterAccountEmail']}`")
    print(f"- AWS Organization ID: `{result.organization['Id']}`")
    print(f"- Organization root ID: `{result.root_id}`")
    print(f"- OU ID: `{result.ou['Id']}`")
    print(f"- Sandbox account ID: `{result.account['Id']}`")
    print(f"- Sandbox account email: `{result.account['Email']}`")
    print(f"- Sandbox account name: `{result.account['Name']}`")
    print(f"- Admin IAM user: `{result.admin_user}`")
    print(f"- Admin policy: `{ADMIN_POLICY_ARN}`")
    print(f"- Console sign-in URL: `https://{result.account['Id']}.signin.aws.amazon.com/console`")
    print(f"- Caller account used for setup: `{result.caller_account}`")
    print(f"- Password reset required: `{result.login_profile['PasswordResetRequired']}`")
    if result.credentials_file:
        print(f"- Generated password file: `{result.credentials_file}`")
    elif result.password_changed:
        print("- Admin password: updated from provided input")
    else:
        print("- Admin password: unchanged")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_experiments_config()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "creds":
        return run_creds(args)
    if args.command == "setup-sandbox":
        return run_setup_command(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
