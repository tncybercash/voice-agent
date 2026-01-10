import { NextRequest, NextResponse } from 'next/server';

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const includeInactive = searchParams.get('include_inactive') || 'false';

    const response = await fetch(
      `${AGENT_API_URL}/api/embed-keys?include_inactive=${includeInactive}`,
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching embed keys:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to fetch embed keys' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const response = await fetch(`${AGENT_API_URL}/api/embed-keys`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error creating embed key:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to create embed key' },
      { status: 500 }
    );
  }
}
