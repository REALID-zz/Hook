import { motion } from 'framer-motion';
import { useMemo, useState } from 'react';
import { pageMotion } from '../../motion/pageMotion';
import { BackPill } from '../../components/BackPill';
import { loadState, updateProfile } from '../../data/store';

export function NowCardPage() {
  const s = useMemo(() => loadState(), []);
  const [name, setName] = useState(s.profile.displayName);
  const [tagline, setTagline] = useState(s.profile.tagline);
  const [email, setEmail] = useState(s.profile.contact?.email ?? '');
  const [wechat, setWechat] = useState(s.profile.contact?.wechat ?? '');

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/now" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">card</div>
          <div className="sub">名片交友：可编辑、可复制、可打招呼（Demo 本地保存）。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18, display: 'grid', gap: 12 }}>
        <div style={{ display: 'grid', gap: 8 }}>
          <div style={{ fontWeight: 760 }}>编辑名片</div>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="display name"
            style={{
              height: 44,
              borderRadius: 14,
              border: '1px solid rgba(234,223,206,.95)',
              padding: '0 14px',
              outline: 'none',
              background: 'rgba(255,255,255,.70)',
            }}
          />
          <input
            value={tagline}
            onChange={(e) => setTagline(e.target.value)}
            placeholder="tagline"
            style={{
              height: 44,
              borderRadius: 14,
              border: '1px solid rgba(234,223,206,.95)',
              padding: '0 14px',
              outline: 'none',
              background: 'rgba(255,255,255,.70)',
            }}
          />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email"
              style={{
                height: 44,
                borderRadius: 14,
                border: '1px solid rgba(234,223,206,.95)',
                padding: '0 14px',
                outline: 'none',
                background: 'rgba(255,255,255,.70)',
              }}
            />
            <input
              value={wechat}
              onChange={(e) => setWechat(e.target.value)}
              placeholder="wechat"
              style={{
                height: 44,
                borderRadius: 14,
                border: '1px solid rgba(234,223,206,.95)',
                padding: '0 14px',
                outline: 'none',
                background: 'rgba(255,255,255,.70)',
              }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="softBtn"
            onClick={async () => {
              const txt = `${name}\n${tagline}\n${email ? `email: ${email}` : ''}${wechat ? `\nwechat: ${wechat}` : ''}`.trim();
              await navigator.clipboard.writeText(txt);
            }}
          >
            复制名片
          </button>
          <button
            type="button"
            className="softBtn softBtnPrimary"
            onClick={() => {
              updateProfile({ displayName: name, tagline, contact: { email, wechat } });
            }}
          >
            保存
          </button>
        </div>
      </section>
    </motion.main>
  );
}

