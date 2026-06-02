"""FTP 无凭据下载路径"""
from unittest.mock import AsyncMock, patch

import pytest

from app.routers.diagnosis import (
    _download_log_tail_ftp,
    _ftp_has_explicit_credentials,
)


def test_no_explicit_credentials_detected():
    assert _ftp_has_explicit_credentials("ftp://10.30.14.12/log/a.log", None, None) is False


def test_explicit_factory_credentials():
    assert _ftp_has_explicit_credentials("ftp://10.30.14.12/log/a.log", "user", "pass") is True


@pytest.mark.asyncio
async def test_anonymous_ftp_uses_urlopen_only():
    with patch(
        "app.routers.diagnosis._download_log_tail_ftp_urlopen",
        AsyncMock(return_value=("log line 1\n", None)),
    ) as mock_urlopen:
        content, err = await _download_log_tail_ftp(
            "ftp://10.30.14.12/log//sn/test.log", 50
        )
    assert err is None
    assert "log line" in content
    mock_urlopen.assert_awaited_once()


@pytest.mark.asyncio
async def test_anonymous_ftp_does_not_fallback_to_ftplib():
    with patch(
        "app.routers.diagnosis._download_log_tail_ftp_urlopen",
        AsyncMock(return_value=("", "FTP failed")),
    ) as mock_urlopen:
        content, err = await _download_log_tail_ftp(
            "ftp://10.30.14.12/log//sn/test.log", 50
        )
    assert content == ""
    assert err == "FTP failed"
    mock_urlopen.assert_awaited_once()
