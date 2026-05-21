"""Mint temporary AWS credentials for sandbox (AssumeRole) or main (GetSessionToken)."""


import pathlib
from dataclasses import dataclass
from typing import Literal

import boto3

from aws_sandbox_cli.config import env, require_env
from aws_sandbox_cli.env_file import update_env_file
from aws_sandbox_cli.remote import (
    update_remote_env_file,
    verify_remote,
    write_remote_env_via_sftp,
)


Target = Literal["sandbox", "main"]

DEFAULT_REGION = "eu-west-1"
DEFAULT_DURATION_SECONDS = 7200
DEFAULT_OUTPUT_FILE = "experiments-env"
SANDBOX_SESSION_NAME = "token-vending-machine-sandbox"


@dataclass(frozen=True)
class CredentialsRequest:
    target: Target
    region: str
    duration_seconds: int
    output: pathlib.Path
    remote_host: str | None
    remote_path: str | None
    mfa_serial: str | None
    mfa_code: str | None


def fetch_sandbox_credentials(request: CredentialsRequest) -> tuple[dict[str, str], str]:
    account_id = require_env("AWS_EXPERIMENTS_ACCOUNT_ID")
    role_name = env("AWS_EXPERIMENTS_ACCESS_ROLE_NAME", "OrganizationAccountAccessRole")
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    sts = boto3.client("sts")
    response = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName=SANDBOX_SESSION_NAME,
        DurationSeconds=request.duration_seconds,
    )
    creds = response["Credentials"]
    expiration = creds["Expiration"].isoformat()

    return (
        {
            "AWS_ACCESS_KEY_ID": creds["AccessKeyId"],
            "AWS_SECRET_ACCESS_KEY": creds["SecretAccessKey"],
            "AWS_SESSION_TOKEN": creds["SessionToken"],
            "AWS_DEFAULT_REGION": request.region,
            "AWS_REGION": request.region,
            "AWS_ACCOUNT_ID": account_id,
            "AWS_CREDENTIAL_EXPIRATION": expiration,
        },
        expiration,
    )


def fetch_main_credentials(request: CredentialsRequest) -> tuple[dict[str, str], str]:
    sts = boto3.client("sts")
    kwargs: dict = {"DurationSeconds": request.duration_seconds}
    if request.mfa_serial:
        kwargs["SerialNumber"] = request.mfa_serial
        if not request.mfa_code:
            raise SystemExit("--mfa-code is required when --mfa-serial is set")
        kwargs["TokenCode"] = request.mfa_code

    response = sts.get_session_token(**kwargs)
    creds = response["Credentials"]
    expiration = creds["Expiration"].isoformat()
    account_id = sts.get_caller_identity()["Account"]

    return (
        {
            "AWS_ACCESS_KEY_ID": creds["AccessKeyId"],
            "AWS_SECRET_ACCESS_KEY": creds["SecretAccessKey"],
            "AWS_SESSION_TOKEN": creds["SessionToken"],
            "AWS_DEFAULT_REGION": request.region,
            "AWS_REGION": request.region,
            "AWS_ACCOUNT_ID": account_id,
            "AWS_CREDENTIAL_EXPIRATION": expiration,
        },
        expiration,
    )


def fetch_credentials(request: CredentialsRequest) -> tuple[dict[str, str], str]:
    if request.target == "sandbox":
        return fetch_sandbox_credentials(request)
    if request.target == "main":
        return fetch_main_credentials(request)
    raise SystemExit(f"Unknown target: {request.target}")


def write_credentials(request: CredentialsRequest, ssh_client=None) -> str:
    updates, expiration = fetch_credentials(request)
    update_env_file(request.output, updates)

    if request.remote_host:
        if not request.remote_path:
            raise SystemExit("--remote-path is required when --remote-host is set")
        if ssh_client is not None:
            write_remote_env_via_sftp(ssh_client, request.remote_path, updates)
        else:
            update_remote_env_file(request.remote_host, request.remote_path, updates)
            verify_remote(request.remote_host, request.remote_path)

    return expiration
