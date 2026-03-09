import { motion } from 'framer-motion';
import { useMemo, useState } from 'react';
import { pageMotion } from '../../motion/pageMotion';
import { BackPill } from '../../components/BackPill';
import { addEmergency, downloadJson, loadState } from '../../data/store';

export function FutureEmergencyPage() {
  const base = useMemo(() => loadState(), []);
  const [venue, setVenue] = useState(base.venue);
  const [type, setType] = useState<
    | 'missing_child'
    | 'missing_elder'
    | 'missing'
    | 'violence_risk'
    | 'medical'
    | 'fire'
    | 'disaster'
    | 'fraud'
    | 'other'
  >('other');
  const [reason, setReason] = useState<'witness' | 'self' | 'proxy' | 'online_lead'>('witness');
  const [risk, setRisk] = useState<'low' | 'medium' | 'high'>('medium');
  const [summary, setSummary] = useState('');
  const [details, setDetails] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const list = useMemo(() => {
    const s = loadState();
    return s.emergencies.filter((e) => e.venue === venue).sort((a, b) => b.createdAt - a.createdAt);
  }, [venue, refreshKey]);

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/future" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">emergency</div>
          <div className="sub">高风险信息走“受控上报”：按理由归类、默认不公开、可导出官方数据包（Demo JSON）。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18, display: 'grid', gap: 12 }}>
        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <div style={{ fontWeight: 760 }}>新建紧急事件</div>
          <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
            <span className="tag">venue</span>
            <input
              value={venue}
              onChange={(e) => setVenue(e.target.value)}
              style={{
                height: 32,
                borderRadius: 12,
                border: '1px solid rgba(234,223,206,.95)',
                padding: '0 10px',
                outline: 'none',
                background: 'rgba(255,255,255,.70)',
              }}
            />
          </div>
        </div>

        <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
          <span className="tag">type</span>
          <select
            value={type}
            onChange={(e) => setType(e.target.value as any)}
            style={{
              height: 36,
              borderRadius: 12,
              border: '1px solid rgba(234,223,206,.95)',
              padding: '0 10px',
              outline: 'none',
              background: 'rgba(255,255,255,.70)',
            }}
          >
            <option value="missing_child">missing_child</option>
            <option value="missing_elder">missing_elder</option>
            <option value="missing">missing</option>
            <option value="violence_risk">violence_risk</option>
            <option value="medical">medical</option>
            <option value="fire">fire</option>
            <option value="disaster">disaster</option>
            <option value="fraud">fraud</option>
            <option value="other">other</option>
          </select>

          <span className="tag">reason</span>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value as any)}
            style={{
              height: 36,
              borderRadius: 12,
              border: '1px solid rgba(234,223,206,.95)',
              padding: '0 10px',
              outline: 'none',
              background: 'rgba(255,255,255,.70)',
            }}
          >
            <option value="witness">witness</option>
            <option value="self">self</option>
            <option value="proxy">proxy</option>
            <option value="online_lead">online_lead</option>
          </select>

          <span className="tag">risk</span>
          <select
            value={risk}
            onChange={(e) => setRisk(e.target.value as any)}
            style={{
              height: 36,
              borderRadius: 12,
              border: '1px solid rgba(234,223,206,.95)',
              padding: '0 10px',
              outline: 'none',
              background: 'rgba(255,255,255,.70)',
            }}
          >
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </div>

        <input
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          placeholder="摘要（公开端只允许展示这一段脱敏摘要）"
          style={{
            height: 44,
            borderRadius: 14,
            border: '1px solid rgba(234,223,206,.95)',
            padding: '0 14px',
            outline: 'none',
            background: 'rgba(255,255,255,.70)',
          }}
        />
        <textarea
          value={details}
          onChange={(e) => setDetails(e.target.value)}
          placeholder="详细描述（默认不公开；用于官方/审核通道）"
          rows={5}
          style={{
            borderRadius: 14,
            border: '1px solid rgba(234,223,206,.95)',
            padding: '12px 14px',
            outline: 'none',
            resize: 'vertical',
            background: 'rgba(255,255,255,.70)',
          }}
        />

        <div className="row" style={{ justifyContent: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
          <button type="button" className="softBtn" onClick={() => setRefreshKey((k) => k + 1)}>
            刷新
          </button>
          <button
            type="button"
            className="softBtn softBtnPrimary"
            onClick={() => {
              if (!summary.trim()) return;
              addEmergency({ venue, type, reason, risk, summary: summary.trim(), details: details.trim() });
              setSummary('');
              setDetails('');
              setRisk('medium');
              setReason('witness');
              setType('other');
              setRefreshKey((k) => k + 1);
            }}
          >
            提交（私有）
          </button>
        </div>
      </section>

      <div style={{ height: 14 }} />

      <section className="card" style={{ padding: 18 }}>
        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <div style={{ fontWeight: 760 }}>记录（私有）</div>
          <button type="button" className="softBtn" onClick={() => setRefreshKey((k) => k + 1)}>
            刷新
          </button>
        </div>
        <div style={{ height: 10 }} />
        <div style={{ display: 'grid', gap: 10 }}>
          {list.length === 0 ? (
            <div className="muted">暂无记录。</div>
          ) : (
            list.map((e) => (
              <div key={e.id} className="listItem" style={{ cursor: 'default' }}>
                <div style={{ display: 'grid', gap: 6 }}>
                  <div style={{ fontWeight: 820, letterSpacing: '-0.01em' }}>
                    {e.summary}{' '}
                    <span className="tag" style={{ marginLeft: 8 }}>
                      {e.type}
                    </span>
                    <span className="tag" style={{ marginLeft: 8 }}>
                      {e.risk}
                    </span>
                  </div>
                  <div className="muted" style={{ fontSize: 13, lineHeight: 1.6 }}>
                    {e.details ? e.details.slice(0, 120) : '（无详情）'}
                    {e.details && e.details.length > 120 ? '…' : ''}
                  </div>
                </div>
                <button
                  type="button"
                  className="softBtn"
                  onClick={() => {
                    const pack = {
                      schemaVersion: '1.0',
                      generatedAt: new Date().toISOString(),
                      app: { name: 'Ahelpis Demo', build: 'web' },
                      case: {
                        caseId: e.id,
                        type: e.type,
                        reason: e.reason,
                        status: 'open',
                        timeWindow: { startAt: new Date(e.createdAt).toISOString(), endAt: new Date(e.createdAt + 60 * 60 * 1000).toISOString() },
                        location: { country: 'CN', venueId: e.venue, venueLabel: e.venue, geoPolicy: 'NO_GPS_STORED' },
                        summary: e.summary,
                        details: { structured: { riskLevel: e.risk }, freeText: e.details },
                      },
                      evidence: { items: [], onSiteVerification: { method: 'none', accuracyM: null, venueDistanceM: null } },
                      submitter: { accountability: 'traceable', userKeyHash: 'demo', realNameRecord: 'none' },
                      moderation: { publicExposure: 'private_by_default', redactionVersion: 'cn-1.0', flags: ['no_precise_location'] },
                    };
                    downloadJson(`${e.id}.case.json`, pack);
                  }}
                >
                  导出 JSON
                </button>
              </div>
            ))
          )}
        </div>
      </section>
    </motion.main>
  );
}

