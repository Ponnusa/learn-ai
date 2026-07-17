import { NextRequest, NextResponse } from 'next/server';

const ALLOWED_HOST = 'pub-ca784163fe614f62b1a3ebb8fe9ad1d3.r2.dev';

export async function GET(req: NextRequest) {
  const url = req.nextUrl.searchParams.get('url');
  if (!url) {
    return NextResponse.json({ error: 'Missing url param' }, { status: 400 });
  }

  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return NextResponse.json({ error: 'Invalid URL' }, { status: 400 });
  }

  if (parsed.hostname !== ALLOWED_HOST) {
    return NextResponse.json({ error: 'URL not allowed' }, { status: 403 });
  }

  const r2Res = await fetch(url);
  if (!r2Res.ok) {
    return NextResponse.json({ error: 'R2 fetch failed', status: r2Res.status }, { status: 502 });
  }

  const bytes = await r2Res.arrayBuffer();
  return new NextResponse(bytes, {
    status: 200,
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Length': bytes.byteLength.toString(),
      'Cache-Control': 'private, max-age=3600',
    },
  });
}
