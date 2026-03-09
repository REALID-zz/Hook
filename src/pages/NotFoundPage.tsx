import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { pageMotion } from '../motion/pageMotion';

export function NotFoundPage() {
  return (
    <motion.main className="page" {...pageMotion}>
      <div className="h1">未找到</div>
      <div className="sub">这个页面不存在。你可以返回首页，或用底部胶囊导航跳转。</div>
      <div style={{ height: 14 }} />
      <Link className="softBtn softBtnPrimary" to="/">
        回到名片
      </Link>
    </motion.main>
  );
}

