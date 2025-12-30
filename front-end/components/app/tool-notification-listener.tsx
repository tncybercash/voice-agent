'use client';

import { useEffect } from 'react';
import { Participant } from 'livekit-client';
import { toast } from 'sonner';
import { useSessionContext } from '@livekit/components-react';

interface ToolNotification {
  type: 'notification';
  event: 'tool_success' | 'tool_error' | 'tool_started';
  data: {
    tool: string;
    message: string;
    error?: string;
    query?: string;
  };
}

export function ToolNotificationListener() {
  const { room } = useSessionContext();

  useEffect(() => {
    if (!room) return;

    const handleDataReceived = (
      payload: Uint8Array,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      participant?: Participant
    ) => {
      try {
        const text = new TextDecoder().decode(payload);
        const data = JSON.parse(text) as ToolNotification;

        if (data.type === 'notification') {
          switch (data.event) {
            case 'tool_started':
              toast.info(data.data.message, {
                description: data.data.query || undefined,
                duration: 3000,
              });
              break;

            case 'tool_success':
              toast.success(data.data.message, {
                description: data.data.query || `${data.data.tool} completed`,
                duration: 4000,
              });
              break;

            case 'tool_error':
              toast.error(data.data.message, {
                description: data.data.error || 'An error occurred',
                duration: 5000,
              });
              break;
          }
        }
      } catch (error) {
        console.error('Failed to parse tool notification:', error);
      }
    };

    room.on('dataReceived', handleDataReceived);

    return () => {
      room.off('dataReceived', handleDataReceived);
    };
  }, [room]);

  return null;
}
