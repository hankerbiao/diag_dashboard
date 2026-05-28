# 前端部署

## 构建

```bash
cd diag_frontend

# 1. 安装依赖
npm install

# 2. 配置 API 地址
echo "VITE_API_BASE_URL=https://your-api-domain.com" > .env.local

# 3. 生产构建
npm run build   # 输出到 dist/
```

## 静态服务

使用 Nginx 部署：

```nginx
server {
    listen 80;
    server_name your-frontend-domain.com;

    root /path/to/diag_frontend/dist;
    index index.html;

    # SPA 路由重定向
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理（可选）
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

## SSE 支持

诊断功能使用 SSE 流式响应，确保 Nginx 不缓冲 SSE：

```nginx
location /api/diagnosis/ {
    proxy_pass http://localhost:8000;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header X-Accel-Buffering no;
}
```
