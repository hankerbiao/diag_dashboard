import { defineConfig } from 'vitepress'

export default defineConfig({
  title: "WeaveEye",
  description: "基于 AI 的智能设备诊断与异常分析系统",
  lang: 'zh-CN',

  themeConfig: {
    logo: '/logo.svg',

    nav: [
      { text: '首页', link: '/' },
      { text: '快速入门', link: '/guide/getting-started' },
      { text: '架构', link: '/architecture/overview' },
      { text: '工作流', link: '/workflows/ai-diagnosis' },
      { text: 'API', link: '/api/overview' },
    ],

    sidebar: {
      '/guide/': [
        {
          text: '指南',
          items: [
            { text: '快速入门', link: '/guide/getting-started' },
            { text: '项目结构', link: '/guide/project-structure' },
            { text: '配置参考', link: '/guide/configuration' },
          ],
        },
      ],
      '/architecture/': [
        {
          text: '架构',
          items: [
            { text: '系统架构', link: '/architecture/overview' },
            { text: '数据流', link: '/architecture/data-flow' },
          ],
        },
      ],
      '/workflows/': [
        {
          text: '业务工作流',
          items: [
            { text: '认证流程', link: '/workflows/authentication' },
            { text: '厂区数据同步', link: '/workflows/factory-data-sync' },
            { text: 'AI 诊断分析', link: '/workflows/ai-diagnosis' },
            { text: '知识库管理', link: '/workflows/knowledge-base' },
            { text: '数据看板', link: '/workflows/analytics-dashboard' },
            { text: '厂区配置管理', link: '/workflows/factory-configuration' },
          ],
        },
      ],
      '/api/': [
        {
          text: 'API 参考',
          items: [
            { text: 'API 概览', link: '/api/overview' },
            { text: '认证 API', link: '/api/auth' },
            { text: '诊断 API', link: '/api/diagnosis' },
            { text: '错误日志 API', link: '/api/error-logs' },
            { text: '数据分析 API', link: '/api/analytics' },
            { text: '数据同步 API', link: '/api/sync' },
            { text: '知识库 API', link: '/api/knowledge-base' },
            { text: '厂区管理 API', link: '/api/factories' },
            { text: '设置 API', link: '/api/settings' },
          ],
        },
      ],
      '/database/': [
        {
          text: '数据库',
          items: [
            { text: 'MongoDB 集合参考', link: '/database/mongodb-schema' },
          ],
        },
      ],
      '/deployment/': [
        {
          text: '部署',
          items: [
            { text: '后端部署', link: '/deployment/backend-deploy' },
            { text: '前端部署', link: '/deployment/frontend-deploy' },
            { text: '环境变量', link: '/deployment/environment-vars' },
          ],
        },
      ],
      '/operations/': [
        {
          text: '运维',
          items: [
            { text: '开发环境', link: '/operations/development' },
            { text: '数据同步脚本', link: '/operations/data-sync-scripts' },
          ],
        },
      ],
    },

    search: {
      provider: 'local',
    },

    footer: {
      message: 'WeaveEye - 基于 AI 的智能设备诊断与异常分析系统',
      copyright: 'MIT License',
    },
  },
})
