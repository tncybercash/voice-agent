'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { useSessionContext, useSessionMessages } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { ChatTranscript } from '@/components/app/chat-transcript';
import { PreConnectMessage } from '@/components/app/preconnect-message';
import { TileLayout } from '@/components/app/tile-layout';
import {
  AgentControlBar,
  type ControlBarControls,
} from '@/components/livekit/agent-control-bar/agent-control-bar';
import { cn } from '@/lib/utils';
import { ScrollArea } from '../livekit/scroll-area/scroll-area';

const MotionBottom = motion.create('div');

const BOTTOM_VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
      translateY: '0%',
    },
    hidden: {
      opacity: 0,
      translateY: '100%',
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.3,
    delay: 0.5,
    ease: 'easeOut',
  },
};

interface FadeProps {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

export function Fade({ top = false, bottom = false, className }: FadeProps) {
  return (
    <div
      className={cn(
        'from-background pointer-events-none h-4 bg-linear-to-b to-transparent',
        top && 'bg-linear-to-b',
        bottom && 'bg-linear-to-t',
        className
      )}
    />
  );
}

interface SessionViewProps {
  appConfig: AppConfig;
}

export const SessionView = ({
  appConfig,
  ...props
}: React.ComponentProps<'section'> & SessionViewProps) => {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const [chatOpen, setChatOpen] = useState(true); // Always start with chat open
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const controls: ControlBarControls = {
    leave: true,
    microphone: true,
    chat: appConfig.supportsChatInput,
    camera: appConfig.supportsVideoInput,
    screenShare: appConfig.supportsVideoInput,
  };

  useEffect(() => {
    const lastMessage = messages.at(-1);
    const lastMessageIsLocal = lastMessage?.from?.isLocal === true;

    if (scrollAreaRef.current && lastMessageIsLocal) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <section className="bg-background relative z-10 h-full w-full overflow-hidden" {...props}>
      {/* Main Layout - Flex container */}
      <div className="flex h-full">
        {/* Left side - AI Circle and controls */}
        <div className="flex-1 relative">
          {/* Tile Layout with pulsating circle */}
          <TileLayout chatOpen={chatOpen} />
        </div>

        {/* Right side - Always visible conversation panel */}
        <div className="w-[350px] md:w-[400px] lg:w-[450px] fixed right-0 top-0 bottom-0 flex flex-col border-l border-gold/30 bg-card/50 backdrop-blur-sm">
          {/* Conversation Header */}
          <div className="px-4 py-3 border-b border-gold/30 bg-card/80">
            <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-gold animate-pulse" />
              Conversation
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {messages.length} message{messages.length !== 1 ? 's' : ''}
            </p>
          </div>

          {/* Chat Messages */}
          <ScrollArea 
            ref={scrollAreaRef} 
            className="flex-1 px-4 pt-4 pb-[120px]"
          >
            <ChatTranscript
              hidden={false}
              messages={messages}
              className="space-y-3"
            />
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center py-8">
                <div className="w-12 h-12 rounded-full bg-gold/20 flex items-center justify-center mb-3">
                  <span className="text-gold text-lg">💬</span>
                </div>
                <p className="text-muted-foreground text-sm">
                  Start speaking to begin the conversation
                </p>
              </div>
            )}
          </ScrollArea>
        </div>
      </div>

      {/* Bottom Control Bar */}
      <MotionBottom
        {...BOTTOM_VIEW_MOTION_PROPS}
        className="fixed bottom-0 left-0 right-[350px] md:right-[400px] lg:right-[450px] z-50 flex flex-col items-center justify-center px-6 md:px-12"
      >
        {appConfig.isPreConnectBufferEnabled && (
          <PreConnectMessage messages={messages} className="pb-4" />
        )}
        <div className="bg-transparent pb-3 md:pb-6 w-full max-w-2xl">
          <AgentControlBar
            controls={controls}
            isConnected={session.isConnected}
            onDisconnect={session.end}
            onChatOpenChange={setChatOpen}
          />
        </div>
      </MotionBottom>
    </section>
  );
};
