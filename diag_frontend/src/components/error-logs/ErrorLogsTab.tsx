import { useState, useCallback, useMemo, useEffect } from 'react';
import { ArrowUpDown } from 'lucide-react';
import type { ErrorLogRow } from '../../types';
import { syncApi, analyticsApi, diagnosisApi, type SyncServer, type DashboardInsights, type FactorySite, type DiagnosisCache } from '../../api/fastapi';
import { mapServerState } from '../../utils/serverState';
import { useDebounce } from '../../hooks/useDebounce';
import SearchPanel from './SearchPanel';
import AnalysisModal from './AnalysisModal';
import ServerDetailModal from './ServerDetailModal';
import BatchTestCharts from './charts/BatchTestCharts';
import SupportHint from '../common/SupportHint';
import { buildYieldTrendFromDaily } from './utils/buildYieldTrend';
import type { DailyStatItem } from '../../api/analytics';

interface ErrorLogsTabProps {
  factory: string;
  factorySites: FactorySite[];
}

function buildAnalyzeContext(row: ErrorLogRow, factoryId: string, fallbackSn?: string) {
  const faults = (row.faultTypes || '').split(',').map((s) => s.trim()).filter(Boolean);
  const logPath = (row.logPath || '').trim();
  return {
    factory_id: factoryId,
    server_sn: row.sn || fallbackSn || '',
    test_time: row.testTime || '',
    test_item: row.testItem === '-' ? '' : row.testItem,
    fail_details: row.status === '-' ? '' : row.status,
    log_path: logPath && logPath !== '-' ? logPath : '',
    fault_type1: faults[0] || '',
    fault_type2: faults[1] || '',
    fault_type3: faults[2] || '',
  };
}

