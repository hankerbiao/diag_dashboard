"""日志下载 URL 拼接（FTP /log// 前缀）"""
from app.core.utils import build_log_download_url


def test_ftp_inserts_log_prefix_when_missing():
    url = build_log_download_url(
        "ftp://10.39.102.31",
        "/6102261604345142/2078_20260602151527_test.log",
    )
    assert url == "ftp://10.39.102.31/log//6102261604345142/2078_20260602151527_test.log"


def test_ftp_keeps_existing_log_prefix():
    url = build_log_download_url(
        "ftp://10.30.14.12",
        "log//6102202904362178/1059_20260602103945_result.log",
    )
    assert url == "ftp://10.30.14.12/log//6102202904362178/1059_20260602103945_result.log"


def test_http_join_relative_path():
    url = build_log_download_url(
        "http://10.8.102.89/log",
        "6102261604345142/2078_test.log",
    )
    assert url == "http://10.8.102.89/log/6102261604345142/2078_test.log"
