import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'WeaveEye Backend',
  description: 'WeaveEye 后端（FastAPI）开发与运维文档',
  lang: 'zh-CN',
  base: '/',
  cleanUrls: true,
  lastUpdated: true,

  themeConfig: {
    logo: '/logo.svg',
    nav: [
      { text: '首页', link: '/' },
      { text: '快速入门', link: '/guide/getting-started' },
      { text: '架构', link: '/architecture/overview' },
      { text: 'API', link: '/api/overview' },
      { text: '运维', link: '/operations/troubleshooting' },
    ],
    sidebar: {
      '/guide/': [
        {
          text: '开发指南',
          items: [
            { text: '快速入门', link: '/guide/getting-started' },
            { text: '项目结构', link: '/guide/project-structure' },
            { text: '本地开发流程', link: '/guide/development-workflow' },
            { text: '配置参考', link: '/guide/configuration' },
            { text: '测试', link: '/guide/testing' },
          ],
        },
      ],
      '/architecture/': [
        {
          text: '架构设计',
          items: [
            { text: '系统概览', link: '/architecture/overview' },
            { text: '分层设计', link: '/architecture/layered-design' },
            { text: '应用生命周期', link: '/architecture/lifecycle' },
            { text: '数据流', link: '/architecture/data-flow' },
          ],
        },
      ],
      '/core/': [
        {
          text: 'Core 模块',
          items: [
            { text: '配置 (config)', link: '/core/config' },
            { text: 'MongoDB 连接', link: '/core/mongodb' },
            { text: '索引与 Seed', link: '/core/indexes' },
            { text: '认证 (auth)', link: '/core/auth' },
            { text: '厂区配置', link: '/core/factory-config' },
            { text: '日志', link: '/core/logger' },
            { text: '工具函数', link: '/core/utils' },
          ],
        },
      ],
      '/routers/': [
        {
          text: '路由层',
          items: [
            { text: '路由总览', link: '/routers/overview' },
            { text: '认证 auth', link: '/routers/auth' },
            { text: '诊断 diagnosis', link: '/routers/diagnosis' },
            { text: '异常 error-logs', link: '/routers/error-logs' },
            { text: '分析 analytics', link: '/routers/analytics' },
            { text: '同步 sync', link: '/routers/sync' },
            { text: '知识库 knowledge-base', link: '/routers/knowledge-base' },
            { text: '设置 settings', link: '/routers/settings' },
            { text: '厂区 factories', link: '/routers/factories' },
          ],
        },
      ],
      '/services/': [
        {
          text: '服务层',
          items: [
            { text: '服务总览', link: '/services/overview' },
            { text: 'LLM 服务', link: '/services/llm-service' },
            { text: '知识图谱', link: '/services/knowledge-graph' },
            { text: 'RAGFlow', link: '/services/ragflow-service' },
            { text: 'MES 直连', link: '/services/mes-direct-service' },
            { text: '分析看板', link: '/services/analytics-service' },
            { text: '同步服务', link: '/services/sync-service' },
            { text: '同步调度器', link: '/services/sync-scheduler' },
            { text: '异常日志', link: '/services/error-logs-service' },
          ],
        },
      ],
      '/workflows/': [
        {
          text: '业务工作流',
          items: [
            { text: 'JWT 认证', link: '/workflows/authentication' },
            { text: 'SN 单机诊断', link: '/workflows/sn-diagnosis' },
            { text: '异常日志智能剖析', link: '/workflows/error-log-analysis' },
            { text: '日志下载', link: '/workflows/log-download' },
            { text: '厂区 SIMS 同步', link: '/workflows/factory-sync' },
            { text: '看板快照预计算', link: '/workflows/analytics-snapshot' },
            { text: '知识库双写', link: '/workflows/knowledge-base' },
          ],
        },
      ],
      '/database/': [
        {
          text: '数据库',
          items: [
            { text: '集合参考', link: '/database/collections' },
            { text: '索引策略', link: '/database/indexes' },
          ],
        },
      ],
      '/deployment/': [
        {
          text: '部署',
          items: [
            { text: '本地运行', link: '/deployment/local' },
            { text: '生产部署', link: '/deployment/production' },
            { text: '环境变量', link: '/deployment/environment-vars' },
          ],
        },
      ],
      '/operations/': [
        {
          text: '运维',
          items: [
            { text: '故障排查', link: '/operations/troubleshooting' },
            { text: '日志与监控', link: '/operations/logging' },
          ],
        },
      ],
      '/api/': [
        {
          text: 'API 参考',
          items: [
            { text: 'API 概览', link: '/api/overview' },
            { text: 'OpenAPI / Swagger', link: '/api/openapi' },
          ],
        },
      ],
    },
    search: { provider: 'local' },
    footer: {
      message: 'WeaveEye Backend — FastAPI + Motor + MongoDB',
      copyright: '内部开发文档',
    },
    editLink: {
      pattern: 'https://github.com/hankerbiao/diag_dashboard/edit/main/diag_backend/docs/:path',
      text: '在 GitHub 上编辑此页',
    },
  },
})
