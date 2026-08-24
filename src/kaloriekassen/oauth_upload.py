"""Upload OAuth artifacts to the NAS through the existing OpenSSH client."""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    import paramiko


logger = logging.getLogger(__name__)
_SSH_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _boolean_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _ssh_settings() -> tuple[str, int, str]:
    host = os.getenv("NAS_SSH_HOST", "").strip()
    user = os.getenv("NAS_SSH_USER", "").strip()
    remote_directory = os.getenv("NAS_SECRETS_DIR", "").strip().rstrip("/")
    if not host or not user or not remote_directory:
        raise ValueError(
            "NAS_SSH_HOST, NAS_SSH_USER and NAS_SECRETS_DIR are required "
            "when OAUTH_UPLOAD_TO_NAS is enabled"
        )
    if not _SSH_NAME.fullmatch(host) or not _SSH_NAME.fullmatch(user):
        raise ValueError("NAS_SSH_HOST and NAS_SSH_USER contain invalid characters")
    if not re.fullmatch(r"/[A-Za-z0-9._/-]+", remote_directory):
        raise ValueError("NAS_SECRETS_DIR must be an absolute POSIX path")
    try:
        port = int(os.getenv("NAS_SSH_PORT", "22"))
    except ValueError as error:
        raise ValueError("NAS_SSH_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("NAS_SSH_PORT must be between 1 and 65535")
    return f"{user}@{host}", port, remote_directory


def _identity_arguments() -> list[str]:
    identity_file = os.getenv("NAS_SSH_IDENTITY_FILE", "").strip()
    return ["-i", identity_file] if identity_file else []


def _password() -> str | None:
    password = os.getenv("NAS_SSH_PASSWORD")
    return password if password else None


def _upload_file(path: Path, target: str, port: int, remote_directory: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"OAuth artifact not found: {path}")
    if not _SSH_NAME.fullmatch(path.name):
        raise ValueError(f"OAuth artifact has an unsafe filename: {path.name}")

    temporary_name = f".{path.name}.{uuid.uuid4().hex}.tmp"
    temporary_path = f"{remote_directory}/{temporary_name}"
    final_path = f"{remote_directory}/{path.name}"
    identity = _identity_arguments()

    subprocess.run(
        [
            "scp",
            "-q",
            "-P",
            str(port),
            *identity,
            str(path),
            f"{target}:{temporary_path}",
        ],
        check=True,
    )
    remote_command = (
        f"chmod 600 -- {shlex.quote(temporary_path)} && "
        f"mv -f -- {shlex.quote(temporary_path)} {shlex.quote(final_path)}"
    )
    subprocess.run(
        ["ssh", "-p", str(port), *identity, target, remote_command],
        check=True,
    )


def _connect_with_password(
    target: str, port: int, password: str
) -> "paramiko.SSHClient":
    import paramiko

    user, host = target.split("@", maxsplit=1)
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(
        hostname=host,
        port=port,
        username=user,
        password=password,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def _upload_files_with_password(
    paths: Iterable[Path],
    target: str,
    port: int,
    remote_directory: str,
    password: str,
) -> None:
    client = _connect_with_password(target, port, password)
    try:
        sftp = client.open_sftp()
        try:
            for path in paths:
                if not path.is_file():
                    raise FileNotFoundError(f"OAuth artifact not found: {path}")
                if not _SSH_NAME.fullmatch(path.name):
                    raise ValueError(
                        f"OAuth artifact has an unsafe filename: {path.name}"
                    )

                temporary_name = f".{path.name}.{uuid.uuid4().hex}.tmp"
                temporary_path = f"{remote_directory}/{temporary_name}"
                final_path = f"{remote_directory}/{path.name}"
                sftp.put(str(path), temporary_path)
                sftp.chmod(temporary_path, 0o600)
                _, stdout, stderr = client.exec_command(
                    f"mv -f -- {shlex.quote(temporary_path)} {shlex.quote(final_path)}"
                )
                exit_status = stdout.channel.recv_exit_status()
                if exit_status:
                    error = stderr.read().decode("utf-8", errors="replace").strip()
                    raise RuntimeError(
                        f"Could not install OAuth artifact on NAS: {error}"
                    )
        finally:
            sftp.close()
    finally:
        client.close()


def upload_oauth_artifacts(
    paths: Iterable[Path],
    *,
    remove_after_upload: Iterable[Path] = (),
) -> bool:
    """Upload files atomically when enabled and optionally remove local tokens.

    OpenSSH performs host-key verification and authentication using the user's
    normal SSH configuration. Local files are retained if any upload fails.
    """
    if not _boolean_env("OAUTH_UPLOAD_TO_NAS"):
        return False

    target, port, remote_directory = _ssh_settings()
    artifacts = [Path(path) for path in paths]
    password = _password()
    if password:
        _upload_files_with_password(artifacts, target, port, remote_directory, password)
    else:
        for artifact in artifacts:
            _upload_file(artifact, target, port, remote_directory)

    if _boolean_env("OAUTH_DELETE_LOCAL_TOKEN_AFTER_UPLOAD", default=True):
        for path in remove_after_upload:
            Path(path).unlink(missing_ok=True)

    logger.info(
        "Uploaded %d OAuth artifact(s) to %s:%s.",
        len(artifacts),
        target,
        remote_directory,
    )
    return True
