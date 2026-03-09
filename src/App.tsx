import { AnimatePresence, MotionConfig } from 'framer-motion';
import { Route, Routes, useLocation } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { PastPage } from './pages/PastPage';
import { PastDetailPage } from './pages/PastDetailPage';
import { PastSubPage } from './pages/PastSubPage';
import { NowPage } from './pages/NowPage';
import { NowDetailPage } from './pages/NowDetailPage';
import { NowSubPage } from './pages/NowSubPage';
import { FuturePage } from './pages/FuturePage';
import { FutureDetailPage } from './pages/FutureDetailPage';
import { FutureSubPage } from './pages/FutureSubPage';
import { NowCardPage } from './pages/now/NowCardPage';
import { NowHelpPage } from './pages/now/NowHelpPage';
import { NowPublicPage } from './pages/now/NowPublicPage';
import { NowRobot4SPage } from './pages/now/NowRobot4SPage';
import { FutureEmergencyPage } from './pages/future/FutureEmergencyPage';
import { FutureUniversePage } from './pages/future/FutureUniversePage';
import { NotFoundPage } from './pages/NotFoundPage';
import { CapsuleNav } from './components/CapsuleNav';

export function App() {
  const location = useLocation();

  return (
    <MotionConfig
      transition={{ type: 'spring', stiffness: 260, damping: 28, mass: 0.6 }}
      reducedMotion="user"
    >
      <div className="appRoot">
        <div className="appStage" role="application" aria-label="Ahelpis 名片">
          <AnimatePresence mode="wait" initial={false}>
            <Routes location={location} key={location.pathname}>
              <Route path="/" element={<HomePage />} />
              <Route path="/past" element={<PastPage />} />
              <Route path="/past/:id" element={<PastDetailPage />} />
              <Route path="/past/:id/:subId" element={<PastSubPage />} />
              <Route path="/now" element={<NowPage />} />
              <Route path="/now/:id" element={<NowDetailPage />} />
              <Route path="/now/:id/:subId" element={<NowSubPage />} />
              <Route path="/now/card" element={<NowCardPage />} />
              <Route path="/now/help" element={<NowHelpPage />} />
              <Route path="/now/public" element={<NowPublicPage />} />
              <Route path="/now/robot4s" element={<NowRobot4SPage />} />
              <Route path="/future" element={<FuturePage />} />
              <Route path="/future/:id" element={<FutureDetailPage />} />
              <Route path="/future/:id/:subId" element={<FutureSubPage />} />
              <Route path="/future/emergency" element={<FutureEmergencyPage />} />
              <Route path="/future/universe" element={<FutureUniversePage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </AnimatePresence>

          <CapsuleNav />
        </div>
      </div>
    </MotionConfig>
  );
}

