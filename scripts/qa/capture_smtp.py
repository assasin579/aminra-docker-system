#!/usr/bin/env python3
import asyncio
from aiosmtpd.controller import Controller

class Handler:
    async def handle_DATA(self, server, session, envelope):
        print('SMTP_CAPTURE_BEGIN', flush=True)
        print(f'FROM={envelope.mail_from}', flush=True)
        print('TO=' + ','.join(envelope.rcpt_tos), flush=True)
        data = envelope.content.decode('utf-8', errors='replace')
        for line in data.splitlines()[:80]:
            if line.lower().startswith(('subject:', 'from:', 'to:', 'content-type:')) or 'VERIFY_EMAIL' in line or 'verify' in line.lower() or 'action-token' in line:
                print(line[:500], flush=True)
        print('SMTP_CAPTURE_END', flush=True)
        return '250 Message accepted for QA capture'

if __name__ == '__main__':
    controller = Controller(Handler(), hostname='0.0.0.0', port=2525)
    controller.start()
    print('SMTP_CAPTURE_READY host=0.0.0.0 port=2525', flush=True)
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
