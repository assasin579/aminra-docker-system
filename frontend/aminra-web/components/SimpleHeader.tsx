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
          <div className="h-8 w-8 rounded-full bg-gradient-to-r from-emerald-500 to-blue-500"></div>
          <span className="text-xl font-bold text-gray-900">Aminra</span>
        </div>

        <nav className="flex items-center space-x-6">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`font-medium transition-colors ${pathname === item.href
                  ? 'text-emerald-600'
                  : 'text-gray-700 hover:text-emerald-500'
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