'use client';

import { useEffect, useState } from 'react';
import { useSessionContext } from '@livekit/components-react';
import { cn } from '@/lib/utils';

interface ConversationTimerProps {
  className?: string;
}

export function ConversationTimer({ className }: ConversationTimerProps) {
  const { isConnected } = useSessionContext();
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!isConnected) {
      setSeconds(0);
      return;
    }

    const interval = setInterval(() => {
      setSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(interval);
  }, [isConnected]);

  const formatTime = (totalSeconds: number): string => {
    const minutes = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  if (!isConnected) {
    return null;
  }

  return (
    <div
      className={cn(
        'border-border/50 bg-background/80 flex items-center gap-2 rounded-full border px-3 py-1.5 backdrop-blur-sm',
        className
      )}
    >
      <div className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
      <span className="text-foreground font-mono text-sm font-medium">{formatTime(seconds)}</span>
    </div>
  );
}
