from datetime import date

from kaloriekassen.withings import client


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_fetch_measurements_follows_pagination(monkeypatch):
    calls = []
    responses = iter(
        [
            {"status": 0, "body": {"measuregrps": [{"grpid": 1}], "more": 1, "offset": 5}},
            {"status": 0, "body": {"measuregrps": [{"grpid": 2}], "more": 0}},
        ]
    )

    def post(url, headers, data, timeout):
        calls.append((url, headers, data, timeout))
        return _Response(next(responses))

    monkeypatch.setattr(client, "get_access_token", lambda: "access")
    monkeypatch.setattr(client.requests, "post", post)

    payload = client.fetch_measurements(date(2026, 8, 14), date(2026, 8, 16))

    assert [group["grpid"] for group in payload["body"]["measuregrps"]] == [1, 2]
    assert calls[0][1] == {"Authorization": "Bearer access"}
    assert "offset" not in calls[0][2]
    assert calls[1][2]["offset"] == 5
