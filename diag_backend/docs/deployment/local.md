# 本地运行

```bash
cd diag_backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 若存在；否则手动创建
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 依赖服务

| 服务 | 必需 | 说明 |
|------|------|------|
| MongoDB | 是 | 本地或远程 URI |
| MES 各厂区 | 否 | 诊断/同步需要内网 |
| RAGFlow | 否 | 知识库增强 |
| OpenAI API | 否 | 无 key 走 mock |

## 文档站

```bash
cd docs && npm install && npm run docs:dev
```

## 独立同步（不启 API）

```bash
cd scripts
pip install -r requirements.txt
python sync_data.py --factory kunshan --hours 24
```
