import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { BackPill } from '../components/BackPill';
import { pageMotion } from '../motion/pageMotion';

const NOW = [
  { href: '/now/card', title: 'card', desc: '名片交友 / 打招呼 / 复制名片（可用）' },
  { href: '/now/help', title: 'help', desc: '实时获得帮助：Now 流（可用）' },
  { href: '/now/public', title: 'public', desc: '公共消息：Keep 流（可用）' },
  { href: '/now/robot4s', title: 'robot 4S', desc: '机器人4S店：维修/二手/配件/需求（可用）' },
];

export function NowPage() {
  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">now</div>
          <div className="sub">用户当下可用的功能都在这里：名片、互助、公共消息、机器人4S。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18 }}>
        <div style={{ display: 'grid', gap: 12 }}>
          {NOW.map((it) => (
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

