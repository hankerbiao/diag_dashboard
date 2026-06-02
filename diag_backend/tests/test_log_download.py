"""FTP 日志下载错误描述"""
import ftplib

from app.routers.diagnosis import _describe_ftp_error


def test_describe_ftp_login_denied():
    err = ftplib.error_perm("530 Login authentication failed")
    msg = _describe_ftp_error(
        err,
        host="10.30.14.12",
        port=21,
        path="/logs/test.log",
        auth_user="anonymous",
        used_anonymous=True,
    )
    assert "530" in msg
    assert "log_ftp_user" in msg
    assert "host=10.30.14.12:21" in msg


def test_describe_ftp_file_not_found():
    err = ftplib.error_perm("550 File not found")
    msg = _describe_ftp_error(
        err,
        host="10.39.102.31",
        port=21,
        path="/missing.log",
        auth_user="mes",
        used_anonymous=False,
    )
    assert "550" in msg
    assert "hint=文件不存在" in msg
