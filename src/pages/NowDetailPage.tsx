import { motion } from 'framer-motion';
import { Link, useParams } from 'react-router-dom';
import { BackPill } from '../components/BackPill';
import { pageMotion } from '../motion/pageMotion';

const TITLES: Record<string, string> = {
  mission: '我在做什么',
  stack: '能力栈',
  collab: '合作方式',
};

export function NowDetailPage() {
  const { id } = useParams();
  const title = (id && TITLES[id]) || 'now · 详情';

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/now" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">{title}</div>
          <div className="sub">这一层讲结论：你能提供什么、做到什么标准。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18 }}>
        <div className="muted" style={{ lineHeight: 1.7 }}>
          用“可交付”的语言描述：范围、标准、节奏、边界。让对方一眼知道怎么和你合作。
        </div>

        <div style={{ height: 14 }} />
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <Link className="softBtn" to={`/now/${id}/notes`}>
            再下一层：细节说明 →
          </Link>
          <Link className="softBtn softBtnPrimary" to={`/now/${id}/cases`}>
            再下一层：案例/结果 →
          </Link>
        </div>
      </section>
    </motion.main>
  );
}

