import subprocess

import pytest

from kaloriekassen import oauth_upload


def _enable_upload(monkeypatch):
    monkeypatch.setenv("OAUTH_UPLOAD_TO_NAS", "true")
    monkeypatch.setenv("NAS_SSH_HOST", "nas")
    monkeypatch.setenv("NAS_SSH_USER", "bruger")
    monkeypatch.setenv("NAS_SSH_PORT", "22")
    monkeypatch.setenv("NAS_SECRETS_DIR", "/volume1/docker/kaloriekassen/secrets")


def test_upload_is_disabled_by_default(tmp_path, monkeypatch):
    token = tmp_path / "token.json"
    token.write_text("{}")
    calls = []
    monkeypatch.delenv("OAUTH_UPLOAD_TO_NAS", raising=False)
    monkeypatch.setattr(oauth_upload.subprocess, "run", lambda *args, **kwargs: calls.append(args))

    assert oauth_upload.upload_oauth_artifacts([token]) is False
    assert calls == []
    assert token.exists()


def test_upload_uses_scp_and_atomic_remote_rename(tmp_path, monkeypatch):
    _enable_upload(monkeypatch)
    client = tmp_path / "client.json"
    token = tmp_path / "token.json"
    client.write_text("client")
    token.write_text("token")
    calls = []
    monkeypatch.setattr(
        oauth_upload.subprocess,
        "run",
        lambda command, check: calls.append((command, check)),
    )
    monkeypatch.setattr(oauth_upload.uuid, "uuid4", lambda: type("U", (), {"hex": "abc"})())

    uploaded = oauth_upload.upload_oauth_artifacts(
        [client, token],
        remove_after_upload=[token],
    )

    assert uploaded is True
    assert client.exists()
    assert not token.exists()
    assert [call[0][0] for call in calls] == ["scp", "ssh", "scp", "ssh"]
    assert calls[0][0][-1].endswith("/.client.json.abc.tmp")
    assert "mv -f" in calls[1][0][-1]
    assert all(call[1] is True for call in calls)


def test_failed_upload_keeps_local_token(tmp_path, monkeypatch):
    _enable_upload(monkeypatch)
    token = tmp_path / "token.json"
    token.write_text("token")
    monkeypatch.setattr(
        oauth_upload.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, "scp")
        ),
    )

    with pytest.raises(subprocess.CalledProcessError):
        oauth_upload.upload_oauth_artifacts(
            [token],
            remove_after_upload=[token],
        )

    assert token.exists()
