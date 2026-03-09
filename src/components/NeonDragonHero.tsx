import { motion } from 'framer-motion';

export function NeonDragonHero(props: { headline?: string; subline?: string; cta?: string }) {
  return (
    <section className="neoDragonHero" aria-label="neon dragon landing">
      <div className="neoDragonBG" aria-hidden="true" />
      <div className="neoDragonScan" aria-hidden="true" />
      <div className="neoDragonVignette" aria-hidden="true" />

      <motion.div
        className="neoDragonBeast"
        initial={{ opacity: 0, y: 18, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.7, ease: [0.2, 0.9, 0.2, 1] }}
      >
        <motion.svg
          className="neoDragonSvg"
          viewBox="0 0 760 760"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="dNeon" x1="130" y1="140" x2="640" y2="640" gradientUnits="userSpaceOnUse">
              <stop stopColor="#F7FFFF" />
              <stop offset="0.35" stopColor="#A3FAFF" />
              <stop offset="0.68" stopColor="#33E2FF" />
              <stop offset="1" stopColor="#00B9FF" />
            </linearGradient>
            <filter id="dGlow" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="12" result="blur" />
              <feColorMatrix
                in="blur"
                type="matrix"
                values="
                  1 0 0 0 0
                  0 1 0 0 0
                  0 0 1 0 0
                  0 0 0 .36 0"
                result="glow"
              />
              <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* body silhouette */}
          <motion.path
            d="M380 102
               C 300 96, 238 140, 210 214
               C 184 284, 204 354, 244 408
               C 286 466, 294 532, 282 606
               C 272 670, 300 714, 350 728
               C 372 734, 388 734, 410 728
               C 460 714, 488 670, 478 606
               C 466 532, 474 466, 516 408
               C 556 354, 576 284, 550 214
               C 522 140, 460 96, 380 102 Z"
            stroke="url(#dNeon)"
            strokeWidth="22"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#dGlow)"
            opacity="0.74"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.25, ease: [0.2, 0.9, 0.2, 1] }}
          />

          {/* spine / energy */}
          <motion.path
            d="M380 150
               C 340 192, 326 240, 336 286
               C 346 332, 368 370, 380 410
               C 392 370, 414 332, 424 286
               C 434 240, 420 192, 380 150 Z"
            stroke="rgba(245,255,255,.88)"
            strokeWidth="7"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ delay: 0.18, duration: 0.95, ease: [0.2, 0.9, 0.2, 1] }}
          />

          {/* horns */}
          <path d="M318 172 C 292 152, 286 128, 298 106" stroke="rgba(160,250,255,.82)" strokeWidth="7" strokeLinecap="round" />
          <path d="M442 172 C 468 152, 474 128, 462 106" stroke="rgba(160,250,255,.82)" strokeWidth="7" strokeLinecap="round" />

          {/* jaw / whiskers */}
          <path d="M340 318 C 322 336, 312 356, 306 382" stroke="rgba(120,235,255,.76)" strokeWidth="6" strokeLinecap="round" />
          <path d="M420 318 C 438 336, 448 356, 454 382" stroke="rgba(120,235,255,.76)" strokeWidth="6" strokeLinecap="round" />
          <path d="M348 410 C 362 424, 398 424, 412 410" stroke="rgba(245,255,255,.72)" strokeWidth="6" strokeLinecap="round" />

          {/* inner outline */}
          <path
            d="M380 102
               C 300 96, 238 140, 210 214
               C 184 284, 204 354, 244 408
               C 286 466, 294 532, 282 606
               C 272 670, 300 714, 350 728
               C 372 734, 388 734, 410 728
               C 460 714, 488 670, 478 606
               C 466 532, 474 466, 516 408
               C 556 354, 576 284, 550 214
               C 522 140, 460 96, 380 102 Z"
            stroke="rgba(245,255,255,.56)"
            strokeWidth="6"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.84"
          />
        </motion.svg>
      </motion.div>

      <div className="neoDragonCopy">
        <div className="neoDragonHeadline">{props.headline ?? 'Honor the pass, play for the future'}</div>
        <div className="neoDragonSubline">{props.subline ?? 'Real-time card · on-site help · public messages'}</div>
      </div>

      <button type="button" className="neoDragonCTA">
        <span className="neoDragonCTAText">{props.cta ?? 'WELCOME'}</span>
        <span aria-hidden="true" className="neoDragonCTAArrow">
          ↗
        </span>
      </button>
    </section>
  );
}

