import { motion } from 'framer-motion';

type Px = { x: number; y: number; w?: number; h?: number };

const OUTLINE: Px[] = [
  // head (blocky)
  { x: 4, y: 2, w: 10, h: 1 },
  { x: 3, y: 3, w: 1, h: 6 },
  { x: 14, y: 3, w: 1, h: 6 },
  { x: 4, y: 9, w: 10, h: 1 },
  { x: 2, y: 5, w: 1, h: 3 }, // left ear-ish
  { x: 15, y: 4, w: 1, h: 3 }, // right step

  // neck + chest
  { x: 6, y: 10, w: 1, h: 6 },
  { x: 7, y: 16, w: 2, h: 1 },

  // body
  { x: 9, y: 10, w: 10, h: 1 },
  { x: 8, y: 11, w: 1, h: 8 },
  { x: 19, y: 11, w: 1, h: 8 },
  { x: 9, y: 19, w: 10, h: 1 },

  // legs
  { x: 7, y: 19, w: 1, h: 4 },
  { x: 6, y: 23, w: 4, h: 1 },
  { x: 16, y: 19, w: 1, h: 6 },

  // tail (zigzag)
  { x: 20, y: 14, w: 2, h: 1 },
  { x: 22, y: 13, w: 1, h: 2 },
  { x: 23, y: 12, w: 1, h: 2 },
  { x: 24, y: 11, w: 1, h: 2 },
  { x: 25, y: 10, w: 1, h: 2 },
  { x: 26, y: 11, w: 1, h: 2 },
  { x: 27, y: 12, w: 1, h: 2 },
  { x: 28, y: 13, w: 1, h: 2 },
  { x: 29, y: 14, w: 1, h: 2 },
];

const EYES: Px[] = [
  { x: 6, y: 5, w: 3, h: 1 },
  { x: 10, y: 5, w: 3, h: 1 },
];

const NOSE: Px[] = [{ x: 9, y: 7, w: 1, h: 1 }];

export function PixelDragonHero(props: { headline?: string; subline?: string; cta?: string; onCta?: () => void }) {
  return (
    <section className="pxHero" aria-label="pixel dragon landing">
      <div className="pxBG" aria-hidden="true" />
      <div className="pxVignette" aria-hidden="true" />

      <motion.div
        className="pxBeast"
        initial={{ opacity: 0, y: 16, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.7, ease: [0.2, 0.9, 0.2, 1] }}
      >
        <motion.svg
          className="pxSvg"
          viewBox="0 0 34 28"
          shapeRendering="crispEdges"
          aria-hidden="true"
          animate={{ y: [0, -4, 0], scale: [1, 1.02, 1] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
        >
          <defs>
            <filter id="pxGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="0.65" result="b" />
              <feColorMatrix
                in="b"
                type="matrix"
                values="
                  1 0 0 0 0
                  0 1 0 0 0
                  0 0 1 0 0
                  0 0 0 .75 0"
                result="g"
              />
              <feMerge>
                <feMergeNode in="g" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <g filter="url(#pxGlow)">
            {OUTLINE.map((p, i) => (
              <rect key={i} x={p.x} y={p.y} width={p.w ?? 1} height={p.h ?? 1} fill="rgba(225,255,235,.96)" />
            ))}
            {EYES.map((p, i) => (
              <rect key={`e${i}`} x={p.x} y={p.y} width={p.w ?? 1} height={p.h ?? 1} fill="rgba(225,255,235,.92)" />
            ))}
            {NOSE.map((p, i) => (
              <rect key={`n${i}`} x={p.x} y={p.y} width={p.w ?? 1} height={p.h ?? 1} fill="rgba(225,255,235,.86)" />
            ))}
          </g>
        </motion.svg>
      </motion.div>

      <div className="pxCopy">
        <div className="pxHeadline">{props.headline ?? 'Honor the pass, play for the future'}</div>
        <div className="pxSubline">{props.subline ?? 'Cream · colorful glow · real-time interaction'}</div>
      </div>

      <button type="button" className="pxCTA" onClick={() => props.onCta?.()}>
        <span className="pxCTAText">{props.cta ?? 'ENTER'}</span>
        <span aria-hidden="true" className="pxCTAArrow">
          ↗
        </span>
      </button>
    </section>
  );
}

