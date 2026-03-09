import { motion } from 'framer-motion';
import { useParams } from 'react-router-dom';
import { BackPill } from '../components/BackPill';
import { pageMotion } from '../motion/pageMotion';

const SUB_TITLES: Record<string, string> = {
  story: '故事线',
  artifacts: '作品 / 证据',
};

export function PastSubPage() {
  const { id, subId } = useParams();
  const t = subId ? SUB_TITLES[subId] : '';

  return (
    <motion.main className="page" {...pageMotion}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <BackPill fallbackHref={id ? `/past/${id}` : '/past'} />
        <div style={{ textAlign: 'right' }}>
          <div className="h1">{t || 'pass · 下一层'}</div>
          <div className="sub">这里是“最下沉的一层”：只放可复用组件与细节内容。</div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <section className="card" style={{ padding: 18 }}>
        <div style={{ display: 'grid', gap: 10 }}>
          <div style={{ fontWeight: 750 }}>路径</div>
          <div className="muted">
            /past/{id}/{subId}
          </div>
          <div className="divider" />
          <div className="muted" style={{ lineHeight: 1.75 }}>
            - 你可以在这里放：时间轴条目、截图、链接、证书、数据、引用。<br />
            - 这层天然适合做“组件化沉淀”，未来一键复用到其它页面。<br />
            - 返回策略：每层都有返回，不迷路。
          </div>
        </div>
      </section>
    </motion.main>
  );
}

