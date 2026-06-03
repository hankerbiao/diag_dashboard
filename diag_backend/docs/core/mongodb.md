# MongoDB 连接

**文件：** `app/core/mongodb.py`

## API

| 函数 | 说明 |
|------|------|
| `connect_mongodb()` | 创建 Motor client，ping，建索引，seed |
| `close_mongodb()` | 关闭 client |
| `get_database()` | 返回 `AsyncIOMotorDatabase` |
| `get_collection(name)` | 快捷取 collection |

## 连接模型

```python
_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None
```

全局单连接池；**无**多租户分库。

## 错误处理

未连接时 `get_database()` 抛出：

```python
RuntimeError("MongoDB not connected. Call connect_mongodb() first.")
```

路由仅在 lifespan 之后可达，正常不会触发。

## 与 PyMongo 异常

Service 层捕获 `pymongo.errors.OperationFailure`（如聚合 175 重试）。

## 集合命名

全部 snake_case，无前缀。库名由 `MONGODB_DB_NAME` 控制（默认 `diag_analysis`）。
