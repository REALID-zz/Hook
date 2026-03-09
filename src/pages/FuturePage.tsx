import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { BackPill } from '../components/BackPill';
import { pageMotion } from '../motion/pageMotion';

const FUTURE = [
  { href: '/future/emergency', title: 'emergency', desc: '高风险信息：按理由归类 → 默认私有 → 导出官方数据包（可用）' },
  { href: '/future/universe', title: 'universe', desc: 'Universe 选项容器：可挂载外部能力（外部内容）' },
];

export function FuturePage() {
  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">future</div>
          <div className="sub">高价值/高风险能力放在 future：受控上报与升级通道。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18 }}>
        <div style={{ display: 'grid', gap: 12 }}>
          {FUTURE.map((it) => (
            <Link key={it.href} to={it.href} className="listItem">
              <div style={{ display: 'grid', gap: 6 }}>
                <div style={{ fontWeight: 780, letterSpacing: '-0.01em' }}>{it.title}</div>
                <div className="muted" style={{ fontSize: 13, lineHeight: 1.55 }}>
                  {it.desc}
                </div>
              </div>
              <div aria-hidden="true" style={{ paddingTop: 2 }}>
                →
              </div>
            </Link>
          ))}
        </div>
      </section>
    </motion.main>
  );
}

