'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { TokenSource } from 'livekit-client';
import {
  RoomAudioRenderer,
  SessionProvider,
  StartAudio,
  useSession,
} from '@livekit/components-react';
import { ChatCircle, X } from '@phosphor-icons/react';
import type { AppConfig } from '@/app-config';
import { APP_CONFIG_DEFAULTS } from '@/app-config';
import { ConversationTimer } from '@/components/app/conversation-timer';
import { ThemeToggle } from '@/components/app/theme-toggle';
import { ToolNotificationListener } from '@/components/app/tool-notification-listener';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/livekit/toaster';
import { useAgentErrors } from '@/hooks/useAgentErrors';
import { useDebugMode } from '@/hooks/useDebug';

const IN_DEVELOPMENT = process.env.NODE_ENV !== 'production';

interface ShareLinkConfig {
  code: string;
  name: string;
  greeting: string | null;
  branding: {
    logo_url: string | null;
    accent_color: string | null;
    company_name: string | null;
  };
  require_auth: boolean;
}

function AppSetup() {
  useDebugMode({ enabled: IN_DEVELOPMENT });
  useAgentErrors();
  return <ToolNotificationListener />;
}

function LoadingState() {
  return (
    <div className="flex h-svh items-center justify-center">
      <div className="text-center">
        <div className="border-primary mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2"></div>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex h-svh items-center justify-center">
      <div className="max-w-md px-4 text-center">
        <div className="mb-4 text-6xl">😔</div>
        <h1 className="mb-2 text-2xl font-bold">Oops!</h1>
        <p className="text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}

function SharedAgentApp({
  shareConfig,
  appConfig,
}: {
  shareConfig: ShareLinkConfig;
  appConfig: AppConfig;
}) {
  const [showConversation, setShowConversation] = useState(true);

  // Create token source for shared agent using custom fetch
  const tokenSource = TokenSource.custom(async () => {
    const res = await fetch('/api/connection-details', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        share_code: shareConfig.code,
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

  const toggleConversation = () => setShowConversation((prev) => !prev);

  // Apply custom branding if provided
  useEffect(() => {
    if (shareConfig.branding.accent_color) {
      document.documentElement.style.setProperty('--primary', shareConfig.branding.accent_color);
    }

    // Update page title
    if (shareConfig.branding.company_name) {
      document.title = `${shareConfig.branding.company_name} - Voice Assistant`;
    } else if (shareConfig.name) {
      document.title = `${shareConfig.name} - Voice Assistant`;
    }
  }, [shareConfig]);

  return (
    <SessionProvider session={session}>
      <AppSetup />

      {/* Custom branding header with conversation toggle */}
      <div className="pointer-events-auto fixed top-4 left-4 z-[60] flex items-center gap-2 md:gap-3">
        {/* Conversation Toggle Button */}
        <button
          onClick={toggleConversation}
          type="button"
          className="bg-card/80 border-gold/30 hover:bg-card text-foreground pointer-events-auto relative flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border backdrop-blur-sm transition-colors md:h-10 md:w-10"
          aria-label={showConversation ? 'Hide conversation' : 'Show conversation'}
        >
          {showConversation ? (
            <X size={18} weight="bold" />
          ) : (
            <ChatCircle size={18} weight="bold" />
          )}
          {!showConversation && (
            <span className="bg-gold absolute -top-1 -right-1 h-2.5 w-2.5 animate-pulse rounded-full" />
          )}
        </button>

        {/* Branding */}
        {(shareConfig.branding.logo_url || shareConfig.branding.company_name) && (
          <>
            {shareConfig.branding.logo_url && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img src={shareConfig.branding.logo_url} alt="Logo" className="h-6 w-auto md:h-8" />
            )}
            {shareConfig.branding.company_name && (
              <span className="hidden text-sm font-semibold md:inline md:text-lg">
                {shareConfig.branding.company_name}
              </span>
            )}
          </>
        )}
      </div>

      {/* Conversation Timer and Theme Toggle - Centered on desktop */}
      <div className="fixed top-4 right-4 z-50 flex items-center gap-2 md:top-6 md:right-auto md:left-1/2 md:-translate-x-1/2 md:gap-3">
        <ConversationTimer />
        <ThemeToggle />
      </div>

      <main className="grid h-svh grid-cols-1 place-content-center">
        <ViewController
          appConfig={appConfig}
          showConversation={showConversation}
          onToggleConversation={toggleConversation}
        />
      </main>

      <StartAudio label="Start Audio" />
      <RoomAudioRenderer />
      <Toaster />
    </SessionProvider>
  );
}

export default function SharePage() {
  const params = useParams();
  const code = params.code as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [shareConfig, setShareConfig] = useState<ShareLinkConfig | null>(null);
  const [appConfig, setAppConfig] = useState<AppConfig>(APP_CONFIG_DEFAULTS);

  useEffect(() => {
    async function loadShareLink() {
      try {
        const response = await fetch(`/api/share/${code}`);
        const data = await response.json();

        if (!response.ok || !data.success) {
          setError(data.error || 'Failed to load share link');
          setLoading(false);
          return;
        }

        setShareConfig(data.data);

        // Update app config with share link customizations
        const updatedConfig: AppConfig = {
          ...APP_CONFIG_DEFAULTS,
          // Override with share link branding
          ...(data.data.branding.company_name && {
            title: data.data.branding.company_name,
          }),
          ...(data.data.greeting &&
            {
              // Could be used by welcome view
            }),
        };
        setAppConfig(updatedConfig);
        setLoading(false);
      } catch (err) {
        console.error('Error loading share link:', err);
        setError('Failed to connect. Please try again later.');
        setLoading(false);
      }
    }

    if (code) {
      loadShareLink();
    }
  }, [code]);

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!shareConfig) {
    return <ErrorState message="Share link not found" />;
  }

  return <SharedAgentApp shareConfig={shareConfig} appConfig={appConfig} />;
}
