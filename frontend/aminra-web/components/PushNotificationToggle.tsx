'use client';

import { useEffect, useState } from 'react';
import { useUserAuth } from '@/components/UserAuthContext';
import { isPushSupported, getCurrentSubscription, subscribePush, unsubscribePush } from '@/lib/pushSubscribe';

type State = 'loading' | 'unsupported' | 'idle' | 'enabled' | 'denied';

export default function PushNotificationToggle() {
  const { token, isAuthenticated } = useUserAuth();
  const [state, setState] = useState<State>('loading');
  const [busy, setBusy]   = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      if (!(await isPushSupported())) { setState('unsupported'); return; }
      if (typeof Notification !== 'undefined' && Notification.permission === 'denied') {
        setState('denied'); return;
      }
      const sub = await getCurrentSubscription();
      setState(sub ? 'enabled' : 'idle');
    })();
  }, []);

  if (!isAuthenticated || state === 'loading') return null;
  if (state === 'unsupported') return null;

  const onEnable = async () => {
    if (!token) return;
    setBusy(true); setError('');
    const r = await subscribePush(token);
    if (r.ok) setState('enabled');
    else {
      setError(r.reason === 'permission-denied' ? 'Bạn đã từ chối quyền thông báo' : `Không bật được thông báo (${r.reason})`);
      setState(r.reason === 'permission-denied' ? 'denied' : 'idle');
    }
    setBusy(false);
  };

  const onDisable = async () => {
    if (!token) return;
    setBusy(true); setError('');
    await unsubscribePush(token);
    setState('idle');
    setBusy(false);
  };

  return (
    <div className="rounded-xl p-4" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold" style={{ color: '#0A1F44' }}>Thông báo đẩy</p>
          <p className="text-xs mt-0.5" style={{ color: '#64748B' }}>
            {state === 'enabled' && 'Đang bật — bạn sẽ nhận thông báo về hồ sơ, chứng nhận, kiểm định ngay cả khi không mở web'}
            {state === 'idle'    && 'Bật để nhận thông báo realtime về thay đổi trạng thái hồ sơ + cert sắp hết hạn'}
            {state === 'denied'  && 'Bạn đã từ chối — vào cài đặt trình duyệt để bật lại quyền thông báo'}
          </p>
          {error && <p className="text-xs mt-1" style={{ color: '#DC2626' }}>{error}</p>}
        </div>
        {state === 'idle' && (
          <button onClick={onEnable} disabled={busy}
            className="px-4 py-2 rounded-lg text-xs font-semibold text-white transition-all hover:scale-105 disabled:opacity-50"
            style={{ background: '#0A1F44' }}>
            {busy ? 'Đang bật...' : 'Bật thông báo'}
          </button>
        )}
        {state === 'enabled' && (
          <button onClick={onDisable} disabled={busy}
            className="px-4 py-2 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-50"
            style={{ background: '#F5F1E8', color: '#6B7280', border: '1px solid #E2E8F0' }}>
            {busy ? 'Đang tắt...' : 'Tắt thông báo'}
          </button>
        )}
        {state === 'denied' && (
          <span className="text-xs px-3 py-1.5 rounded-lg" style={{ background: '#FEF3C7', color: '#92400E' }}>Đã chặn</span>
        )}
      </div>
    </div>
  );
}
