import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { BackPill } from '../components/BackPill';
import { pageMotion } from '../motion/pageMotion';

const PAST = [
  { id: 'origin', title: '起点', desc: '一句话描述你的 pass：为什么你会走到今天。' },
  { id: 'turning-point', title: '转折点', desc: '你的关键选择、关键事件、关键作品。' },
  { id: 'craft', title: '方法论', desc: '你做事的框架、价值观、取舍风格。' },
];

export function PastPage() {
  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">pass</div>
          <div className="sub">所有“其它内容”都下沉到下一层：点进去看细节，再返回。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18 }}>
        <div style={{ display: 'grid', gap: 12 }}>
          {PAST.map((it) => (
            <Link key={it.id} to={`/past/${it.id}`} className="listItem">
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

