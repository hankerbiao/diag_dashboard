---
layout: home

hero:
  name: "WeaveEye"
  text: "基于 AI 的智能设备<br>诊断与异常分析系统"
  tagline: "全链路异步架构 · 多厂区数据同步 · RAGFlow 知识库增强 · 预计算分析看板"
  actions:
    - theme: brand
      text: 快速开始
      link: /guide/getting-started
    - theme: alt
      text: AI 诊断工作流
      link: /workflows/ai-diagnosis
    - theme: alt
      text: API 参考
      link: /api/overview

features:
  - title: 智能诊断分析
    details: 基于 LLM + RAGFlow 知识库的 3 阶段管道诊断（日志下载 → 知识检索 → 推理分析），SSE 流式实时推送诊断进展。
  - title: 多厂区数据同步
    details: 独立同步脚本从各厂区 MES API 拉取测试数据，支持增量与全量同步，并发控制与断点续传。
  - title: 知识库增强
    details: 集成 RAGFlow 引擎，支持文档上传、自动解析、语义检索，诊断时自动检索相关技术文档辅助推理。
  - title: 数据看板
    details: 每小时预计算聚合快照，6 种可视化图表展示故障分布、良率趋势、工站失败等关键指标。
  - title: JWT 认证
    details: 自建 JWT 认证体系，支持 remember-me 令牌过期策略，前后端统一 Bearer Token 鉴权。
  - title: YAML 单一配置源
    details: 厂区配置统一由 YAML 文件管理，后端与同步脚本共享同一数据源，启动时自动同步到 MongoDB。
---
