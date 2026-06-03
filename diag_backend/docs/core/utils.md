# 工具函数

**文件：** `app/core/utils.py`

## 时间

| 函数 | 说明 |
|------|------|
| `utc_now()` | timezone-aware datetime |
| `utc_now_iso()` | ISO 字符串，写 MongoDB |

## 测试状态

| 函数 | 说明 |
|------|------|
| `is_test_failed(status)` | 判定失败文案 |
| `is_sims_record_failed(record)` | SIMS 行是否失败 |

## 日志路径与下载

| 函数 | 说明 |
|------|------|
| `validate_log_path(path)` | 允许 SIMS  leading `/` |
| `build_log_download_url(log_base_url, log_path, ftp_user?, ftp_pass?)` | 拼 HTTP/FTP URL；FTP 加 `/log//` 前缀 |

FTP 逻辑与 `download_ftp.py` 对齐，测试见 `test_build_log_url.py`。

## MongoDB

| 函数 | 说明 |
|------|------|
| `parse_object_id(id_str)` | 安全转 ObjectId |

## 使用注意

- 日志 URL 不要在日志中打印完整 FTP 密码
- `build_log_download_url` 对 anonymous FTP 仅用 urllib
