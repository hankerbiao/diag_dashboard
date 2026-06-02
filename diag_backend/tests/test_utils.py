"""core.utils 单元测试"""
from app.core.utils import is_sims_record_failed, is_test_failed, is_test_passed, validate_log_path
import pytest


class TestTestResultHelpers:
    def test_passed_excludes_failed(self):
        assert is_test_passed("成功")
        assert not is_test_failed("成功")

    def test_failed_includes_chinese(self):
        assert is_test_failed("不通过")
        assert not is_test_passed("不通过")

    def test_failed_variants(self):
        assert is_test_failed("失败")
        assert is_test_failed("FAIL")
        assert not is_test_passed("失败")

    def test_wei_tong_guo_not_passed(self):
        assert not is_test_passed("未通过")
        assert is_test_failed("未通过")

    def test_sims_record_failed_by_fault_type(self):
        assert is_sims_record_failed(
            {"server_test_result": "", "fault_type1": "阻抗异常"}
        )
        assert not is_sims_record_failed({"server_test_result": "成功", "fault_type1": "x"})


class TestValidateLogPath:
    def test_rejects_traversal(self):
        with pytest.raises(ValueError):
            validate_log_path("../etc/passwd")

    def test_accepts_relative(self):
        assert validate_log_path("logs/test.log") == "logs/test.log"
