# WeaveEye 独立数据同步

数据写入 MongoDB 由本目录脚本完成，**不依赖 FastAPI 进程**。API 服务只读已同步数据，并通过 MES 直连做实时查询。

## 一键同步

```bash
cd /path/to/diag_ai_analysis

# 首次：复制配置
cp scripts/sync_config.example.yaml scripts/sync_config.yaml
# 编辑 sync_config.yaml（MongoDB、hours、厂区等）

# 执行 SIMS + MES（默认读 scripts/sync_config.yaml）
python scripts/weaveeye_sync.py run

# 或使用 shell 包装（可 source 仓库根 .env）
chmod +x scripts/run_sync.sh
./scripts/run_sync.sh
```

## 子命令

| 命令 | 说明 |
|------|------|
| `weaveeye_sync.py run` | 按 YAML 执行 SIMS + MES |
| `weaveeye_sync.py sims --hours 24` | 仅 `sync_data.py` |
| `weaveeye_sync.py mes --sync-recent 1` | 仅 `sync_mes.py` 最近 N 天 |

## 定时任务

```cron
# 每小时同步近 24 小时 SIMS + 近 1 天 MES 维修
0 * * * * cd /path/to/diag_ai_analysis && ./scripts/run_sync.sh >> /var/log/weaveeye-sync.log 2>&1
```

环境变量（可写在仓库根 `.env` 或 crontab）：

- `MONGODB_URI` / `MONGODB_DB_NAME`
- `SYNC_LOG_LEVEL`, `SYNC_LOG_DIR`

## 脚本说明

| 文件 | 作用 |
|------|------|
| `weaveeye_sync.py` | 统一入口，编排 SIMS + MES |
| `sync_data.py` | 各厂区 SIMS → `sync_remote_*` |
| `sync_mes.py` | MES 维修 → `maintenance_records` |
| `sync_config.yaml` | 本地配置（勿提交敏感信息时可 gitignore） |
| `sync_logger.py` | 同步日志 |

厂区地址与后端共用：`diag_backend/configs/factories.yaml`。

## 依赖

```bash
pip install -r scripts/requirements.txt
```
