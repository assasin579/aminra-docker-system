'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useTranslation } from 'react-i18next';
import { useState, useEffect } from 'react';
import { useAdminAuth } from './AdminAuthContext';
import { useUserAuth } from './UserAuthContext';
import AdminLoginModal from './AdminLoginModal';

export default function Sidebar({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const [clientReady, setClientReady] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  const { isAdmin, logout: logoutAdmin } = useAdminAuth();
  const { user, isAuthenticated, logout: logoutUser } = useUserAuth();
  const [showLogin, setShowLogin] = useState(false);

  useEffect(() => {
    setClientReady(true);
  }, []);

  const languages = [
    { code: 'en', name: 'English' },
    { code: 'vi', name: 'Tiếng Việt' },
    { code: 'ms', name: 'Bahasa Malaysia' },
    { code: 'ar', name: 'العربية' },
  ];

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    setLangOpen(false);
  };

  const dashboardHref = user?.role === 'business' ? '/dashboard/business' : user?.role === 'provider' ? '/dashboard/provider' : null;

  const navItems = [
    ...(dashboardHref ? [{
      label: 'Dashboard',
      href: dashboardHref,
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
      )
    }] : []),
    {
      label: t('navbar.home'),
      href: '/',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      )
    },
    {
      label: t('navbar.upload'),
      href: '/upload',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      )
    },
    ...(user?.role === 'business' ? [{
      label: 'Tài liệu',
      href: '/documents',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      )
    }] : []),
    ...(user?.role === 'business' && user?.is_owner ? [{
      label: 'Thành viên',
      href: '/members',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      )
    }] : []),
    ...(user?.role === 'provider' && user?.is_owner ? [{
      label: 'Quản lý Auditor',
      href: '/auditors',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      )
    }] : []),
    ...(user?.role === 'provider' ? [{
      label: 'Hồ sơ nhận',
      href: '/submissions',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
        </svg>
      )
    }] : []),
    ...(isAdmin ? [{
      label: 'Admin Panel',
      href: '/admin',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      )
    }] : []),
  ];

  return (
    <aside className="w-64 min-h-screen grid"
      style={{
        background: '#111725',
        borderRight: '1px solid #1e3a5f',
        gridTemplateRows: 'auto 1fr auto auto auto auto',
      }}>
      {/* Logo */}
      <div className="p-6" style={{borderBottom:'1px solid #1e3a5f'}}>
        <div className="grid items-center"
          style={{gridTemplateColumns: '1fr auto'}}>
          <div className="grid items-center"
            style={{gridTemplateColumns: '2.5rem 1fr', gap: '0.75rem'}}>
            <div className="h-10 w-10 rounded-full bg-green-600 grid place-items-center">
              <span className="text-white font-bold text-lg">A</span>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Aminra</h1>
              <p className="text-sm text-slate-400">Halal Certification</p>
            </div>
          </div>
          {onClose && (
            <button onClick={onClose} className="md:hidden text-slate-400 hover:text-white p-1" aria-label="Close menu">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="p-4 space-y-2 overflow-y-auto">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`grid items-center px-4 py-3 rounded-lg transition-all ${pathname === item.href
                ? 'bg-green-600 text-white shadow-md'
                : 'text-slate-300 hover:bg-green-600/20 hover:text-white'
              }`}
            style={{gridTemplateColumns: '1.25rem 1fr', gap: '0.75rem'}}
            onClick={onClose}
          >
            <div className={pathname === item.href ? 'text-white' : 'text-green-500'}>
              {item.icon}
            </div>
            <span className="font-medium">{item.label}</span>
          </Link>
        ))}
      </nav>

      {/* Auth section */}
      <div className="px-4 pb-3" style={{borderTop:'1px solid #1e3a5f', paddingTop:'12px'}}>
        {/* User logged in */}
        {isAuthenticated && user && (
          <div className="space-y-2">
            <div className="px-3 py-2.5 rounded-lg" style={{background:'rgba(34,197,94,0.06)', border:'1px solid rgba(34,197,94,0.15)'}}>
              <p className="text-xs font-semibold text-white truncate">{user.company_name}</p>
              <p className="text-xs mt-0.5 truncate" style={{color:'#64748b'}}>{user.email}</p>
              <span className="inline-block mt-1 px-1.5 py-0.5 rounded text-xs font-medium"
                style={{background: user.role === 'business' ? 'rgba(34,197,94,0.12)' : 'rgba(37,99,235,0.12)', color: user.role === 'business' ? '#4ade80' : '#60a5fa'}}>
                {user.role === 'business' ? (user.is_owner ? 'Chủ tài khoản' : 'Thành viên') : 'Tổ chức'}
              </span>
            </div>
            <button onClick={() => { logoutUser(); router.push('/'); onClose?.(); }}
              className="w-full grid items-center px-4 py-3 rounded-lg transition-all text-slate-300 hover:bg-red-500/20 hover:text-red-400" style={{gridTemplateColumns:'1.25rem 1fr',gap:'0.75rem'}}>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              <span className="font-medium">Đăng xuất</span>
            </button>
          </div>
        )}

        {/* Admin logged in (no user session) */}
        {!isAuthenticated && isAdmin && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{background:'rgba(34,197,94,0.08)', border:'1px solid rgba(34,197,94,0.2)'}}>
              <span style={{color:'#22c55e', fontSize:10}}>●</span>
              <span className="text-xs font-medium" style={{color:'#4ade80'}}>Admin đang đăng nhập</span>
            </div>
            <button onClick={() => { logoutAdmin(); router.push('/'); onClose?.(); }}
              className="w-full grid items-center px-4 py-3 rounded-lg transition-all text-slate-300 hover:bg-red-500/20 hover:text-red-400" style={{gridTemplateColumns:'1.25rem 1fr',gap:'0.75rem'}}>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              <span className="font-medium">Đăng xuất Admin</span>
            </button>
          </div>
        )}

        {/* Not logged in — show login options */}
        {!isAuthenticated && !isAdmin && (
          <div className="space-y-2">
            <Link href="/business/login" onClick={onClose}
              className="grid items-center px-4 py-3 rounded-lg transition-all text-slate-300 hover:bg-green-600/20 hover:text-white" style={{gridTemplateColumns:'1.25rem 1fr',gap:'0.75rem'}}>
              <div style={{color:'#4ade80'}}>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <span className="font-medium">Đăng nhập Doanh nghiệp</span>
            </Link>
            <Link href="/provider/login" onClick={onClose}
              className="grid items-center px-4 py-3 rounded-lg transition-all text-slate-300 hover:bg-green-600/20 hover:text-white" style={{gridTemplateColumns:'1.25rem 1fr',gap:'0.75rem'}}>
              <div style={{color:'#60a5fa'}}>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <span className="font-medium">Đăng nhập Tổ chức</span>
            </Link>
            <button onClick={() => setShowLogin(true)}
              className="w-full grid items-center px-4 py-3 rounded-lg transition-all text-slate-300 hover:bg-green-600/20 hover:text-white" style={{gridTemplateColumns:'1.25rem 1fr',gap:'0.75rem'}}>
              <div className="text-green-500">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <span className="font-medium">Đăng nhập Admin</span>
            </button>
          </div>
        )}
      </div>

      {/* Language Switcher */}
      <div className="p-4" style={{borderTop:'1px solid #1e3a5f'}}>
        <div className="relative">
          <button
            onClick={() => setLangOpen(!langOpen)}
            className="flex items-center justify-between w-full px-4 py-3 rounded-lg transition-colors text-slate-300 hover:border-green-500"
            style={{border:'1px solid #1e3a5f', background:'#162847'}}
          >
            <span>{t('navbar.language')}</span>
            <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {langOpen && (
            <div className="absolute bottom-full left-0 right-0 mb-2 rounded-lg shadow-lg z-50" style={{background:'#162847', border:'1px solid #1e3a5f'}}>
              {languages.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => changeLanguage(lang.code)}
                  className="w-full text-left px-4 py-3 transition-colors text-slate-300 hover:bg-green-600/20 hover:text-white"
                >
                  {lang.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4" style={{borderTop:'1px solid #1e3a5f'}}>
        <p className="text-xs text-center" style={{color:'#3d6a96'}} suppressHydrationWarning>
          © {new Date().getFullYear()} Aminra
        </p>
      </div>

      {showLogin && <AdminLoginModal onClose={(loggedIn) => {
        setShowLogin(false);
        if (loggedIn) { router.push('/admin'); onClose?.(); }
      }} />}
    </aside>
  );
}