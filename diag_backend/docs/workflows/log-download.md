# 日志下载

## URL 构建

`build_log_download_url(log_base_url, log_path, user?, password?)`

### HTTP 厂区

```
log_base_url: http://10.8.102.89/log
log_path:     /path/to/file.log
→ http://10.8.102.89/log/path/to/file.log
```

### FTP 厂区

- `log_base_url`: `ftp://10.30.14.12`
- SIMS 路径常需 **`/log//`** 双斜杠前缀（与 `download_ftp.py` 一致）
- 非匿名：YAML 配置 `log_ftp_user` / `log_ftp_password` 或 URL 嵌入

## 校验

`validate_log_path` — 允许 leading `/`（SIMS 原始格式）。

## 大小限制

`MAX_LOG_BYTES = 2MB`，超出截断；分析取 tail `LOG_TAIL_LINES = 50`。

## API

- `POST /api/diagnosis/sn/log-content`
- 剖析管道内部同样逻辑

## 测试

- `tests/test_build_log_url.py`
- `tests/test_ftp_urlopen.py`
- `tests/test_validate_log_path.py`

## 排查

1. 浏览器/curl 直接访问拼好的 URL
2. FTP 用 `download_ftp.py` 对照
3. 检查厂区是否选对（log_base_url  per factory）
