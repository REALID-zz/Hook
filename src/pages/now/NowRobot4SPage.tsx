import { motion } from 'framer-motion';
import { useMemo, useState } from 'react';
import { pageMotion } from '../../motion/pageMotion';
import { BackPill } from '../../components/BackPill';
import { addPost, loadState } from '../../data/store';

export function NowRobot4SPage() {
  const base = useMemo(() => loadState(), []);
  const [venue, setVenue] = useState(base.venue);
  const [title, setTitle] = useState('');
  const [detail, setDetail] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const list = useMemo(() => {
    const s = loadState();
    return s.posts
      .filter((p) => p.venue === venue)
      .filter((p) => p.category === 'robot4s')
      .sort((a, b) => b.createdAt - a.createdAt);
  }, [venue, refreshKey]);

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/now" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">robot 4S</div>
          <div className="sub">专门跟机器人相关：维修/保养、二手、配件、需求撮合（Demo）。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18, display: 'grid', gap: 12 }}>
        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <div style={{ fontWeight: 760 }}>发布机器人信息</div>
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
          placeholder="例如：宇树 Go2 保养 / 维修 / 配件 / 二手转让 / 求购"
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
          placeholder="写清楚：型号、问题/成色、预算、时间、联系方式（建议先不写敏感信息）"
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
              addPost({ venue, category: 'robot4s', title: title.trim(), detail: detail.trim() });
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
          <div style={{ fontWeight: 760 }}>当前 venue 聚合</div>
          <button type="button" className="softBtn" onClick={() => setRefreshKey((k) => k + 1)}>
            刷新
          </button>
        </div>

        <div style={{ height: 10 }} />
        <div style={{ display: 'grid', gap: 10 }}>
          {list.length === 0 ? (
            <div className="muted">暂无机器人相关内容。你可以先发一条测试。</div>
          ) : (
            list.map((p) => (
              <div key={p.id} className="listItem" style={{ cursor: 'default' }}>
                <div style={{ display: 'grid', gap: 6 }}>
                  <div style={{ fontWeight: 820, letterSpacing: '-0.01em' }}>{p.title}</div>
                  <div className="muted" style={{ fontSize: 13, lineHeight: 1.6 }}>
                    {p.detail || '（无内容）'}
                  </div>
                </div>
                <button
                  type="button"
                  className="softBtn"
                  onClick={async () => {
                    await navigator.clipboard.writeText(`${p.title}\n${p.detail}`);
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

