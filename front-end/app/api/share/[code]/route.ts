import { NextRequest, NextResponse } from 'next/server';

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://localhost:8000';

export async function GET(request: NextRequest, { params }: { params: Promise<{ code: string }> }) {
  try {
    const { code } = await params;
    const response = await fetch(`${AGENT_API_URL}/api/share/${code}`, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error fetching share config:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to fetch share config' },
      { status: 500 }
    );
  }
}
