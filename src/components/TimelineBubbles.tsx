import { motion, useMotionValue } from 'framer-motion';
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import clsx from 'clsx';

import type { Phase } from '../features/features';
import { FEATURES, PHASE_LABEL } from '../features/features';

export function TimelineBubbles(props: { className?: string }) {
  const nav = useNavigate();
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const trackRef = useRef<HTMLDivElement | null>(null);

  const x = useMotionValue(0);
  const [constraints, setConstraints] = useState({ left: 0, right: 0 });

  const groups = useMemo(() => {
    const out: Record<Phase, (typeof FEATURES)[number][]> = { past: [], now: [], future: [] };
    for (const it of FEATURES) out[it.phase].push(it);
    return out;
  }, []);

  useLayoutEffect(() => {
    const el = viewportRef.current;
    const track = trackRef.current;
    if (!el || !track) return;

    const compute = () => {
      const vw = el.getBoundingClientRect().width;
      const tw = track.scrollWidth;
      const overflow = Math.max(0, tw - vw);
      setConstraints({ left: -overflow, right: 0 });
    };

    compute();
    const ro = new ResizeObserver(() => compute());
    ro.observe(el);
    ro.observe(track);
    return () => ro.disconnect();
  }, []);

  // Keep x inside constraints if content resizes smaller.
  useEffect(() => {
    const cur = x.get();
    if (cur < constraints.left) x.set(constraints.left);
    if (cur > constraints.right) x.set(constraints.right);
  }, [constraints.left, constraints.right, x]);

  return (
    <section className={clsx('timelineCard', props.className)}>
      <div className="timelineHeader">
        <div>
          <div className="timelineTitle">timeline</div>
          <div className="timelineSub">气泡滑动 · 点击即进入下一层</div>
        </div>
        <div className="timelineHint">
          <span className="kbd">drag</span>
          <span className="muted">or</span>
          <span className="kbd">swipe</span>
        </div>
      </div>

      <div ref={viewportRef} className="timelineViewport">
        <div className="timelineMaskLeft" aria-hidden="true" />
        <div className="timelineMaskRight" aria-hidden="true" />

        <motion.div
          ref={trackRef}
          className="timelineTrack"
          drag="x"
          dragConstraints={constraints}
          dragElastic={0.06}
          style={{ x }}
          whileTap={{ cursor: 'grabbing' }}
        >
          {(['past', 'now', 'future'] as Phase[]).map((phase) => (
            <div key={phase} className="timelineGroup">
              <div className={clsx('timelineGroupLabel', `timelineGroupLabel-${phase}`)}>
                {PHASE_LABEL[phase]}
              </div>

              <div className="timelineRow">
                {groups[phase].map((it) => (
                  <motion.button
                    key={it.id}
                    type="button"
                    className={clsx('bubble', `bubble-${it.phase}`)}
                    onClick={() => nav(it.href)}
                    whileHover={{ y: -2 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <div className="bubbleHalo" aria-hidden="true" />
                    <div className="bubbleInner">
                      <div className="bubbleTitle">{it.title}</div>
                      <div className="bubbleSub">{it.subtitle}</div>
                    </div>
                    <div className="bubbleArrow" aria-hidden="true">
                      →
                    </div>
                  </motion.button>
                ))}
              </div>
            </div>
          ))}

          <div className="timelineEnd" aria-hidden="true">
            <div className="timelineEndDot" />
          </div>
        </motion.div>
      </div>

      <div className="timelineFooter muted">
        功能分配固定：pass（叙事）· now（可用功能）· future（升级/官方通道）
      </div>
    </section>
  );
}

