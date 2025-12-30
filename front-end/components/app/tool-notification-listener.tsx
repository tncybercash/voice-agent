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
    if (!room) {
      console.log('[ToolNotificationListener] No room available yet');
      return;
    }

    console.log('[ToolNotificationListener] Setting up data listener');

    const handleDataReceived = (
      payload: Uint8Array,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      participant?: Participant
    ) => {
      try {
        const text = new TextDecoder().decode(payload);
        console.log('[ToolNotificationListener] Received data:', text);
        
        const data = JSON.parse(text) as ToolNotification;
        console.log('[ToolNotificationListener] Parsed data:', data);

        if (data.type === 'notification') {
          console.log('[ToolNotificationListener] Processing notification event:', data.event);
          
          switch (data.event) {
            case 'tool_started':
              console.log('[ToolNotificationListener] Showing info toast');
              toast.info(data.data.message, {
                description: data.data.query || undefined,
                duration: 3000,
              });
              break;

            case 'tool_success':
              console.log('[ToolNotificationListener] Showing success toast');
              toast.success(data.data.message, {
                description: data.data.query || `${data.data.tool} completed`,
                duration: 4000,
              });
              break;

            case 'tool_error':
              console.log('[ToolNotificationListener] Showing error toast');
              toast.error(data.data.message, {
                description: data.data.error || 'An error occurred',
                duration: 5000,
              });
              break;
              
            default:
              console.log('[ToolNotificationListener] Unknown event type:', data.event);
          }
        } else {
          console.log('[ToolNotificationListener] Not a notification type:', data.type);
        }
      } catch (error) {
        console.error('[ToolNotificationListener] Failed to parse notification:', error);
      }
    };

    room.on('dataReceived', handleDataReceived);
    console.log('[ToolNotificationListener] Listener attached to room');

    return () => {
      console.log('[ToolNotificationListener] Cleaning up listener');
      room.off('dataReceived', handleDataReceived);
    };
  }, [room]);

  return null;
}
