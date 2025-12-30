/**
 * Enhanced Audio Configuration for LiveKit Client
 *
 * This file provides configuration for client-side audio enhancements
 * including noise suppression, echo cancellation, and auto gain control.
 */
import { LocalAudioTrack, Room, RoomOptions } from 'livekit-client';

/**
 * Audio processing options for optimal voice quality
 */
export const ENHANCED_AUDIO_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
  // Additional constraints for better quality
  sampleRate: 48000,
  channelCount: 1, // Mono is fine for voice
};

/**
 * Room options with advanced audio processing
 */
export const ENHANCED_ROOM_OPTIONS: RoomOptions = {
  // Enable advanced audio processing
  audioCaptureDefaults: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },

  // Adaptive stream for better network handling
  adaptiveStream: true,

  // Simulcast for better quality adaptation
  dynacast: true,
};

/**
 * Standard room options without Krisp (works offline)
 */
export const STANDARD_ROOM_OPTIONS: RoomOptions = {
  audioCaptureDefaults: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },
  adaptiveStream: true,
  dynacast: true,
};

/**
 * Enable enhanced audio on an existing room
 */
export async function enableEnhancedAudio(room: Room): Promise<void> {
  const localParticipant = room.localParticipant;

  // Enable microphone with enhanced settings
  await localParticipant.setMicrophoneEnabled(true, ENHANCED_AUDIO_CONSTRAINTS);

  console.log('✅ Enhanced audio enabled with:');
  console.log('   - Echo cancellation: enabled');
  console.log('   - Noise suppression: enabled');
  console.log('   - Auto gain control: enabled');
}

/**
 * Apply audio processing to an existing track
 */
export async function applyAudioProcessing(track: LocalAudioTrack): Promise<void> {
  try {
    const mediaStreamTrack = track.mediaStreamTrack;

    if (mediaStreamTrack.getSettings) {
      const settings = mediaStreamTrack.getSettings();
      console.log('Current audio settings:', settings);
    }

    // Apply constraints
    await mediaStreamTrack.applyConstraints(ENHANCED_AUDIO_CONSTRAINTS);

    console.log('✅ Audio processing applied to track');
  } catch (error) {
    console.error('Failed to apply audio processing:', error);
  }
}

/**
 * Detect and log audio issues
 */
export function monitorAudioQuality(track: LocalAudioTrack): void {
  const mediaStreamTrack = track.mediaStreamTrack;

  // Monitor track state
  mediaStreamTrack.addEventListener('ended', () => {
    console.warn('⚠️ Audio track ended unexpectedly');
  });

  mediaStreamTrack.addEventListener('mute', () => {
    console.warn('⚠️ Audio track muted');
  });

  mediaStreamTrack.addEventListener('unmute', () => {
    console.log('✅ Audio track unmuted');
  });

  // Log current settings
  const settings = mediaStreamTrack.getSettings();
  console.log('📊 Audio track settings:', {
    sampleRate: settings.sampleRate,
    channelCount: settings.channelCount,
    echoCancellation: settings.echoCancellation,
    noiseSuppression: settings.noiseSuppression,
    autoGainControl: settings.autoGainControl,
  });
}

/**
 * Test microphone and provide feedback
 */
export async function testMicrophone(): Promise<{
  success: boolean;
  message: string;
  settings?: MediaTrackSettings;
}> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: ENHANCED_AUDIO_CONSTRAINTS,
    });

    const track = stream.getAudioTracks()[0];
    const settings = track.getSettings();

    // Stop the test track
    track.stop();

    return {
      success: true,
      message: 'Microphone test successful',
      settings,
    };
  } catch (error) {
    return {
      success: false,
      message: `Microphone test failed: ${error}`,
    };
  }
}

/**
 * Get available audio input devices
 */
export async function getAudioInputDevices(): Promise<MediaDeviceInfo[]> {
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((device) => device.kind === 'audioinput');
}

/**
 * Select best audio input device (prefer headset/external mic)
 */
export async function selectBestAudioDevice(): Promise<string | undefined> {
  const devices = await getAudioInputDevices();

  // Prefer devices with these keywords (usually better quality)
  const preferredKeywords = ['headset', 'external', 'usb', 'bluetooth'];

  const preferredDevice = devices.find((device) =>
    preferredKeywords.some((keyword) => device.label.toLowerCase().includes(keyword))
  );

  if (preferredDevice) {
    console.log('✅ Selected preferred audio device:', preferredDevice.label);
    return preferredDevice.deviceId;
  }

  // Return default device
  return devices[0]?.deviceId;
}
