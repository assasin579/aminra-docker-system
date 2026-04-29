'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTranslation } from 'react-i18next';
import { useState, useEffect } from 'react';
import { useAdminAuth } from './AdminAuthContext';
import AdminLoginModal from './AdminLoginModal';

export default function Sidebar({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const { t, i18n } = useTranslation();
  const [clientReady, setClientReady] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  const { isAdmin, logout } = useAdminAuth();
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

  const navItems = [
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
    <aside className="w-64 min-h-screen flex flex-col" style={{background:'#111725', borderRight:'1px solid #1e3a5f'}}>
      {/* Logo */}
      <div className="p-6" style={{borderBottom:'1px solid #1e3a5f'}}>
        <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-full bg-green-600 flex items-center justify-center">
            <span className="text-white font-bold text-lg">M</span>
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Mukjizat Saigoncert</h1>
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
      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all ${pathname === item.href
                ? 'bg-green-600 text-white shadow-md'
                : 'text-slate-300 hover:bg-green-600/20 hover:text-white'
              }`}
            onClick={onClose}
          >
            <div className={pathname === item.href ? 'text-white' : 'text-green-500'}>
              {item.icon}
            </div>
            <span className="font-medium">{item.label}</span>
          </Link>
        ))}
      </nav>

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

      {/* Admin section */}
      <div className="px-4 pb-3" style={{borderTop:'1px solid #1e3a5f', paddingTop:'12px'}}>
        {isAdmin ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{background:'rgba(34,197,94,0.08)', border:'1px solid rgba(34,197,94,0.2)'}}>
              <span style={{color:'#22c55e', fontSize:10}}>●</span>
              <span className="text-xs font-medium" style={{color:'#4ade80'}}>Admin đang đăng nhập</span>
            </div>
            <button onClick={() => { logout(); onClose?.(); }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all"
              style={{color:'#94a3b8', background:'rgba(255,255,255,0.03)', border:'1px solid #1e3a5f'}}>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              Đăng xuất Admin
            </button>
          </div>
        ) : (
          <button onClick={() => setShowLogin(true)}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-xs font-medium transition-all"
            style={{color:'#94a3b8', background:'rgba(255,255,255,0.03)', border:'1px solid #1e3a5f'}}>
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            Đăng nhập Admin
          </button>
        )}
      </div>

      {/* Footer */}
      <div className="p-4" style={{borderTop:'1px solid #1e3a5f'}}>
        <p className="text-xs text-center" style={{color:'#3d6a96'}} suppressHydrationWarning>
          © {new Date().getFullYear()} Mukjizat Saigoncert
        </p>
      </div>

      {showLogin && <AdminLoginModal onClose={() => setShowLogin(false)} />}
    </aside>
  );
}
