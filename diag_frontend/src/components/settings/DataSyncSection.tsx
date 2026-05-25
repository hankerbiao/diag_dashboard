import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, CheckCircle2, XCircle, Loader2, Search, ChevronDown, ChevronUp } from 'lucide-react';
import { syncApi, SyncJob, SyncServer, SyncTestDetail } from '../../api/fastapi';

interface DataSyncSectionProps {
  className?: string;
}

type SyncStatus = 'idle' | 'syncing' | 'success' | 'failed';

export default function DataSyncSection({ className = '' }: DataSyncSectionProps) {
  const [syncStatus, setSyncStatus] = useState<SyncStatus>('idle');
  const [latestJob, setLatestJob] = useState<SyncJob | null>(null);
  const [syncJobs, setSyncJobs] = useState<SyncJob[]>([]);
  const [errorMessage, setErrorMessage] = useState<string>('');

  // 服务器查询
  const [searchSN, setSearchSN] = useState('');
  const [servers, setServers] = useState<SyncServer[]>([]);
  const [serversTotal, setServersTotal] = useState(0);
  const [serversPage, setServersPage] = useState(1);
  const [serversLoading, setServersLoading] = useState(false);

  // 展开的服务器
  const [expandedSN, setExpandedSN] = useState<string | null>(null);
  const [testDetails, setTestDetails] = useState<SyncTestDetail[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);

  const limit = 20;

  // 获取最新同步状态
  const fetchStatus = useCallback(async () => {
    const resp = await syncApi.getSyncStatus();
    if (resp.success && resp.data) {
      setLatestJob(resp.data);
      if (resp.data.status === 'running') {
        setSyncStatus('syncing');
      } else if (resp.data.status === 'success') {
        setSyncStatus('success');
      } else {
        setSyncStatus('failed');
        setErrorMessage(resp.data.error_message || '');
      }
    }
  }, []);

  // 获取同步历史
  const fetchJobs = useCallback(async () => {
    const resp = await syncApi.getSyncJobs({ limit: 5 });
    if (resp.success && resp.data) {
      setSyncJobs(resp.data.items);
    }
  }, []);

  // 获取服务器列表
  const fetchServers = useCallback(async (sn: string, page: number) => {
    setServersLoading(true);
    try {
      const resp = await syncApi.getServers({
        search_sn: sn || undefined,
        page,
        limit,
      });
      if (resp.success && resp.data) {
        setServers(resp.data.items);
        setServersTotal(resp.data.total);
      }
    } finally {
      setServersLoading(false);
    }
  }, []);

  // 获取测试详情
  const fetchTestDetails = useCallback(async (serverSn: string) => {
    setDetailsLoading(true);
    try {
      const resp = await syncApi.getTestDetails(serverSn, { limit: 50 });
      if (resp.success && resp.data) {
        setTestDetails(resp.data.items);
      }
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  // 初始加载
  useEffect(() => {
    fetchStatus();
    fetchJobs();
    fetchServers('', 1);
  }, [fetchStatus, fetchJobs, fetchServers]);

  // 轮询同步状态
  useEffect(() => {
    if (syncStatus !== 'syncing') return;

    const interval = setInterval(async () => {
      await fetchStatus();
    }, 5000);

    return () => clearInterval(interval);
  }, [syncStatus, fetchStatus]);

  // 触发同步
  const handleTriggerSync = async () => {
    setSyncStatus('syncing');
    setErrorMessage('');

    const resp = await syncApi.triggerSync();
    if (resp.success) {
      // 开始轮询状态
      const poll = setInterval(async () => {
        const statusResp = await syncApi.getSyncStatus();
        if (statusResp.success && statusResp.data) {
          if (statusResp.data.status === 'running') {
            setLatestJob(statusResp.data);
          } else {
            clearInterval(poll);
            setLatestJob(statusResp.data);
            setSyncStatus(statusResp.data.status === 'success' ? 'success' : 'failed');
            if (statusResp.data.status === 'failed') {
              setErrorMessage(statusResp.data.error_message || '同步失败');
            }
            fetchJobs();
            fetchServers('', 1);
          }
        }
      }, 2000);

      setTimeout(() => clearInterval(poll), 300000); // 5分钟超时
    } else {
      setSyncStatus('failed');
      setErrorMessage(resp.error || '启动同步失败');
    }
  };

  // 搜索服务器
  const handleSearch = () => {
    setServersPage(1);
    fetchServers(searchSN, 1);
  };

  // 服务器分页
  const handleServersPageChange = (newPage: number) => {
    setServersPage(newPage);
    fetchServers(searchSN, newPage);
  };

  // 展开/收起服务器详情
  const handleToggleExpand = (sn: string) => {
    if (expandedSN === sn) {
      setExpandedSN(null);
      setTestDetails([]);
    } else {
      setExpandedSN(sn);
      fetchTestDetails(sn);
    }
  };

  // 格式化时间
  const formatTime = (timeStr: string) => {
    if (!timeStr) return '-';
    const date = new Date(timeStr);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // 状态图标
  const StatusIcon = ({ status }: { status: string }) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'running':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      default:
        return null;
    }
  };

  return (
    <div className={className}>
      <h3
        className="text-sm font-bold mb-4 flex items-center gap-2"
        style={{ color: 'var(--color-text-primary)' }}
      >
        <RefreshCw className="w-4 h-4" />
        第三方数据同步管理
      </h3>

      {/* 同步控制区 */}
      <div
        className="p-4 rounded-lg mb-4"
        style={{ backgroundColor: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <button
              onClick={handleTriggerSync}
              disabled={syncStatus === 'syncing'}
              className="px-4 py-2 text-white text-[13px] font-bold rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
              style={{
                backgroundColor: syncStatus === 'syncing' ? 'var(--color-text-muted)' : 'var(--color-accent)',
              }}
            >
              {syncStatus === 'syncing' ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> 同步中...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4" /> 触发同步
                </>
              )}
            </button>

            {syncStatus !== 'idle' && latestJob && (
              <div className="flex items-center gap-2 text-[13px]">
                <StatusIcon status={syncStatus} />
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {syncStatus === 'syncing' && '同步中...'}
                  {syncStatus === 'success' && (
                    <>同步成功: {latestJob.servers_total} 台服务器, {latestJob.details_total} 条详情</>
                  )}
                  {syncStatus === 'failed' && '同步失败'}
                </span>
              </div>
            )}
          </div>

          {latestJob && (
            <div className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              上次同步: {formatTime(latestJob.started_at)}
            </div>
          )}
        </div>

        {syncStatus === 'failed' && errorMessage && (
          <div
            className="p-3 rounded text-[13px]"
            style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}
          >
            <strong>错误:</strong> {errorMessage}
          </div>
        )}

        {/* 同步历史 */}
        {syncJobs.length > 0 && (
          <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--color-border)' }}>
            <div className="text-[12px] font-semibold mb-2" style={{ color: 'var(--color-text-secondary)' }}>
              最近同步记录
            </div>
            <div className="space-y-2">
              {syncJobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between text-[12px] py-1.5 px-2 rounded"
                  style={{ backgroundColor: 'var(--color-bg-primary)' }}
                >
                  <div className="flex items-center gap-2">
                    <StatusIcon status={job.status} />
                    <span style={{ color: 'var(--color-text-primary)' }}>
                      {formatTime(job.started_at)}
                    </span>
                  </div>
                  <div style={{ color: 'var(--color-text-muted)' }}>
                    {job.servers_total} 台 / {job.details_total} 条
                    {job.error_message && (
                      <span className="ml-2 text-red-500">({job.error_message.slice(0, 30)}...)</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 服务器查询 */}
      <div
        className="p-4 rounded-lg"
        style={{ backgroundColor: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
      >
        <div className="text-[13px] font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
          服务器列表查询
        </div>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="按 SN 模糊搜索..."
            value={searchSN}
            onChange={(e) => setSearchSN(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="flex-1 px-3 py-2 text-[13px] rounded outline-none border"
            style={{
              backgroundColor: 'var(--color-bg-primary)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-primary)',
            }}
          />
          <button
            onClick={handleSearch}
            disabled={serversLoading}
            className="px-4 py-2 text-white text-[13px] font-bold rounded-lg flex items-center gap-2 disabled:opacity-50"
            style={{ backgroundColor: 'var(--color-accent)' }}
          >
            <Search className="w-4 h-4" /> 查询
          </button>
        </div>

        {serversLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--color-accent)' }} />
          </div>
        ) : (
          <>
            <div className="text-[12px] mb-2" style={{ color: 'var(--color-text-muted)' }}>
              共 {serversTotal} 条记录
            </div>

            <div className="space-y-2 max-h-80 overflow-y-auto custom-scrollbar">
              {servers.map((server) => (
                <div key={server.id}>
                  <div
                    className="flex items-center justify-between p-3 rounded cursor-pointer transition-colors"
                    style={{
                      backgroundColor: expandedSN === server.server_sn ? 'var(--color-bg-primary)' : 'transparent',
                      border: '1px solid var(--color-border)',
                    }}
                    onClick={() => handleToggleExpand(server.server_sn)}
                  >
                    <div className="flex-1 grid grid-cols-5 gap-4 text-[12px]">
                      <div style={{ color: 'var(--color-text-primary)' }} className="font-mono">
                        {server.server_sn}
                      </div>
                      <div style={{ color: 'var(--color-text-secondary)' }}>{server.model}</div>
                      <div style={{ color: 'var(--color-text-secondary)' }}>{server.product_models}</div>
                      <div style={{ color: 'var(--color-text-muted)' }}>{server.host_ip}</div>
                      <div>
                        <span
                          className="px-2 py-0.5 rounded text-[11px] font-bold"
                          style={{
                            backgroundColor: server.server_state === '2' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(234, 179, 8, 0.2)',
                            color: server.server_state === '2' ? '#22c55e' : '#eab308',
                          }}
                        >
                          {server.server_state === '2' ? '测试中' : server.server_state}
                        </span>
                      </div>
                    </div>
                    {expandedSN === server.server_sn ? (
                      <ChevronUp className="w-4 h-4 ml-2" style={{ color: 'var(--color-text-muted)' }} />
                    ) : (
                      <ChevronDown className="w-4 h-4 ml-2" style={{ color: 'var(--color-text-muted)' }} />
                    )}
                  </div>

                  {/* 测试详情展开面板 */}
                  {expandedSN === server.server_sn && (
                    <div
                      className="mt-1 p-3 rounded-b"
                      style={{ backgroundColor: 'var(--color-bg-primary)', border: '1px solid var(--color-border)', borderTop: 'none' }}
                    >
                      <div className="text-[11px] font-semibold mb-2" style={{ color: 'var(--color-text-secondary)' }}>
                        测试详情
                      </div>
                      {detailsLoading ? (
                        <div className="flex items-center justify-center py-4">
                          <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--color-accent)' }} />
                        </div>
                      ) : testDetails.length === 0 ? (
                        <div className="text-[12px] py-2" style={{ color: 'var(--color-text-muted)' }}>
                          暂无测试记录
                        </div>
                      ) : (
                        <div className="space-y-1.5 max-h-48 overflow-y-auto">
                          {testDetails.map((detail) => (
                            <div
                              key={detail.id}
                              className="flex items-center gap-3 text-[11px] py-1.5 px-2 rounded"
                              style={{ backgroundColor: 'var(--color-bg-secondary)' }}
                            >
                              <span style={{ color: 'var(--color-text-muted)' }}>{formatTime(detail.test_time)}</span>
                              <span
                                className="font-medium"
                                style={{
                                  color: detail.server_test_result === '成功' ? '#22c55e' : '#ef4444'
                                }}
                              >
                                {detail.server_test_result}
                              </span>
                              <span style={{ color: 'var(--color-text-secondary)' }}>{detail.detailed_flow}</span>
                              {detail.fault_type1 && (
                                <span className="text-red-500 ml-auto">故障: {detail.fault_type1}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {servers.length === 0 && (
                <div className="text-center py-8 text-[13px]" style={{ color: 'var(--color-text-muted)' }}>
                  暂无数据
                </div>
              )}
            </div>

            {/* 分页 */}
            {serversTotal > limit && (
              <div className="flex items-center justify-center gap-2 mt-4">
                <button
                  onClick={() => handleServersPageChange(serversPage - 1)}
                  disabled={serversPage <= 1}
                  className="px-3 py-1 text-[12px] rounded disabled:opacity-50"
                  style={{ backgroundColor: 'var(--color-bg-primary)', border: '1px solid var(--color-border)' }}
                >
                  上一页
                </button>
                <span className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                  第 {serversPage} / {Math.ceil(serversTotal / limit)} 页
                </span>
                <button
                  onClick={() => handleServersPageChange(serversPage + 1)}
                  disabled={serversPage >= Math.ceil(serversTotal / limit)}
                  className="px-3 py-1 text-[12px] rounded disabled:opacity-50"
                  style={{ backgroundColor: 'var(--color-bg-primary)', border: '1px solid var(--color-border)' }}
                >
                  下一页
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}