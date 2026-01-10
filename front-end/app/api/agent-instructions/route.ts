import { NextRequest, NextResponse } from 'next/server';

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const response = await fetch(`${AGENT_API_URL}/api/agent-instructions`, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching agent instructions:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to fetch agent instructions' },
      { status: 500 }
    );
  }
}
