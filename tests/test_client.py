from pathlib import Path

from flow_mcp.client import _flow_device_json, _flow_password_encrypt, extract_session_from_har


def test_extract_session_from_sanitized_har(tmp_path: Path) -> None:
    har = tmp_path / "sanitized.har"
    har.write_text(
        """
        {
          "log": {
            "entries": [
              {
                "request": {
                  "postData": {
                    "text": "_JSON_=%7B%22USER_ID%22%3A%22user%40example.com%22%2C%22RGSN_DTTM%22%3A%22FLOW_TEST%22%7D"
                  }
                }
              }
            ]
          }
        }
        """,
        encoding="utf-8",
    )

    session = extract_session_from_har(har)

    assert session.user_id == "user@example.com"
    assert session.rgsn_dttm == "FLOW_TEST"


def test_flow_password_encrypt_is_deterministic() -> None:
    encrypted = _flow_password_encrypt("password", "20260430100910")

    assert encrypted == _flow_password_encrypt("password", "20260430100910")
    assert encrypted != "password"
    assert encrypted.endswith("=")


def test_flow_device_json_matches_browser_shape() -> None:
    device = _flow_device_json()

    assert set(device) == {"DUID", "DUID_NM"}
    assert device["DUID_NM"] == f"PC-CHROME_{device['DUID']}"
    parts = device["DUID"].split("-")
    assert len(parts) == 4
    assert all(part.isdigit() for part in parts)
