import { describe, test, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import SimpleHeader from '@/components/SimpleHeader';

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(() => '/'),
}));

describe('SimpleHeader', () => {
  test('renders brand name Aminra', () => {
    render(<SimpleHeader />);
    expect(screen.getByText('Aminra')).toBeInTheDocument();
  });

  test('renders Chat and Upload nav links', () => {
    render(<SimpleHeader />);
    expect(screen.getByRole('link', { name: 'Chat' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: 'Upload' })).toHaveAttribute('href', '/upload');
  });

  test('highlights active link on current pathname', async () => {
    const nav = await import('next/navigation');
    vi.mocked(nav.usePathname).mockReturnValue('/upload');

    render(<SimpleHeader />);
    const uploadLink = screen.getByRole('link', { name: 'Upload' });
    expect(uploadLink.className).toContain('text-emerald-600');
  });
});