export default function ErrorLogsTab({ factory, factorySites }: ErrorLogsTabProps) {
  // 搜索
  const [sn, setSn] = useState('');
  const [productModels, setProductModels] = useState('');
  const [isSearched, setIsSearched] = useState(false);

  // 服务器列表
  const [servers, setServers] = useState<SyncServer[]>([]);
  const [serverTotal, setServerTotal] = useState(0);
  const [serverLoading, setServerLoading] = useState(false);

  // 选中的 SN 及详情
  const [selectedSn, setSelectedSn] = useState<string | null>(null);
  const [selectedServer, setSelectedServer] = useState<SyncServer | null>(null);
  const [detailRows, setDetailRows] = useState<ErrorLogRow[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState('');
  const [showDetailModal, setShowDetailModal] = useState(false);

  const currentFactory = factorySites.find(f => f.factory_id === factory);
  const logBaseUrl = currentFactory?.log_base_url ?? '';

  // 排序
  const [sortField, setSortField] = useState<'status' | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  // 分析看板
  const [insights, setInsights] = useState<DashboardInsights | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [dailyStats, setDailyStats] = useState<DailyStatItem[]>([]);
  const [trend, setTrend] = useState<'day' | 'week' | 'month'>('day');

  const loadInsights = useCallback(async () => {
    setInsightsLoading(true);
    try {
      const [summaryRes, dailyRes] = await Promise.all([
        analyticsApi.getSummary({ factory_id: factory, days: 30 }),
        analyticsApi.getDailyStats({ factory_id: factory, days: 30 }),
      ]);

      if (summaryRes.success && summaryRes.data) {
        const summary = summaryRes.data;
        const daily = dailyRes.success ? dailyRes.data?.items ?? [] : [];
        setDailyStats(daily);

        setInsights({
          fault_categories: summary.fault_categories,
          fault_subcategories: summary.fault_subcategories,
          station_failures: summary.station_failures,
          decision_distribution: summary.decision_distribution,
          model_defects: summary.model_defects,
          yield_trend: buildYieldTrendFromDaily(daily, trend),
        });
      }
    } finally {
      setInsightsLoading(false);
    }
  }, [factory]);

  useEffect(() => {
    void loadInsights();
  }, [loadInsights]);

  // 切换日/周/月：用已缓存的每日数据重算良率，不重复请求接口
  useEffect(() => {
    if (dailyStats.length === 0) return;
    setInsights((prev) =>
      prev ? { ...prev, yield_trend: buildYieldTrendFromDaily(dailyStats, trend) } : prev,
    );
  }, [trend, dailyStats]);

  const handleTrendChange = (g: 'day' | 'week' | 'month') => {
    setTrend(g);
  };

  // 诊断
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<Record<string, DiagnosisCache>>({});
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [analyzingProgress, setAnalyzingProgress] = useState<{ stage: string; detail: string } | null>(null);
  const [streamingText, setStreamingText] = useState('');

  const sortedServers = useMemo(() => {
    if (!sortField) return servers;
    return [...servers].sort((a, b) => {
      const aVal = mapServerState(a.server_state).label;
      const bVal = mapServerState(b.server_state).label;
      return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    });
  }, [servers, sortField, sortDir]);

  const toggleSort = (field: 'status') => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const debouncedSn = useDebounce(sn, 400);
  const debouncedProductModels = useDebounce(productModels, 400);

  // 防抖搜索
  useEffect(() => {
    if (!debouncedSn.trim() && !debouncedProductModels.trim()) {
      if (isSearched) {
        handleReset();
      }
      return;
    }
    handleSearch();
  }, [debouncedSn, debouncedProductModels]);

  const handleSearch = async () => {
    setServerLoading(true);
    setIsSearched(true);
    setSelectedSn(null);
    setDetailRows([]);

    try {
      const serverRes = await syncApi.getServers({
        factory_id: factory || undefined,
        search_sn: sn || undefined,
        search_product_models: productModels || undefined,
        page: 1,
        limit: 100,
      });
      if (serverRes.success && serverRes.data) {
        setServers(serverRes.data.items);
        setServerTotal(serverRes.data.total);
      }
    } finally {
      setServerLoading(false);
    }
  };

  const handleReset = () => {
    setSn('');
    setProductModels('');
    setIsSearched(false);
    setServers([]);
    setServerTotal(0);
    setSelectedSn(null);
    setSelectedServer(null);
    setDetailRows([]);
    setDetailsError('');
    setShowDetailModal(false);
    loadInsights();
  };

  const fetchDetails = useCallback(async (server: SyncServer) => {
    if (!factory) {
      setDetailsError('请先在右上角选择厂区');
      return;
    }
    setSelectedSn(server.server_sn);
    setSelectedServer(server);
    setShowDetailModal(true);
    setDetailsLoading(true);
    setDetailsError('');
    setDetailRows([]);
    try {
      const res = await syncApi.getTestDetails(server.server_sn, {
        factory_id: factory,
        page: 1,
        limit: 500,
      });
      if (res.success && res.data) {
        const rows: ErrorLogRow[] = res.data.items.map((d, idx) => ({
          id: d.id || `${factory}_${d.server_sn}_${d.test_time}_${idx}`,
          sn: d.server_sn,
          testItem: d.detailed_flow || d.big_flow || '-',
          testTime: d.test_time,
          status: d.server_test_result || '-',
          decision: d.decision || '-',
          faultTypes: [d.fault_type1, d.fault_type2, d.fault_type3].filter(Boolean).join(', '),
          logPath: d.log_path || '-',
          mesRecord: d.mes_record || '',
        }));
        setDetailRows(rows);
        if (rows.length === 0) {
          setDetailsError('SIMS 未返回该服务器的测试记录');
        }
      } else {
        setDetailRows([]);
        setDetailsError(res.error || '加载测试详情失败');
      }
    } catch {
      setDetailRows([]);
      setDetailsError('网络请求失败，请稍后重试');
    } finally {
      setDetailsLoading(false);
    }
  }, [factory]);

  const handleAnalyze = async (id: string) => {
    setSelectedLogId(id);
    if (analysisResult[id]) return;
    const row = detailRows.find((r) => r.id === id);
    if (!row) return;
    setAnalyzingId(id);
    setStreamingText('');

    const params = logBaseUrl ? `?log_base_url=${encodeURIComponent(logBaseUrl)}` : '';
    const encodedId = encodeURIComponent(id);
    await diagnosisApi.analyzeSSE(
      `/api/diagnosis/error-log/${encodedId}/analyze${params}`,
      (_stage, detail) => setAnalyzingProgress({ stage: _stage, detail }),
      (data) => {
        setAnalysisResult((prev) => ({ ...prev, [id]: data }));
        setAnalyzingId(null);
        setAnalyzingProgress(null);
        setStreamingText('');
      },
      (_message) => {
        setAnalyzingId(null);
        setAnalyzingProgress(null);
        setStreamingText('');
      },
      (text) => setStreamingText((prev) => prev + text),
      buildAnalyzeContext(row, factory, selectedServer?.server_sn),
    );
  };

  const handleReAnalyze = async (id: string) => {
    const row = detailRows.find((r) => r.id === id);
    if (!row) return;
    setAnalyzingId(id);
    setAnalyzingProgress(null);
    setStreamingText('');

    const params = logBaseUrl ? `?log_base_url=${encodeURIComponent(logBaseUrl)}` : '';
    const encodedId = encodeURIComponent(id);
    await diagnosisApi.analyzeSSE(
      `/api/diagnosis/error-log/${encodedId}/re-analyze${params}`,
      (_stage, detail) => setAnalyzingProgress({ stage: _stage, detail }),
      (data) => {
        setAnalysisResult((prev) => ({ ...prev, [id]: data }));
        setAnalyzingId(null);
        setAnalyzingProgress(null);
        setStreamingText('');
      },
      (_message) => {
        setAnalyzingId(null);
        setAnalyzingProgress(null);
        setStreamingText('');
      },
      (text) => setStreamingText((prev) => prev + text),
      buildAnalyzeContext(row, factory, selectedServer?.server_sn),
    );
  };

  const handleCloseModal = () => {
    setSelectedLogId(null);
  };

  const selectedDetail = detailRows.find((r) => r.id === selectedLogId) ?? null;

  return (
    <div
      className="flex-1 flex flex-col h-full overflow-hidden relative"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      <SearchPanel
        factory={factory}
        factorySites={factorySites}
        sn={sn}
        productModels={productModels}
        onSnChange={setSn}
        onProductModelsChange={setProductModels}
        onSearch={handleSearch}
        onReset={handleReset}
      />

      <div className="flex-1 flex flex-col min-h-0 overflow-y-auto custom-scrollbar">
        {/* 默认视图：分析看板图表 */}
        {!isSearched && (
          <BatchTestCharts data={insights} loading={insightsLoading} trend={trend} onTrendChange={handleTrendChange} />
        )}

        {/* 搜索后显示服务器列表 */}
        {isSearched && (
          <div
            className="mx-4 mb-4 rounded-lg border flex-none overflow-hidden flex flex-col"
            style={{ maxHeight: '500px', backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
          >
            <div
              className="h-10 px-4 border-b flex items-center justify-between flex-none text-[12px]"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
            >
              <span>
                匹配 <span className="font-bold" style={{ color: 'var(--color-accent)' }}>{serverTotal}</span> 台服务器
              </span>
              {selectedSn && (
                <span className="font-mono" style={{ color: 'var(--color-accent)' }}>
                  当前: {selectedSn}
                </span>
              )}
            </div>
            <div className="flex-1 min-h-0 overflow-auto custom-scrollbar">
              {serverLoading ? (
                <div className="flex items-center justify-center py-8 gap-2" style={{ color: 'var(--color-text-secondary)' }}>
                  <div className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-accent)', borderTopColor: 'transparent' }} />
                  <span className="text-xs">加载中...</span>
                </div>
              ) : servers.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-xs gap-2" style={{ color: 'var(--color-text-secondary)' }}>
                  <span>暂无匹配的服务器</span>
                  <span style={{ color: 'var(--color-text-muted)' }}>
                    {factory
                      ? `当前基地：${currentFactory?.name ?? factory}，请确认 SN 是否正确`
                      : '请在右上角选择目标基地后重试'}
                  </span>
                  <SupportHint compact className="justify-center mt-1" />
                </div>
              ) : (
                <table className="w-full text-left text-[12px]">
                  <thead style={{ color: 'var(--color-text-secondary)' }}>
                    <tr className="border-b" style={{ borderColor: 'var(--color-border)' }}>
                      <th className="px-4 py-2 font-semibold">SN</th>
                      <th className="px-4 py-2 font-semibold">型号</th>
                      <th className="px-4 py-2 font-semibold">产品型号</th>
                      <th className="px-4 py-2 font-semibold cursor-pointer select-none" onClick={() => toggleSort('status')}>
                        <span className="inline-flex items-center gap-1">
                          状态
                          <ArrowUpDown className="w-3 h-3 opacity-50" />
                        </span>
                      </th>
                      <th className="px-4 py-2 font-semibold">下一步骤</th>
                      <th className="px-4 py-2 font-semibold">坐标位置</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedServers.map((srv) => {
                      const isSelected = selectedSn === srv.server_sn;
                      const stateInfo = mapServerState(srv.server_state);
                      return (
                        <tr
                          key={srv.id}
                          onClick={() => fetchDetails(srv)}
                          className="border-b cursor-pointer transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
                          style={{
                            backgroundColor: isSelected ? 'var(--color-accent-light)' : 'transparent',
                            borderColor: 'var(--color-border)',
                          }}
                        >
                          <td className="px-4 py-2.5 font-mono font-semibold" style={{ color: 'var(--color-accent)' }}>{srv.server_sn}</td>
                          <td className="px-4 py-2.5" style={{ color: 'var(--color-text-primary)' }}>{srv.model || '-'}</td>
                          <td className="px-4 py-2.5" style={{ color: 'var(--color-text-secondary)' }}>{srv.product_models || '-'}</td>
                          <td className="px-4 py-2.5">
                            <span
                              className="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold"
                              style={{ backgroundColor: stateInfo.bg, color: stateInfo.color }}
                            >
                              {stateInfo.label}
                            </span>
                          </td>
                          <td className="px-4 py-2.5" style={{ color: 'var(--color-text-primary)' }}>{srv.next_item || '-'}</td>
                          <td className="px-4 py-2.5 font-mono text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>{srv.position || '-'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>

      {showDetailModal && selectedServer && (
        <ServerDetailModal
          server={selectedServer}
          detailRows={detailRows}
          detailsLoading={detailsLoading}
          detailsError={detailsError}
          analyzingId={analyzingId}
          analysisResult={analysisResult}
          onAnalyze={handleAnalyze}
          onClose={() => setShowDetailModal(false)}
          factory={factory}
          logBaseUrl={logBaseUrl}
        />
      )}

      <AnalysisModal
        selectedLog={selectedDetail}
        analyzingId={analyzingId}
        analysisResult={analysisResult}
        analyzingProgress={analyzingProgress}
        streamingText={streamingText}
        onClose={handleCloseModal}
        onReAnalyze={handleReAnalyze}
      />
    </div>
  );
}
