import { motion } from 'framer-motion';
import { pageMotion } from '../../motion/pageMotion';
import { BackPill } from '../../components/BackPill';

export function FutureUniversePage() {
  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/future" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">universe</div>
          <div className="sub">Universe 作为“选项容器”：这里可以挂载外部能力（例如公开信息看板）。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18, display: 'grid', gap: 12 }}>
        <div style={{ fontWeight: 760 }}>World Monitor（外部能力）</div>
        <div className="muted" style={{ lineHeight: 1.7 }}>
          这里用 iframe 挂载外部看板。真正“融合”建议走“能力级整合”（API/数据契约），避免把高风险信息直接公开展示。
        </div>
        <div
          className="card"
          style={{
            padding: 0,
            borderRadius: 18,
            overflow: 'hidden',
            height: 420,
            background: 'rgba(255,255,255,.55)',
          }}
        >
          <iframe
            title="World Monitor"
            src="https://worldmonitor.app/"
            style={{ width: '100%', height: '100%', border: 0 }}
            referrerPolicy="no-referrer"
          />
        </div>
      </section>
    </motion.main>
  );
}

