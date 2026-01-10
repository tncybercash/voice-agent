import { NextRequest, NextResponse } from 'next/server';

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const response = await fetch(`${AGENT_API_URL}/api/embed/validate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error validating embed key:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to validate embed key' },
      { status: 500 }
    );
  }
}
