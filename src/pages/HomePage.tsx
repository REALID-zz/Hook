import { motion } from 'framer-motion';
import { useEffect, useMemo, useState } from 'react';
import { pageMotion } from '../motion/pageMotion';
import { useNowTicker } from '../hooks/useNowTicker';
import { TimelineBubbles } from '../components/TimelineBubbles';
import { PixelDragonHero } from '../components/PixelDragonHero';
import { Link } from 'react-router-dom';
import { addGreeting, loadState, updateProfile } from '../data/store';

function pad2(n: number) {
  return String(n).padStart(2, '0');
}

function formatTime(d: Date) {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

export function HomePage() {
  const now = useNowTicker(1000);
  const [refresh, setRefresh] = useState(0);
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState('');
  const state = useMemo(() => loadState(), [refresh]);
  const profile = state.profile;
  const greetings = state.greetings;

  const preview = useMemo(() => {
    const base = msg.trim();
    if (!base) return '我在听。你可以直接说重点。';
    return `收到：${base}`;
  }, [msg]);

  const canSend = msg.trim().length > 0;

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'ahelpis-demo-state-v1') setRefresh((v) => v + 1);
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="fadeTop" />
      <div className="fadeBottom" />

      <PixelDragonHero
        headline="Honor the pass, play for the future"
        subline="Cream · colorful glow · real-time interaction"
        cta="ENTER"
        onCta={() => {
          document.querySelector('.timelineCard')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }}
      />

      <div style={{ height: 14 }} />

      <section className="card">
        <div style={{ padding: 20, display: 'grid', gridTemplateColumns: '92px 1fr', gap: 18, alignItems: 'center' }}>
          <div
            aria-label="头像"
            style={{
              width: 92,
              height: 92,
              borderRadius: 28,
              border: '1px solid rgba(234,223,206,.95)',
              background:
                'radial-gradient(60px 60px at 30% 25%, rgba(255,255,255,.95), rgba(255,255,255,0)), linear-gradient(135deg, rgba(202,163,126,.38), rgba(127,154,122,.30))',
              boxShadow: '0 18px 38px rgba(31,35,40,.10)',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div
              aria-hidden="true"
              style={{
                position: 'absolute',
                inset: 0,
                background:
                  'radial-gradient(120px 80px at 60% 0%, rgba(255,255,255,.60), rgba(255,255,255,0) 62%)',
              }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <div style={{ fontSize: 18, fontWeight: 750, letterSpacing: '-0.01em' }}>{profile.displayName || 'Ahelpis'}</div>
              <div className="muted" style={{ fontSize: 13 }}>
                {profile.status} · 本地时间 {formatTime(now)}
              </div>
            </div>
            <div style={{ marginTop: 8 }} className="muted">
              {profile.tagline || '一张名片 · 实时可交互 · 南法奶油风炫彩'}
            </div>
            <div style={{ marginTop: 14, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <a className="link" href={profile.contact?.email ? `mailto:${profile.contact.email}` : 'mailto:hello@ahelpis.com'}>
                邮箱
              </a>
              <span className="muted">·</span>
              {profile.contact?.wechat ? (
                <button
                  type="button"
                  className="softBtn"
                  onClick={async () => {
                    const txt = profile.contact?.wechat ?? '';
                    if (!txt) return;
                    try {
                      await navigator.clipboard.writeText(txt);
                    } catch {
                      window.prompt('复制失败（系统限制）。请手动复制：', txt);
                    }
                  }}
                >
                  复制微信
                </button>
              ) : (
                <span className="muted">微信未设置</span>
              )}
              <span className="muted">·</span>
              <button type="button" className="softBtn softBtnPrimary" onClick={() => setOpen(true)}>
                实时打招呼
              </button>
              <button
                type="button"
                className="softBtn"
                onClick={() => {
                  const next = profile.status === 'online' ? 'focus' : profile.status === 'focus' ? 'offline' : 'online';
                  updateProfile({ status: next });
                  setRefresh((v) => v + 1);
                }}
              >
                切换状态
              </button>
              <Link className="softBtn" to="/now/card" onClick={() => setRefresh((v) => v + 1)}>
                编辑名片
              </Link>
            </div>
          </div>
        </div>

        <div className="divider" />

        <div style={{ padding: 18, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div className="muted" style={{ fontSize: 13 }}>
            只保留 3 个胶囊按钮：pass / now / future。其他内容全部下沉到下一层页面。
          </div>
          <div className="row" style={{ gap: 10 }}>
            <span className="kbd">pass</span>
            <span className="kbd">now</span>
            <span className="kbd">future</span>
          </div>
        </div>

        <div className="divider" />

        <div style={{ padding: 18, display: 'grid', gap: 10 }}>
          <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <div style={{ fontWeight: 760 }}>最近打招呼</div>
            <button type="button" className="softBtn" onClick={() => setOpen(true)}>
              发送新的
            </button>
          </div>
          {greetings.length === 0 ? (
            <div className="muted" style={{ fontSize: 13, lineHeight: 1.6 }}>
              还没有记录。点“发送新的”，写一句话，你的名片就有了“实时痕迹”。
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {greetings.slice(0, 5).map((g) => (
                <div key={g.id} className="listItem" style={{ cursor: 'default' }}>
                  <div style={{ display: 'grid', gap: 6 }}>
                    <div style={{ fontWeight: 820, letterSpacing: '-0.01em' }}>{g.message}</div>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {g.from} · {new Date(g.createdAt).toLocaleString()} · {g.venue}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="softBtn"
                    onClick={async () => {
                      const txt = `${g.message}\n${g.from} · ${g.venue}`;
                      try {
                        await navigator.clipboard.writeText(txt);
                      } catch {
                        window.prompt('复制失败（系统限制）。请手动复制：', txt);
                      }
                    }}
                  >
                    复制
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <TimelineBubbles />

      {open ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="实时打招呼"
          onMouseDown={() => setOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(31,35,40,.30)',
            backdropFilter: 'blur(10px)',
            WebkitBackdropFilter: 'blur(10px)',
            display: 'grid',
            placeItems: 'center',
            padding: 16,
            zIndex: 50,
          }}
        >
          <motion.div
            onMouseDown={(e) => e.stopPropagation()}
            initial={{ opacity: 0, y: 18, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 18, scale: 0.98 }}
            className="card"
            style={{ width: 'min(560px, 100%)' }}
          >
            <div style={{ padding: 18, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ fontWeight: 760, letterSpacing: '-0.01em' }}>实时交互</div>
              <button type="button" className="softBtn" onClick={() => setOpen(false)}>
                关闭
              </button>
            </div>
            <div className="divider" />
            <div style={{ padding: 18, display: 'grid', gap: 10 }}>
              <div className="muted" style={{ fontSize: 13 }}>
                这是“名片的实时痕迹”：你发出一句话，就会写入本地记录；多端可升级为真正的实时（WebSocket/Supabase/Convex）。
              </div>
              <input
                value={msg}
                onChange={(e) => setMsg(e.target.value)}
                placeholder="一句话就好，越直接越强"
                style={{
                  height: 44,
                  borderRadius: 14,
                  border: '1px solid rgba(234,223,206,.95)',
                  padding: '0 14px',
                  outline: 'none',
                  background: 'rgba(255,255,255,.70)',
                }}
              />
              <div className="card" style={{ padding: 14, borderRadius: 18 }}>
                <div style={{ fontSize: 13, fontWeight: 680 }}>预览</div>
                <div style={{ marginTop: 8 }} className="muted">
                  {preview}
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
                <button type="button" className="softBtn" onClick={() => setMsg('')}>
                  清空
                </button>
                <button
                  type="button"
                  className="softBtn softBtnPrimary"
                  onClick={() => {
                    const text = msg.trim();
                    if (!text) return;
                    addGreeting({
                      venue: state.venue,
                      from: profile.displayName || 'Ahelpis',
                      message: text,
                    });
                    setRefresh((v) => v + 1);
                    setOpen(false);
                    setMsg('');
                  }}
                  disabled={!canSend}
                  style={canSend ? undefined : { opacity: 0.55, cursor: 'not-allowed' }}
                >
                  发送
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      ) : null}
    </motion.main>
  );
}

