# 环境变量

完整列表见 [配置参考](/guide/configuration)。

## 生产最小集

```env
MONGODB_URI=mongodb://user:pass@host:27018/diag_analysis?authSource=admin
MONGODB_DB_NAME=diag_analysis
JWT_SECRET_KEY=<64+ random chars>
OPENAI_API_KEY=sk-...
OPENAI_API_URL=https://your-llm-gateway/v1
AI_MODEL=gpt-4-turbo
LOG_LEVEL=INFO
LOG_FILE=/var/log/weaveeye/api.log
DEBUG=false
```

## 可选

```env
RAGFLOW_API_URL=http://ragflow:9380
RAGFLOW_API_KEY=...
FACTORIES_YAML_PATH=/etc/weaveeye/factories.yaml
MES_REQUEST_TIMEOUT=45
```

## 敏感信息

- 勿 commit `.env`
- FTP 密码放 YAML 时注意文件权限
- `global_app_config` 中 api_key 应脱敏返回给前端

## pydantic-settings 规则

- 环境变量名 **大写**
- 字段名 snake_case 自动映射
