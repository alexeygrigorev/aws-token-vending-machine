.DEFAULT_GOAL := help

.PHONY: help install creds creds-local creds-main setup-sandbox

help:
	@echo "Available targets:"
	@echo "  make install         Sync dependencies with uv"
	@echo "  make creds           Mint sandbox credentials (interactive remote picker)"
	@echo "  make creds-local     Mint sandbox credentials, local file only"
	@echo "  make creds-main      Mint credentials for the management account (GetSessionToken)"
	@echo "  make setup-sandbox   Create or verify the AWS Organizations sandbox account"

install:
	uv sync

creds:
	uv run aws-token-vending-machine creds

creds-local:
	uv run aws-token-vending-machine creds --no-remote

creds-main:
	uv run aws-token-vending-machine creds --target main

setup-sandbox:
	uv run aws-token-vending-machine setup-sandbox
