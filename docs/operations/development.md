# 开发环境

## 常用命令

### 后端

```bash
# 启动开发服务器（热重载）
cd diag_backend
uvicorn app.main:app --reload --port 8000

# 运行测试
pytest
pytest --cov=app --cov-report=term-missing

# 代码检查
ruff check .
ruff format .
```

### 前端

```bash
cd diag_frontend

# 启动开发服务器
npm run dev

# TypeScript 类型检查
npm run lint

# 生产构建
npm run build
```

### 文档

```bash
cd docs

# 启动文档预览
npm run docs:dev

# 构建文档
npm run docs:build
```

## 调试技巧

### 后端日志

后端日志输出到 stdout，`logger.exception()` 会打印完整堆栈。

### SSE 测试

```bash
curl -N -X POST "http://localhost:8000/api/diagnosis/error-log/{id}/analyze?log_base_url=..."
```

### 直播日志

```bash
tail -f /path/to/log
```
