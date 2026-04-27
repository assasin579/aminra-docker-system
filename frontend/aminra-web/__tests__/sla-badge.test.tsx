import { describe, test, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import SlaBadge from '@/components/submissions/SlaBadge';

afterEach(() => {
  vi.useRealTimers();
});

const now = new Date('2026-04-25T12:00:00Z');

function withFakeNow(fn: () => void) {
  vi.useFakeTimers();
  vi.setSystemTime(now);
  fn();
}

describe('SlaBadge', () => {
  test('renders nothing when missing deadline', () => {
    const { container } = render(<SlaBadge submittedAt="2026-04-01T00:00:00Z" deadline={null} status="reviewing" />);
    expect(container.firstChild).toBeNull();
  });

  test('renders nothing when missing submittedAt', () => {
    const { container } = render(<SlaBadge submittedAt={null} deadline="2026-05-01T00:00:00Z" status="reviewing" />);
    expect(container.firstChild).toBeNull();
  });

  test('renders nothing for terminal statuses (approved/rejected/returned)', () => {
    const props = {
      submittedAt: '2026-01-01T00:00:00Z',
      deadline: '2026-04-01T00:00:00Z',  // already past
    };
    for (const status of ['approved', 'rejected', 'returned']) {
      const { container } = render(<SlaBadge {...props} status={status} />);
      expect(container.firstChild).toBeNull();
    }
  });

  test('renders nothing when elapsed < 80%', () => {
    withFakeNow(() => {
      // Submitted 30 days ago, 100-day window → 30% elapsed
      const submittedAt = new Date(now.getTime() - 30 * 86400_000).toISOString();
      const deadline    = new Date(now.getTime() + 70 * 86400_000).toISOString();
      const { container } = render(<SlaBadge submittedAt={submittedAt} deadline={deadline} status="reviewing" />);
      expect(container.firstChild).toBeNull();
    });
  });

  test('renders WARNING badge at 80% elapsed', () => {
    withFakeNow(() => {
      // 80 days elapsed, 100-day window
      const submittedAt = new Date(now.getTime() - 80 * 86400_000).toISOString();
      const deadline    = new Date(now.getTime() + 20 * 86400_000).toISOString();
      render(<SlaBadge submittedAt={submittedAt} deadline={deadline} status="reviewing" />);
      const badge = screen.getByText(/Sắp hết hạn/i);
      expect(badge).toBeInTheDocument();
      expect(badge.closest('span')).toHaveAttribute('data-sla', 'warning');
    });
  });

  test('renders OVERDUE badge when past deadline', () => {
    withFakeNow(() => {
      const submittedAt = new Date(now.getTime() - 50 * 86400_000).toISOString();
      const deadline    = new Date(now.getTime() - 5 * 86400_000).toISOString();
      render(<SlaBadge submittedAt={submittedAt} deadline={deadline} status="reviewing" />);
      const badge = screen.getByText(/QUÁ HẠN/i);
      expect(badge).toBeInTheDocument();
      expect(badge.closest('span')).toHaveAttribute('data-sla', 'overdue');
      expect(badge.textContent).toContain('5d');
    });
  });

  test('renders nothing when deadline before submitted (malformed)', () => {
    withFakeNow(() => {
      const submittedAt = new Date(now.getTime() - 10 * 86400_000).toISOString();
      const deadline    = new Date(now.getTime() - 20 * 86400_000).toISOString();
      const { container } = render(<SlaBadge submittedAt={submittedAt} deadline={deadline} status="reviewing" />);
      expect(container.firstChild).toBeNull();
    });
  });

  test('warning badge shows days remaining count', () => {
    withFakeNow(() => {
      // 85% elapsed, ~15 days remaining of 100-day window
      const submittedAt = new Date(now.getTime() - 85 * 86400_000).toISOString();
      const deadline    = new Date(now.getTime() + 15 * 86400_000).toISOString();
      render(<SlaBadge submittedAt={submittedAt} deadline={deadline} status="reviewing" />);
      expect(screen.getByText(/15d/)).toBeInTheDocument();
    });
  });
});
