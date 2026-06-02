import pytest

from app.core.utils import validate_log_path


def test_validate_log_path_allows_mes_leading_slash():
    assert validate_log_path("/6102261604345142/2078_test.log") == "/6102261604345142/2078_test.log"
    assert validate_log_path("/log//610226/file.log") == "/log//610226/file.log"


def test_validate_log_path_rejects_traversal():
    with pytest.raises(ValueError, match="无效的日志路径"):
        validate_log_path("../etc/passwd")
