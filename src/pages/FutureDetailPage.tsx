import { motion } from 'framer-motion';
import { Link, useParams } from 'react-router-dom';
import { BackPill } from '../components/BackPill';
import { pageMotion } from '../motion/pageMotion';

const TITLES: Record<string, string> = {
  roadmap: '路线图',
  partners: '理想合作者',
  ask: '我需要什么',
};

export function FutureDetailPage() {
  const { id } = useParams();
  const title = (id && TITLES[id]) || 'future · 详情';

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref="/future" />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">{title}</div>
          <div className="sub">把未来写成“可执行的剧本”，而不是宏大口号。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18 }}>
        <div className="muted" style={{ lineHeight: 1.7 }}>
          建议结构：目标 → 衡量标准 → 阶段里程碑 → 你愿意付出的代价。
        </div>

        <div style={{ height: 14 }} />
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <Link className="softBtn" to={`/future/${id}/milestones`}>
            再下一层：里程碑 →
          </Link>
          <Link className="softBtn softBtnPrimary" to={`/future/${id}/proof`}>
            再下一层：可验证指标 →
          </Link>
        </div>
      </section>
    </motion.main>
  );
}

