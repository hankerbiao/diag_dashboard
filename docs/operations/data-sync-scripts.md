# 数据同步脚本

## sync_data.py

从各厂区 MES API 同步测试数据到 MongoDB。

```bash
cd scripts
pip install -r requirements.txt

# 最近 24 小时
python sync_data.py

# 最近 48 小时
python sync_data.py --hours 48

# 全量同步
python sync_data.py --hours 0

# 仅同步指定厂区
python sync_data.py --factory kunshan

# 试运行（不写数据库）
python sync_data.py --dry-run
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--hours` | 回溯小时数（0=全量） | 24 |
| `--factory` | 指定厂区 ID | 所有厂区 |
| `--dry-run` | 试运行模式 | false |

### 数据流

```
读取 factories.yaml → 遍历厂区
  └→ 分页拉取 MES API → upsert 写入 sync_remote_servers
  └→ 按 SN 拉取测试明细 → upsert 写入 sync_remote_test_details
  └→ 记录同步日志 → sync_jobs
```

## sync_mes.py

从 MES 主 API 同步维修记录到 MongoDB，并上传 RAGFlow 知识库。

```bash
# 同步并上传知识库
python sync_mes.py

# 仅同步 MongoDB，不上传 RAGFlow
python sync_mes.py --no-ragflow
```

## 依赖

```txt
requests>=2.31.0
PyYAML>=6.0
pymongo>=4.9.0
tqdm>=4.66.0
```
