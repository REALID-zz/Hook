import { motion } from 'framer-motion';
import { useParams } from 'react-router-dom';
import { BackPill } from '../components/BackPill';
import { pageMotion } from '../motion/pageMotion';

const SUB_TITLES: Record<string, string> = {
  notes: '细节说明',
  cases: '案例 / 结果',
};

export function NowSubPage() {
  const { id, subId } = useParams();
  const t = subId ? SUB_TITLES[subId] : '';

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref={id ? `/now/${id}` : '/now'} />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">{t || 'now · 下一层'}</div>
          <div className="sub">把“可信度”做扎实：过程、对比、数据、样例。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18 }}>
        <div style={{ display: 'grid', gap: 10 }}>
          <div style={{ fontWeight: 750 }}>路径</div>
          <div className="muted">
            /now/{id}/{subId}
          </div>
          <div className="divider" />
          <div className="muted" style={{ lineHeight: 1.75 }}>
            这一层建议做成可复用组件：卡片、标签、时间线、对比块、引用块。后续你要加“更多功能”，都塞进这一层即可。
          </div>
        </div>
      </section>
    </motion.main>
  );
}

