import { motion } from 'framer-motion';
import { useMemo, useState } from 'react';
import { pageMotion } from '../../motion/pageMotion';
import { BackPill } from '../../components/BackPill';
import { addPost, loadState } from '../../data/store';

function fmt(ts: number) {
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(
    d.getHours()
  ).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function NowPublicPage() {
  const base = useMemo(() => loadState(), []);
  const [venue, setVenue] = useState(base.venue);
  const [category, setCategory] = useState<'announcement' | 'lostfound' | 'community' | 'robot4s'>('community');
  const [title, setTitle] = useState('');
  const [detail, setDetail] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const list = useMemo(() => {
    const s = loadState();
    return s.posts
      .filter((p) => p.venue === venue)
      .filter((p) => (category ? p.category === category : true))
      .sort((a, b) => b.createdAt - a.createdAt);
  }, [venue, category, refreshKey]);

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/now" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">public</div>
          <div className="sub">公共消息：Keep 流（分类白名单，Demo 本地存储）。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18, display: 'grid', gap: 12 }}>
        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <div style={{ fontWeight: 760 }}>发布公共消息</div>
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
          <span className="tag">category</span>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as any)}
            style={{
              height: 36,
              borderRadius: 12,
              border: '1px solid rgba(234,223,206,.95)',
              padding: '0 10px',
              outline: 'none',
              background: 'rgba(255,255,255,.70)',
            }}
          >
            <option value="community">community</option>
            <option value="announcement">announcement</option>
            <option value="lostfound">lost&amp;found</option>
            <option value="robot4s">robot 4S</option>
          </select>
        </div>

        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="标题"
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
          placeholder="内容"
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

        <div className="row" style={{ justifyContent: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
          <button type="button" className="softBtn" onClick={() => setRefreshKey((k) => k + 1)}>
            刷新
          </button>
          <button
            type="button"
            className="softBtn softBtnPrimary"
            onClick={() => {
              if (!title.trim()) return;
              addPost({ venue, category, title: title.trim(), detail: detail.trim() });
              setTitle('');
              setDetail('');
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
          <div style={{ fontWeight: 760 }}>Keep 流</div>
          <button type="button" className="softBtn" onClick={() => setRefreshKey((k) => k + 1)}>
            刷新
          </button>
        </div>
        <div style={{ height: 10 }} />
        <div style={{ display: 'grid', gap: 10 }}>
          {list.length === 0 ? (
            <div className="muted">暂无内容。你可以先发一条测试。</div>
          ) : (
            list.map((p) => (
              <div key={p.id} className="listItem" style={{ cursor: 'default' }}>
                <div style={{ display: 'grid', gap: 6 }}>
                  <div style={{ fontWeight: 820, letterSpacing: '-0.01em' }}>
                    {p.title}{' '}
                    <span className="tag" style={{ marginLeft: 8 }}>
                      {p.category}
                    </span>
                  </div>
                  <div className="muted" style={{ fontSize: 13, lineHeight: 1.6 }}>
                    {p.detail || '（无内容）'}
                  </div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {fmt(p.createdAt)} · {p.venue}
                  </div>
                </div>
                <button
                  type="button"
                  className="softBtn"
                  onClick={async () => {
                    const txt = `${p.title}\n${p.detail}\n${p.category} · ${p.venue}`;
                    await navigator.clipboard.writeText(txt);
                  }}
                >
                  复制
                </button>
              </div>
            ))
          )}
        </div>
      </section>
    </motion.main>
  );
}

