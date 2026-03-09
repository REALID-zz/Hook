import { motion } from 'framer-motion';
import { useParams } from 'react-router-dom';
import { BackPill } from '../components/BackPill';
import { pageMotion } from '../motion/pageMotion';

const SUB_TITLES: Record<string, string> = {
  milestones: '里程碑',
  proof: '可验证指标',
};

export function FutureSubPage() {
  const { id, subId } = useParams();
  const t = subId ? SUB_TITLES[subId] : '';

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref={id ? `/future/${id}` : '/future'} />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">{t || 'future · 下一层'}</div>
          <div className="sub">这一层是“兑现系统”：计划拆分 + 指标可追踪。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18 }}>
        <div style={{ display: 'grid', gap: 10 }}>
          <div style={{ fontWeight: 750 }}>路径</div>
          <div className="muted">
            /future/{id}/{subId}
          </div>
          <div className="divider" />
          <div className="muted" style={{ lineHeight: 1.75 }}>
            这层适合未来接入“实时”：比如订阅你的进度、上线公告、公开里程碑完成率、实时互动投票等。
          </div>
        </div>
      </section>
    </motion.main>
  );
}

