import { motion } from 'framer-motion';

export function TigerHero(props: { headline?: string; subline?: string; cta?: string }) {
  return (
    <section className="tigerHero" aria-label="neon tiger landing">
      <div className="tigerBG" aria-hidden="true" />
      <div className="tigerScan" aria-hidden="true" />
      <div className="tigerVignette" aria-hidden="true" />

      <motion.div
        className="tigerBeast"
        initial={{ opacity: 0, y: 18, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.65, ease: [0.2, 0.9, 0.2, 1] }}
      >
        <motion.svg
          className="tigerSvg"
          viewBox="0 0 640 760"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="tNeon" x1="110" y1="120" x2="530" y2="650" gradientUnits="userSpaceOnUse">
              <stop stopColor="#D9FFFF" />
              <stop offset="0.38" stopColor="#89F6FF" />
              <stop offset="0.72" stopColor="#2ED7FF" />
              <stop offset="1" stopColor="#00B9FF" />
            </linearGradient>
            <filter id="tGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="10" result="blur" />
              <feColorMatrix
                in="blur"
                type="matrix"
                values="
                  1 0 0 0 0
                  0 1 0 0 0
                  0 0 1 0 0
                  0 0 0 .34 0"
                result="glow"
              />
              <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Outer silhouette (glow) */}
          <motion.path
            d="M320 82
               C 246 78, 190 120, 162 180
               C 128 250, 142 332, 180 392
               C 214 446, 224 520, 212 596
               C 202 654, 222 702, 266 720
               C 302 736, 338 736, 374 720
               C 418 702, 438 654, 428 596
               C 416 520, 426 446, 460 392
               C 498 332, 512 250, 478 180
               C 450 120, 394 78, 320 82 Z"
            stroke="url(#tNeon)"
            strokeWidth="20"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#tGlow)"
            opacity="0.72"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.2, ease: [0.2, 0.9, 0.2, 1] }}
          />

          {/* Face + stripes (inner line) */}
          <motion.path
            d="M230 232
               C 250 180, 290 152, 320 152
               C 350 152, 390 180, 410 232
               C 432 288, 406 332, 368 350
               C 346 360, 336 378, 320 404
               C 304 378, 294 360, 272 350
               C 234 332, 208 288, 230 232 Z"
            stroke="rgba(235,255,255,.92)"
            strokeWidth="7"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ delay: 0.18, duration: 0.95, ease: [0.2, 0.9, 0.2, 1] }}
          />
          <path d="M250 210 C 228 202, 210 188, 198 168" stroke="rgba(150,246,255,.82)" strokeWidth="6" strokeLinecap="round" />
          <path d="M390 210 C 412 202, 430 188, 442 168" stroke="rgba(150,246,255,.82)" strokeWidth="6" strokeLinecap="round" />
          <path d="M278 270 C 254 274, 240 290, 232 310" stroke="rgba(120,235,255,.78)" strokeWidth="6" strokeLinecap="round" />
          <path d="M362 270 C 386 274, 400 290, 408 310" stroke="rgba(120,235,255,.78)" strokeWidth="6" strokeLinecap="round" />
          <path d="M286 318 C 304 300, 336 300, 354 318" stroke="rgba(235,255,255,.88)" strokeWidth="6" strokeLinecap="round" />
          <path d="M306 356 C 316 366, 324 366, 334 356" stroke="rgba(235,255,255,.78)" strokeWidth="6" strokeLinecap="round" />

          {/* subtle inner glow duplicate */}
          <path
            d="M320 82
               C 246 78, 190 120, 162 180
               C 128 250, 142 332, 180 392
               C 214 446, 224 520, 212 596
               C 202 654, 222 702, 266 720
               C 302 736, 338 736, 374 720
               C 418 702, 438 654, 428 596
               C 416 520, 426 446, 460 392
               C 498 332, 512 250, 478 180
               C 450 120, 394 78, 320 82 Z"
            stroke="rgba(235,255,255,.55)"
            strokeWidth="6"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.8"
          />
        </motion.svg>
      </motion.div>

      <div className="tigerCopy">
        <div className="tigerHeadline">{props.headline ?? 'Honor the past, play for the future'}</div>
        <div className="tigerSubline">{props.subline ?? 'Real-time card · on-site help · public messages'}</div>
      </div>

      <button type="button" className="tigerCTA">
        <span className="tigerCTAText">{props.cta ?? 'WELCOME TO THE CLUB'}</span>
        <span aria-hidden="true" className="tigerCTAArrow">
          ↗
        </span>
      </button>
    </section>
  );
}

