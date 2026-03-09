import { motion } from 'framer-motion';
import { Link, useParams } from 'react-router-dom';
import { BackPill } from '../components/BackPill';
import { pageMotion } from '../motion/pageMotion';

const TITLES: Record<string, string> = {
  origin: '起点',
  'turning-point': '转折点',
  craft: '方法论',
};

export function PastDetailPage() {
  const { id } = useParams();
  const title = (id && TITLES[id]) || 'pass · 详情';

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/past" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">{title}</div>
          <div className="sub">这一层只讲“关键”，再下一层放证据/作品/过程。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18 }}>
        <div className="muted" style={{ lineHeight: 1.7 }}>
          这里放你的叙事：短、狠、可验证。让“名片”像一段高级预告片。
        </div>

        <div style={{ height: 14 }} />
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <Link className="softBtn" to={`/past/${id}/story`}>
            再下一层：故事线 →
          </Link>
          <Link className="softBtn softBtnPrimary" to={`/past/${id}/artifacts`}>
            再下一层：作品/证据 →
          </Link>
        </div>
      </section>
    </motion.main>
  );
}

