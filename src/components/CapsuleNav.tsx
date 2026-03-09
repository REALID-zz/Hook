import { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import clsx from 'clsx';

type NavItem = { key: 'past' | 'now' | 'future'; label: string; href: string };

const ITEMS: NavItem[] = [
  { key: 'past', label: 'pass', href: '/past' },
  { key: 'now', label: 'now', href: '/now' },
  { key: 'future', label: 'future', href: '/future' },
];

export function CapsuleNav() {
  const nav = useNavigate();
  const { pathname } = useLocation();

  const activeKey = useMemo(() => {
    if (pathname === '/') return null;
    for (const it of ITEMS) {
      if (pathname === it.href || pathname.startsWith(`${it.href}/`)) return it.key;
    }
    return null;
  }, [pathname]);

  return (
    <nav className="navDock" aria-label="主导航">
      {ITEMS.map((it) => (
        <button
          key={it.key}
          type="button"
          className={clsx('navBtn', activeKey === it.key && 'navBtnActive')}
          onClick={() => nav(it.href)}
          aria-current={activeKey === it.key ? 'page' : undefined}
        >
          <span className="navBtnLabel">{it.label}</span>
        </button>
      ))}
    </nav>
  );
}

