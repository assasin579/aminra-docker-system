'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function SimpleHeader() {
  const pathname = usePathname();

  const navItems = [
    { label: 'Chat', href: '/' },
    { label: 'Upload', href: '/upload' },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-gray-200 bg-white/90 backdrop-blur-sm">
      <div className="container mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/aminra-mark.svg" alt="AMINRA" className="h-8 w-8" />
          <span className="text-xl font-bold tracking-wider" style={{ color: '#0F5132' }}>AMINRA</span>
        </div>

        <nav className="flex items-center space-x-6">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`font-medium transition-colors ${pathname === item.href
                  ? 'text-[#0F5132]'
                  : 'text-gray-700 hover:text-[#0F5132]'
                }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}