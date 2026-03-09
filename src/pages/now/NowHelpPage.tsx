import { motion } from 'framer-motion';
import { useMemo, useState } from 'react';
import { pageMotion } from '../../motion/pageMotion';
import { BackPill } from '../../components/BackPill';
import { addHelp, closeHelp, loadState } from '../../data/store';

function fmt(ts: number) {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function NowHelpPage() {
  const base = useMemo(() => loadState(), []);
  const [venue, setVenue] = useState(base.venue);
  const [title, setTitle] = useState('');
  const [detail, setDetail] = useState('');
  const [urgency, setUrgency] = useState<'low' | 'med' | 'high'>('med');
  const [refreshKey, setRefreshKey] = useState(0);

  const list = useMemo(() => {
    const s = loadState();
    const now = Date.now();
    return s.help
      .filter((h) => h.venue === venue)
      .filter((h) => h.expiresAt > now)
      .sort((a, b) => b.createdAt - a.createdAt);
  }, [venue, refreshKey]);

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/now" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">help</div>
          <div className="sub">实时获得帮助：Now 流（自动过期，Demo 用本地存储模拟）。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18, display: 'grid', gap: 12 }}>
        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <div style={{ fontWeight: 760 }}>发布求助</div>
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

        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="一句话标题（越短越清晰）"
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
          value={detail}
          onChange={(e) => setDetail(e.target.value)}
          placeholder="细节（可选）：你需要什么、时间窗、怎么联系"
          rows={4}
          style={{
            borderRadius: 14,
            border: '1px solid rgba(234,223,206,.95)',
            padding: '12px 14px',
            outline: 'none',
            resize: 'vertical',
            background: 'rgba(255,255,255,.70)',
          }}
        />

        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
            <span className="tag">urgency</span>
            <select
              value={urgency}
              onChange={(e) => setUrgency(e.target.value as any)}
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
              <option value="med">med</option>
              <option value="high">high</option>
            </select>
          </div>
          <button
            type="button"
            className="softBtn softBtnPrimary"
            onClick={() => {
              if (!title.trim()) return;
              addHelp({
                venue,
                title: title.trim(),
                detail: detail.trim(),
                urgency,
                expiresAt: Date.now() + 30 * 60 * 1000,
              });
              setTitle('');
              setDetail('');
              setUrgency('med');
              setRefreshKey((k) => k + 1);
            }}
          >
            发布
          </button>
        </div>
      </section>

      <div style={{ height: 14 }} />

      <section className="card" style={{ padding: 18 }}>
        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <div style={{ fontWeight: 760 }}>Now 流</div>
          <button type="button" className="softBtn" onClick={() => setRefreshKey((k) => k + 1)}>
            刷新
          </button>
        </div>

        <div style={{ height: 10 }} />
        <div style={{ display: 'grid', gap: 10 }}>
          {list.length === 0 ? (
            <div className="muted">暂无求助。你可以先发一条测试。</div>
          ) : (
            list.map((h) => (
              <div key={h.id} className="listItem" style={{ cursor: 'default' }}>
                <div style={{ display: 'grid', gap: 6 }}>
                  <div style={{ fontWeight: 820, letterSpacing: '-0.01em' }}>
                    {h.title}{' '}
                    <span className="tag" style={{ marginLeft: 8 }}>
                      {h.urgency}
                    </span>
                  </div>
                  <div className="muted" style={{ fontSize: 13, lineHeight: 1.6 }}>
                    {h.detail || '（无细节）'}
                  </div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {fmt(h.createdAt)} · expires {fmt(h.expiresAt)} · {h.venue}
                  </div>
                </div>
                <button
                  type="button"
                  className="softBtn"
                  onClick={() => {
                    closeHelp(h.id);
                    setRefreshKey((k) => k + 1);
                  }}
                >
                  关闭
                </button>
              </div>
            ))
          )}
        </div>
      </section>
    </motion.main>
  );
}

