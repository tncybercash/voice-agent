import React, { useMemo } from 'react';
import { Track } from 'livekit-client';
import { AnimatePresence, motion } from 'motion/react';
import {
  type TrackReference,
  VideoTrack,
  useLocalParticipant,
  useTracks,
  useVoiceAssistant,
} from '@livekit/components-react';
import { cn } from '@/lib/utils';

const MotionContainer = motion.create('div');

const ANIMATION_TRANSITION = {
  type: 'spring',
  stiffness: 675,
  damping: 75,
  mass: 1,
};

export function useLocalTrackRef(source: Track.Source) {
  const { localParticipant } = useLocalParticipant();
  const publication = localParticipant.getTrackPublication(source);
  const trackRef = useMemo<TrackReference | undefined>(
    () => (publication ? { source, participant: localParticipant, publication } : undefined),
    [source, publication, localParticipant]
  );
  return trackRef;
}

interface TileLayoutProps {
  chatOpen: boolean;
}

export function TileLayout({ chatOpen }: TileLayoutProps) {
  const { state: agentState, videoTrack: agentVideoTrack } = useVoiceAssistant();
  const [screenShareTrack] = useTracks([Track.Source.ScreenShare]);
  const cameraTrack: TrackReference | undefined = useLocalTrackRef(Track.Source.Camera);

  const isCameraEnabled = cameraTrack && !cameraTrack.publication.isMuted;
  const isScreenShareEnabled = screenShareTrack && !screenShareTrack.publication.isMuted;
  const hasSecondTile = isCameraEnabled || isScreenShareEnabled;

  const animationDelay = chatOpen ? 0 : 0.15;
  const isAvatar = agentVideoTrack !== undefined;
  const videoWidth = agentVideoTrack?.publication.dimensions?.width ?? 0;
  const videoHeight = agentVideoTrack?.publication.dimensions?.height ?? 0;

  // Determine if AI is speaking based on agent state
  const isSpeaking = agentState === 'speaking';
  const isListening = agentState === 'listening';
  const isThinking = agentState === 'thinking';

  return (
    <div className="pointer-events-none fixed inset-0 z-40">
      {/* Video Feed - Top Left */}
      {hasSecondTile && (
        <div className="fixed top-20 left-4 z-50 md:top-24 md:left-6">
          <AnimatePresence>
            {((cameraTrack && isCameraEnabled) || (screenShareTrack && isScreenShareEnabled)) && (
              <MotionContainer
                key="camera"
                layout="position"
                layoutId="camera"
                initial={{
                  opacity: 0,
                  scale: 0,
                }}
                animate={{
                  opacity: 1,
                  scale: 1,
                }}
                exit={{
                  opacity: 0,
                  scale: 0,
                }}
                transition={{
                  ...ANIMATION_TRANSITION,
                  delay: animationDelay,
                }}
                className="border-gold/30 overflow-hidden rounded-xl border-2 drop-shadow-xl"
              >
                <VideoTrack
                  trackRef={cameraTrack || screenShareTrack}
                  width={(cameraTrack || screenShareTrack)?.publication.dimensions?.width ?? 0}
                  height={(cameraTrack || screenShareTrack)?.publication.dimensions?.height ?? 0}
                  className="aspect-video w-[180px] rounded-xl object-cover md:w-[240px]"
                />
              </MotionContainer>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Agent Avatar - Top Left (when enabled) */}
      {isAvatar && (
        <div className="fixed top-20 left-4 z-50 md:top-24 md:left-6">
          <AnimatePresence mode="popLayout">
            <MotionContainer
              key="avatar"
              layoutId="avatar"
              initial={{
                scale: 1,
                opacity: 1,
                maskImage:
                  'radial-gradient(circle, rgba(0, 0, 0, 1) 0, rgba(0, 0, 0, 1) 20px, transparent 20px)',
                filter: 'blur(20px)',
              }}
              animate={{
                maskImage:
                  'radial-gradient(circle, rgba(0, 0, 0, 1) 0, rgba(0, 0, 0, 1) 500px, transparent 500px)',
                filter: 'blur(0px)',
                borderRadius: 12,
              }}
              transition={{
                ...ANIMATION_TRANSITION,
                delay: animationDelay,
                maskImage: {
                  duration: 1,
                },
                filter: {
                  duration: 1,
                },
              }}
              className="border-gold/30 overflow-hidden rounded-xl border-2 drop-shadow-xl"
            >
              <VideoTrack
                width={videoWidth}
                height={videoHeight}
                trackRef={agentVideoTrack}
                className="aspect-video w-[180px] object-cover md:w-[240px]"
              />
            </MotionContainer>
          </AnimatePresence>
        </div>
      )}

      {/* Pulsating Gold Circle - Centered in content area */}
      {!isAvatar && (
        <div className="pointer-events-none fixed inset-0 right-[350px] flex items-center justify-center md:right-[400px] lg:right-[450px]">
          <AnimatePresence mode="popLayout">
            <MotionContainer
              key="agent-circle"
              layoutId="agent-circle"
              initial={{
                opacity: 0,
                scale: 0,
              }}
              animate={{
                opacity: 1,
                scale: 1,
              }}
              transition={{
                ...ANIMATION_TRANSITION,
                delay: animationDelay,
              }}
              className="relative flex items-center justify-center"
            >
              {/* Outer glow rings */}
              <div
                className={cn(
                  'bg-gold/20 absolute rounded-full',
                  'h-[200px] w-[200px] md:h-[280px] md:w-[280px]',
                  isSpeaking && 'animate-gold-pulse-fast',
                  isListening && 'animate-gold-pulse',
                  isThinking && 'animate-pulse'
                )}
              />
              <div
                className={cn(
                  'bg-gold/30 absolute rounded-full',
                  'h-[160px] w-[160px] md:h-[220px] md:w-[220px]',
                  isSpeaking && 'animate-gold-pulse-fast',
                  isListening && 'animate-gold-pulse'
                )}
                style={{ animationDelay: '0.2s' }}
              />
              {/* Main circle - no icon inside */}
              <div
                className={cn(
                  'bg-gold-gradient relative rounded-full',
                  'h-[120px] w-[120px] md:h-[160px] md:w-[160px]',
                  'flex items-center justify-center',
                  'shadow-gold/40 shadow-lg',
                  'border-gold-light/50 border-2',
                  isSpeaking && 'animate-gold-pulse-fast',
                  isListening && 'animate-gold-pulse'
                )}
              />

              {/* Sound wave indicators when speaking */}
              {isSpeaking && (
                <div className="absolute inset-0 flex items-center justify-center">
                  {[...Array(3)].map((_, i) => (
                    <div
                      key={i}
                      className="border-gold/40 absolute rounded-full border-2"
                      style={{
                        width: `${180 + i * 40}px`,
                        height: `${180 + i * 40}px`,
                        animation: `gold-pulse ${1 + i * 0.3}s ease-out infinite`,
                        animationDelay: `${i * 0.2}s`,
                      }}
                    />
                  ))}
                </div>
              )}
            </MotionContainer>
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
