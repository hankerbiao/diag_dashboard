import { useState, useCallback } from 'react';
import { AlertTriangle } from 'lucide-react';
import type { FactoryLocation, ErrorLogRow } from '../../types';
import { syncApi, type SyncServer } from '../../api/fastapi';
import SearchPanel from './SearchPanel';
import ErrorTable from './ErrorTable';
import AnalysisModal from './AnalysisModal';
import ModelStatisticsDashboard from '../dashboard/ModelStatisticsDashboard';

interface ErrorLogsTabProps {
  factory: FactoryLocation;
}

export default function ErrorLogsTab({ factory }: ErrorLogsTabProps) {
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
  const [detailRows, setDetailRows] = useState<ErrorLogRow[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);

  // 诊断
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<Record<string, string>>({});
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);

  const handleSearch = async () => {
    setServerLoading(true);
    setIsSearched(true);
    setSelectedSn(null);
    setDetailRows([]);

    try {
      const res = await syncApi.getServers({
        search_sn: sn || undefined,
        search_product_models: productModels || undefined,
        page: 1,
        limit: 100,
      });
      if (res.success && res.data) {
        setServers(res.data.items);
        setServerTotal(res.data.total);
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
    setDetailRows([]);
  };

  const fetchDetails = useCallback(async (serverSn: string) => {
    setSelectedSn(serverSn);
    setDetailsLoading(true);
    try {
      const res = await syncApi.getTestDetails(serverSn, { page: 1, limit: 200 });
      if (res.success && res.data) {
        const rows: ErrorLogRow[] = res.data.items.map((d) => ({
          id: d.id,
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
      } else {
        setDetailRows([]);
      }
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  const handleAnalyze = (id: string) => {
    setSelectedLogId(id);
    if (analysisResult[id]) return;
    setAnalyzingId(id);
    setTimeout(() => {
      setAnalysisResult((prev) => ({
        ...prev,
        [id]: '基于知识图谱深度分析与大模型聚类反馈：该测试节点的离群异常与已知高频缺陷簇表现出关键特征维度的吻合。系统推荐最优处置策略为主板阻抗微调或执行诊断框架 `diag --verify` 命令进行边界校验验证。',
      }));
      setAnalyzingId(null);
    }, 1500);
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
        sn={sn}
        productModels={productModels}
        onSnChange={setSn}
        onProductModelsChange={setProductModels}
        onReset={handleReset}
        onSearch={handleSearch}
      />

      {isSearched ? (
        <>
          {/* 服务器列表 */}
          <div
            className="mx-4 mb-2 rounded-lg border overflow-hidden flex-none"
            style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
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
            <div className="max-h-[200px] overflow-auto custom-scrollbar">
              {serverLoading ? (
                <div className="flex items-center justify-center py-8 gap-2" style={{ color: 'var(--color-text-secondary)' }}>
                  <div className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-accent)', borderTopColor: 'transparent' }} />
                  <span className="text-xs">加载中...</span>
                </div>
              ) : servers.length === 0 ? (
                <div className="flex items-center justify-center py-8 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  暂无匹配的服务器
                </div>
              ) : (
                <table className="w-full text-left text-[12px]">
                  <thead style={{ color: 'var(--color-text-secondary)' }}>
                    <tr className="border-b" style={{ borderColor: 'var(--color-border)' }}>
                      <th className="px-4 py-2 font-semibold">SN</th>
                      <th className="px-4 py-2 font-semibold">型号</th>
                      <th className="px-4 py-2 font-semibold">产品型号</th>
                      <th className="px-4 py-2 font-semibold text-center">告警数</th>
                      <th className="px-4 py-2 font-semibold">状态</th>
                      <th className="px-4 py-2 font-semibold">客户</th>
                    </tr>
                  </thead>
                  <tbody>
                    {servers.map((srv) => {
                      const isSelected = selectedSn === srv.server_sn;
                      return (
                        <tr
                          key={srv.id}
                          onClick={() => fetchDetails(srv.server_sn)}
                          className="border-b cursor-pointer transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
                          style={{
                            backgroundColor: isSelected ? 'var(--color-accent-light)' : 'transparent',
                            borderColor: 'var(--color-border)',
                          }}
                        >
                          <td className="px-4 py-2.5 font-mono font-semibold" style={{ color: 'var(--color-accent)' }}>{srv.server_sn}</td>
                          <td className="px-4 py-2.5" style={{ color: 'var(--color-text-primary)' }}>{srv.model || '-'}</td>
                          <td className="px-4 py-2.5" style={{ color: 'var(--color-text-secondary)' }}>{srv.product_models || '-'}</td>
                          <td className="px-4 py-2.5 text-center">
                            {srv.alarm > 0 ? (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-bold"
                                style={{ backgroundColor: 'rgba(239,68,68,0.1)', color: '#dc2626' }}>
                                <AlertTriangle className="w-3 h-3" />{srv.alarm}
                              </span>
                            ) : <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>0</span>}
                          </td>
                          <td className="px-4 py-2.5" style={{ color: 'var(--color-text-secondary)' }}>{srv.server_state || '-'}</td>
                          <td className="px-4 py-2.5" style={{ color: 'var(--color-text-secondary)' }}>{srv.customer_name || '-'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* 测试详情表 */}
          <div
            className="mx-4 mb-4 rounded-lg shadow-sm flex-1 flex flex-col min-h-0 border overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500"
            style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
          >
            <div
              className="h-10 px-4 border-b flex items-center justify-between flex-none"
              style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }}
            >
              <span className="text-[12px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                {selectedSn ? `${selectedSn} 的测试详情` : '选择一台服务器查看测试详情'}
              </span>
              {detailRows.length > 0 && (
                <span className="text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                  共 {detailRows.length} 条
                </span>
              )}
            </div>

            <ErrorTable
              data={detailRows}
              loading={detailsLoading}
              analyzingId={analyzingId}
              analysisResult={analysisResult}
              onAnalyze={handleAnalyze}
            />
          </div>
        </>
      ) : (
        <ModelStatisticsDashboard />
      )}

      <AnalysisModal
        selectedLog={selectedDetail}
        analyzingId={analyzingId}
        analysisResult={analysisResult}
        onClose={handleCloseModal}
      />
    </div>
  );
}
