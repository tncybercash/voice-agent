'use client';

import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
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
const MotionPanel = motion.create('div');

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

const PANEL_MOTION_PROPS = {
  variants: {
    open: {
      translateY: '0%',
    },
    closed: {
      translateY: '100%',
    },
  },
  initial: 'closed',
  animate: 'open',
  exit: 'closed',
  transition: {
    type: 'spring',
    stiffness: 300,
    damping: 30,
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
  showConversation?: boolean;
  onToggleConversation?: () => void;
}

export const SessionView = ({
  appConfig,
  showConversation = true,
  onToggleConversation,
  ...props
}: React.ComponentProps<'section'> & SessionViewProps) => {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const [chatOpen, setChatOpen] = useState(true);
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

  // Calculate panel width for positioning
  const panelWidth = showConversation ? { sm: 350, md: 400, lg: 450 } : { sm: 0, md: 0, lg: 0 };

  return (
    <section className="bg-background relative z-10 h-full w-full overflow-hidden" {...props}>
      {/* Desktop Layout */}
      <div className="hidden h-full md:flex">
        {/* Left side - AI Circle and controls */}
        <div className="relative flex-1">
          <TileLayout chatOpen={chatOpen} showConversation={showConversation} />
        </div>

        {/* Right side - Desktop conversation panel */}
        <div
          className={cn(
            "border-gold/30 bg-card/50 fixed top-0 right-0 bottom-0 z-40 flex w-[350px] flex-col border-l backdrop-blur-sm transition-transform duration-300 ease-out md:w-[400px] lg:w-[450px]",
            showConversation ? "translate-x-0" : "translate-x-full"
          )}
        >
              {/* Conversation Header */}
              <div className="border-gold/30 bg-card/80 flex items-center justify-between border-b px-4 py-3">
                <div>
                  <h2 className="text-foreground flex items-center gap-2 text-sm font-semibold">
                    <span className="bg-gold h-2 w-2 animate-pulse rounded-full" />
                    Conversation
                  </h2>
                  <p className="text-muted-foreground mt-0.5 text-xs">
                    {messages.length} message{messages.length !== 1 ? 's' : ''}
                  </p>
                </div>
                {onToggleConversation && (
                  <button
                    onClick={onToggleConversation}
                    className="bg-muted hover:bg-muted/80 flex h-8 w-8 items-center justify-center rounded-full transition-colors"
                    aria-label="Hide conversation"
                  >
                    <span className="text-muted-foreground text-lg">×</span>
                  </button>
                )}
              </div>

              {/* Chat Messages */}
              <ScrollArea ref={scrollAreaRef} className="flex-1 px-4 pt-4 pb-[120px]">
                <ChatTranscript hidden={false} messages={messages} className="space-y-3" />
                {messages.length === 0 && (
                  <div className="h-full flex-col items-center justify-center py-8 text-center">
                    <div className="bg-gold/20 mb-3 flex h-12 w-12 items-center justify-center rounded-full">
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

      {/* Mobile Layout */}
      <div className="flex h-full flex-col md:hidden">
        {/* AI Circle - Takes most of the space */}
        <div className="relative flex-1">
          <TileLayout chatOpen={false} />
        </div>

        {/* Mobile Chat Preview / Collapsed State */}
        <AnimatePresence>
          {!showConversation && messages.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="bg-card/90 border-gold/30 absolute right-4 bottom-28 left-4 rounded-xl border p-3 shadow-lg backdrop-blur-sm"
              onClick={onToggleConversation}
            >
              <div className="flex items-start gap-3">
                <div className="bg-gold/20 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full">
                  <span className="text-gold text-sm">🤖</span>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-foreground text-sm font-medium">Latest message</p>
                  <p className="text-muted-foreground mt-0.5 truncate text-xs">
                    {messages.at(-1)?.message?.content ?? 'Tap to view conversation'}
                  </p>
                </div>
                <div className="bg-gold/20 text-gold flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-medium">
                  {messages.length}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Mobile Expanded Chat Panel */}
        <AnimatePresence>
          {showConversation && (
            <>
              {/* Backdrop */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
                onClick={onToggleConversation}
              />

              {/* Chat Panel */}
              <MotionPanel
                {...PANEL_MOTION_PROPS}
                className="bg-card border-gold/30 fixed right-0 bottom-0 left-0 z-50 flex h-[70vh] flex-col rounded-t-2xl border-t shadow-2xl"
              >
                {/* Handle bar */}
                <div className="flex justify-center py-2">
                  <div
                    className="bg-muted-foreground/30 h-1 w-10 cursor-pointer rounded-full"
                    onClick={onToggleConversation}
                  />
                </div>

                {/* Header */}
                <div className="border-gold/30 flex items-center justify-between border-b px-4 pb-3">
                  <div>
                    <h2 className="text-foreground flex items-center gap-2 text-sm font-semibold">
                      <span className="bg-gold h-2 w-2 animate-pulse rounded-full" />
                      Conversation
                    </h2>
                    <p className="text-muted-foreground mt-0.5 text-xs">
                      {messages.length} message{messages.length !== 1 ? 's' : ''}
                    </p>
                  </div>
                  <button
                    onClick={onToggleConversation}
                    className="bg-muted hover:bg-muted/80 flex h-8 w-8 items-center justify-center rounded-full transition-colors"
                  >
                    <span className="text-muted-foreground text-lg">×</span>
                  </button>
                </div>

                {/* Messages */}
                <ScrollArea ref={scrollAreaRef} className="flex-1 px-4 py-4">
                  <ChatTranscript hidden={false} messages={messages} className="space-y-3" />
                  {messages.length === 0 && (
                    <div className="flex h-full flex-col items-center justify-center py-8 text-center">
                      <div className="bg-gold/20 mb-3 flex h-12 w-12 items-center justify-center rounded-full">
                        <span className="text-gold text-lg">💬</span>
                      </div>
                      <p className="text-muted-foreground text-sm">
                        Start speaking to begin the conversation
                      </p>
                    </div>
                  )}
                </ScrollArea>
              </MotionPanel>
            </>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom Control Bar - Desktop */}
      <MotionBottom
        {...BOTTOM_VIEW_MOTION_PROPS}
        className={cn(
          'fixed bottom-0 left-0 z-50 hidden flex-col items-center justify-center px-6 md:flex md:px-12',
          showConversation ? 'right-[350px] md:right-[400px] lg:right-[450px]' : 'right-0'
        )}
      >
        {appConfig.isPreConnectBufferEnabled && (
          <PreConnectMessage messages={messages} className="pb-4" />
        )}
        <div className="w-full max-w-2xl bg-transparent pb-3 md:pb-6">
          <AgentControlBar
            controls={controls}
            isConnected={session.isConnected}
            onDisconnect={session.end}
            onChatOpenChange={setChatOpen}
          />
        </div>
      </MotionBottom>

      {/* Bottom Control Bar - Mobile */}
      <MotionBottom
        {...BOTTOM_VIEW_MOTION_PROPS}
        className="pb-safe fixed right-0 bottom-0 left-0 z-[60] flex flex-col items-center justify-center px-4 md:hidden"
      >
        {appConfig.isPreConnectBufferEnabled && (
          <PreConnectMessage messages={messages} className="pb-2" />
        )}
        <div className="w-full max-w-md bg-transparent pb-4">
          <AgentControlBar
            controls={controls}
            isConnected={session.isConnected}
            onDisconnect={session.end}
          />
        </div>
      </MotionBottom>
    </section>
  );
};
