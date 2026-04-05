import { NextRequest } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://aminra-backend:8000';

export async function POST(req: NextRequest) {
  const body = await req.text();
  const upstream = await fetch(`${BACKEND}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: upstream.headers,
  });
}
