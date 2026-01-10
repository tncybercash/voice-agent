'use client';

import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { TokenSource } from 'livekit-client';
import {
  RoomAudioRenderer,
  SessionProvider,
  StartAudio,
  useSession,
} from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { APP_CONFIG_DEFAULTS } from '@/app-config';
import { ToolNotificationListener } from '@/components/app/tool-notification-listener';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/livekit/toaster';
import { useAgentErrors } from '@/hooks/useAgentErrors';

interface EmbedConfig {
  greeting: string | null;
  branding: {
    logo_url: string | null;
    accent_color: string | null;
    company_name: string | null;
  };
  widget: {
    position: string;
    theme: string;
    size: string;
    button_text: string;
    button_icon: string | null;
  };
}

function AppSetup() {
  useAgentErrors();
  return <ToolNotificationListener />;
}

function LoadingState() {
  return (
    <div className="bg-background flex h-full items-center justify-center">
      <div className="text-center">
        <div className="border-primary mx-auto h-8 w-8 animate-spin rounded-full border-b-2"></div>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="bg-background flex h-full items-center justify-center p-4">
      <div className="text-center">
        <p className="text-muted-foreground text-sm">{message}</p>
      </div>
    </div>
  );
}

function EmbedAgentWidget({
  embedConfig,
  apiKey,
  embedSessionId,
  appConfig,
}: {
  embedConfig: EmbedConfig;
  apiKey: string;
  embedSessionId: string;
  appConfig: AppConfig;
}) {
  // Track session for cleanup
  const [sessionStartTime] = useState(Date.now());

  // Create token source for embedded agent using custom fetch
  const tokenSource = TokenSource.custom(async () => {
    const res = await fetch('/api/connection-details', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
        'X-Embed-Session': embedSessionId,
      },
      body: JSON.stringify({
        embed_session_id: embedSessionId,
        room_config: appConfig.agentName
          ? { agents: [{ agent_name: appConfig.agentName }] }
          : undefined,
      }),
    });
    if (!res.ok) {
      throw new Error('Failed to get connection details');
    }
    return await res.json();
  });

  const session = useSession(
    tokenSource,
    appConfig.agentName ? { agentName: appConfig.agentName } : undefined
  );

  // Apply custom branding
  useEffect(() => {
    if (embedConfig.branding.accent_color) {
      document.documentElement.style.setProperty('--primary', embedConfig.branding.accent_color);
    }
  }, [embedConfig]);

  // Notify parent window of session events
  const postMessage = useCallback((type: string, data?: Record<string, unknown>) => {
    if (window.parent !== window) {
      window.parent.postMessage({ type, ...data }, '*');
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    postMessage('tncb:session_start');

    return () => {
      const duration = Math.floor((Date.now() - sessionStartTime) / 1000);
      postMessage('tncb:session_end', { duration });

      // End embed session
      fetch(`/api/embed/session/${embedSessionId}/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration_seconds: duration }),
      }).catch(console.error);
    };
  }, [embedSessionId, sessionStartTime, postMessage]);

  return (
    <SessionProvider session={session}>
      <AppSetup />

      <div className="flex h-full flex-col">
        {/* Compact header with branding */}
        {(embedConfig.branding.logo_url || embedConfig.branding.company_name) && (
          <div className="flex items-center gap-2 border-b p-3">
            {embedConfig.branding.logo_url && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img src={embedConfig.branding.logo_url} alt="Logo" className="h-6 w-auto" />
            )}
            {embedConfig.branding.company_name && (
              <span className="text-sm font-medium">{embedConfig.branding.company_name}</span>
            )}
          </div>
        )}

        <main className="flex-1 overflow-hidden">
          <ViewController appConfig={appConfig} />
        </main>
      </div>

      <StartAudio label="Start" />
      <RoomAudioRenderer />
      <Toaster />
    </SessionProvider>
  );
}

export default function EmbedWidgetPage() {
  const searchParams = useSearchParams();
  const apiKey = searchParams.get('key');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [embedConfig, setEmbedConfig] = useState<EmbedConfig | null>(null);
  const [embedSessionId, setEmbedSessionId] = useState<string | null>(null);
  const [appConfig, setAppConfig] = useState<AppConfig>(APP_CONFIG_DEFAULTS);

  useEffect(() => {
    async function initEmbed() {
      if (!apiKey) {
        setError('API key required');
        setLoading(false);
        return;
      }

      try {
        // Get embed configuration
        const configResponse = await fetch('/api/embed/config', {
          headers: { 'X-API-Key': apiKey },
        });
        const configData = await configResponse.json();

        if (!configResponse.ok || !configData.success) {
          setError(configData.error || 'Invalid API key');
          setLoading(false);
          return;
        }

        setEmbedConfig(configData.data);

        // Create embed session
        const sessionResponse = await fetch('/api/embed/session', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': apiKey,
          },
          body: JSON.stringify({
            visitor_id: getVisitorId(),
          }),
        });
        const sessionData = await sessionResponse.json();

        if (!sessionResponse.ok || !sessionData.success) {
          setError(sessionData.error || 'Failed to create session');
          setLoading(false);
          return;
        }

        setEmbedSessionId(sessionData.data.embed_session_id);

        // Update app config
        const updatedConfig: AppConfig = {
          ...APP_CONFIG_DEFAULTS,
          ...(configData.data.branding.company_name && {
            title: configData.data.branding.company_name,
          }),
        };
        setAppConfig(updatedConfig);
        setLoading(false);
      } catch (err) {
        console.error('Error initializing embed:', err);
        setError('Failed to initialize');
        setLoading(false);
      }
    }

    initEmbed();
  }, [apiKey]);

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!embedConfig || !embedSessionId || !apiKey) {
    return <ErrorState message="Configuration error" />;
  }

  return (
    <EmbedAgentWidget
      embedConfig={embedConfig}
      apiKey={apiKey}
      embedSessionId={embedSessionId}
      appConfig={appConfig}
    />
  );
}

// Generate or retrieve visitor ID
function getVisitorId(): string {
  const key = 'tncb_visitor_id';
  let visitorId = localStorage.getItem(key);

  if (!visitorId) {
    visitorId = `v_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem(key, visitorId);
  }

  return visitorId;
}
