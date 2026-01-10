import { NextRequest, NextResponse } from 'next/server';
import { AccessToken, type AccessTokenOptions, type VideoGrant } from 'livekit-server-sdk';
import { RoomConfiguration } from '@livekit/protocol';

type ConnectionDetails = {
  serverUrl: string;
  roomName: string;
  participantName: string;
  participantToken: string;
};

// NOTE: you are expected to define the following environment variables in `.env.local`:
const API_KEY = process.env.LIVEKIT_API_KEY;
const API_SECRET = process.env.LIVEKIT_API_SECRET;
const LIVEKIT_URL = process.env.LIVEKIT_URL;
const AGENT_API_URL = process.env.AGENT_API_URL || 'http://localhost:8000';

// don't cache the results
export const revalidate = 0;

/**
 * Validate share link code with the agent API
 */
async function validateShareLink(code: string): Promise<{
  valid: boolean;
  shareLink?: {
    id: number;
    name: string;
    customGreeting?: string;
    agentName?: string;
  };
  error?: string;
}> {
  try {
    const response = await fetch(`${AGENT_API_URL}/api/share/${code}`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return { valid: false, error: errorData.error || 'Invalid share link' };
    }

    const data = await response.json();
    return { valid: true, shareLink: data };
  } catch (error) {
    console.error('Error validating share link:', error);
    return { valid: false, error: 'Failed to validate share link' };
  }
}

/**
 * Validate embed API key and create/validate session
 */
async function validateEmbedAccess(
  apiKey: string,
  sessionId?: string,
  origin?: string
): Promise<{
  valid: boolean;
  session?: {
    id: string;
    agentName?: string;
  };
  error?: string;
}> {
  try {
    // If we have a session ID, validate it
    if (sessionId) {
      const response = await fetch(`${AGENT_API_URL}/api/embed/session/${sessionId}`, {
        headers: { 'X-API-Key': apiKey },
      });

      if (response.ok) {
        const data = await response.json();
        return { valid: true, session: data };
      }
    }

    // Create a new session
    const response = await fetch(`${AGENT_API_URL}/api/embed/session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: JSON.stringify({ origin: origin || 'unknown' }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return { valid: false, error: errorData.error || 'Invalid API key' };
    }

    const data = await response.json();
    return { valid: true, session: data };
  } catch (error) {
    console.error('Error validating embed access:', error);
    return { valid: false, error: 'Failed to validate embed access' };
  }
}

export async function POST(req: NextRequest) {
  try {
    if (LIVEKIT_URL === undefined) {
      throw new Error('LIVEKIT_URL is not defined');
    }
    if (API_KEY === undefined) {
      throw new Error('LIVEKIT_API_KEY is not defined');
    }
    if (API_SECRET === undefined) {
      throw new Error('LIVEKIT_API_SECRET is not defined');
    }

    // Parse agent configuration from request body
    const body = await req.json();
    let agentName: string | undefined = body?.room_config?.agents?.[0]?.agent_name;

    // Check for share link access
    const shareCode = body?.share_code;
    if (shareCode) {
      const validation = await validateShareLink(shareCode);
      if (!validation.valid) {
        return NextResponse.json(
          { error: validation.error || 'Invalid share link' },
          { status: 403 }
        );
      }
      // Use agent name from share link if specified
      if (validation.shareLink?.agentName) {
        agentName = validation.shareLink.agentName;
      }
    }

    // Check for embed access (API key in header)
    const embedApiKey = req.headers.get('X-API-Key');
    const embedSessionId = req.headers.get('X-Embed-Session');
    const origin = req.headers.get('Origin') || req.headers.get('Referer');

    if (embedApiKey) {
      const validation = await validateEmbedAccess(
        embedApiKey,
        embedSessionId || undefined,
        origin || undefined
      );
      if (!validation.valid) {
        return NextResponse.json(
          { error: validation.error || 'Invalid embed access' },
          { status: 403 }
        );
      }
      // Use agent name from embed session if specified
      if (validation.session?.agentName) {
        agentName = validation.session.agentName;
      }
    }

    // Generate participant token
    const participantName = 'user';
    const participantIdentity = `voice_assistant_user_${Math.floor(Math.random() * 10_000)}`;
    const roomName = `voice_assistant_room_${Math.floor(Math.random() * 10_000)}`;

    const participantToken = await createParticipantToken(
      { identity: participantIdentity, name: participantName },
      roomName,
      agentName
    );

    // Return connection details
    const data: ConnectionDetails = {
      serverUrl: LIVEKIT_URL,
      roomName,
      participantToken: participantToken,
      participantName,
    };
    const headers = new Headers({
      'Cache-Control': 'no-store',
    });
    return NextResponse.json(data, { headers });
  } catch (error) {
    if (error instanceof Error) {
      console.error(error);
      return new NextResponse(error.message, { status: 500 });
    }
  }
}

function createParticipantToken(
  userInfo: AccessTokenOptions,
  roomName: string,
  agentName?: string
): Promise<string> {
  const at = new AccessToken(API_KEY, API_SECRET, {
    ...userInfo,
    ttl: '15m',
  });
  const grant: VideoGrant = {
    room: roomName,
    roomJoin: true,
    canPublish: true,
    canPublishData: true,
    canSubscribe: true,
  };
  at.addGrant(grant);

  if (agentName) {
    at.roomConfig = new RoomConfiguration({
      agents: [{ agentName }],
    });
  }

  return at.toJwt();
}
