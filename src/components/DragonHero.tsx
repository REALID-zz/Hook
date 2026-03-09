import { motion } from 'framer-motion';

export function DragonHero(props: { title?: string; subtitle?: string }) {
  return (
    <section className="dragonHero" aria-label="dragon landing">
      <div className="dragonGlow" aria-hidden="true" />
      <div className="dragonGrid" aria-hidden="true" />

      <div className="dragonText">
        <div className="dragonTitle">{props.title ?? 'Ahelpis'}</div>
        <div className="dragonSubtitle">{props.subtitle ?? '南法奶油风 · 彩色炫彩 · 实时交互名片'}</div>
      </div>

      <motion.svg
        className="dragonSvg"
        viewBox="0 0 900 420"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        initial={{ opacity: 0, y: 6, scale: 0.995 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.55, ease: [0.2, 0.8, 0.2, 1] }}
      >
        <defs>
          <linearGradient id="drg" x1="110" y1="80" x2="780" y2="340" gradientUnits="userSpaceOnUse">
            <stop stopColor="rgba(202,163,126,0.95)" />
            <stop offset="0.35" stopColor="rgba(127,154,122,0.85)" />
            <stop offset="0.7" stopColor="rgba(218,170,120,0.88)" />
            <stop offset="1" stopColor="rgba(145,122,98,0.78)" />
          </linearGradient>
          <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="7" result="blur" />
            <feColorMatrix
              in="blur"
              type="matrix"
              values="
                1 0 0 0 0
                0 1 0 0 0
                0 0 1 0 0
                0 0 0 .28 0"
              result="glow"
            />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* soft halo stroke */}
        <path
          d="M140 270
             C 170 140, 320 110, 360 190
             C 390 250, 330 292, 270 280
             C 190 260, 185 200, 240 168
             C 330 116, 520 140, 586 218
             C 646 290, 600 334, 520 320
             C 430 305, 430 244, 500 230
             C 640 202, 760 240, 820 170"
          stroke="rgba(255,255,255,0.65)"
          strokeWidth="14"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.55"
        />

        <motion.path
          d="M140 270
             C 170 140, 320 110, 360 190
             C 390 250, 330 292, 270 280
             C 190 260, 185 200, 240 168
             C 330 116, 520 140, 586 218
             C 646 290, 600 334, 520 320
             C 430 305, 430 244, 500 230
             C 640 202, 760 240, 820 170"
          stroke="url(#drg)"
          strokeWidth="7"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter="url(#softGlow)"
          initial={{ pathLength: 0, opacity: 0.0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 1.35, ease: [0.2, 0.9, 0.2, 1] }}
        />

        {/* head + horns */}
        <motion.path
          d="M820 170
             C 842 160, 860 166, 870 182
             C 878 196, 874 210, 862 220
             C 846 234, 824 230, 812 216
             C 802 204, 802 184, 820 170 Z"
          fill="rgba(255,253,250,.82)"
          stroke="rgba(202,163,126,.75)"
          strokeWidth="2"
          initial={{ scale: 0.94, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.9, duration: 0.5, ease: [0.2, 0.9, 0.2, 1] }}
        />
        <path
          d="M846 160 C 850 142, 866 130, 884 126"
          stroke="rgba(202,163,126,.65)"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <path
          d="M830 160 C 834 146, 828 134, 816 126"
          stroke="rgba(127,154,122,.55)"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </motion.svg>

      <div className="dragonHint muted">向下滑动进入 timeline</div>
    </section>
  );
}

