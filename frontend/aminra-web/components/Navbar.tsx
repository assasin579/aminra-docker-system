'use client';

import { useTranslation } from 'react-i18next';
import Link from 'next/link';
import { useState } from 'react';

const languages = [
  { code: 'en', name: 'English' },
  { code: 'vi', name: 'Tiếng Việt' },
  { code: 'ar', name: 'العربية' },
];

export default function Navbar() {
  const { t, i18n } = useTranslation();
  const [isLangOpen, setIsLangOpen] = useState(false);

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    setIsLangOpen(false);
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-gray-200 bg-white/80 backdrop-blur-md">
      <div className="container mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/aminra-mark.svg" alt="AMINRA" className="h-8 w-8" />
          <span className="text-xl font-bold tracking-wider" style={{ color: '#0F5132' }}>AMINRA</span>
        </div>

        <nav className="hidden md:flex items-center space-x-8">
          <Link
            href="/"
            className="font-medium transition-colors"
            style={{ color: '#374151' }}
          >
            {t('navbar.home')}
          </Link>
          <Link
            href="/upload"
            className="font-medium transition-colors"
            style={{ color: '#374151' }}
          >
            {t('navbar.upload')}
          </Link>
        </nav>

        <div className="relative">
          <button
            onClick={() => setIsLangOpen(!isLangOpen)}
            className="flex items-center space-x-2 px-4 py-2 rounded-lg border border-gray-300 transition-colors bg-white"
            style={{ borderColor: '#E2E8F0' }}
          >
            <span className="text-gray-700">{t('navbar.language')}</span>
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>

          {isLangOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
              {languages.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => changeLanguage(lang.code)}
                  className="w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors"
                  style={{ color: i18n.language === lang.code ? '#0F5132' : '#374151', background: i18n.language === lang.code ? '#E8F5EF' : 'transparent', fontWeight: i18n.language === lang.code ? 600 : 400 }}
                >
                  {lang.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}