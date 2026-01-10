import 'dart:async';
import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart';
import 'package:permission_handler/permission_handler.dart';
import 'tncb_voice_agent.dart';
import 'models/session_state.dart';

/// Full-screen voice agent widget
/// 
/// Provides a complete voice interaction interface with
/// connection status, audio visualization, and controls.
class TNCBVoiceAgentWidget extends StatefulWidget {
  /// Callback when session state changes
  final void Function(SessionState state)? onStateChange;
  
  /// Callback when an error occurs
  final void Function(String error)? onError;
  
  /// Callback when session ends
  final void Function(int durationSeconds, int messageCount)? onSessionEnd;
  
  /// Custom background color
  final Color? backgroundColor;
  
  /// Custom accent color (overrides config)
  final Color? accentColor;
  
  /// Whether to show the header with branding
  final bool showHeader;
  
  /// Whether to show the status text
  final bool showStatus;

  const TNCBVoiceAgentWidget({
    super.key,
    this.onStateChange,
    this.onError,
    this.onSessionEnd,
    this.backgroundColor,
    this.accentColor,
    this.showHeader = true,
    this.showStatus = true,
  });

  @override
  State<TNCBVoiceAgentWidget> createState() => _TNCBVoiceAgentWidgetState();
}

class _TNCBVoiceAgentWidgetState extends State<TNCBVoiceAgentWidget>
    with SingleTickerProviderStateMixin {
  SessionState _state = SessionState.disconnected;
  Room? _room;
  LocalParticipant? _localParticipant;
  RemoteParticipant? _agentParticipant;
  
  late AnimationController _pulseController;
  DateTime? _sessionStartTime;
  int _messageCount = 0;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _disconnect();
    super.dispose();
  }

  void _setState(SessionState state) {
    if (mounted && _state != state) {
      setState(() => _state = state);
      widget.onStateChange?.call(state);
    }
  }

  Future<void> _connect() async {
    _setState(SessionState.connecting);
    _errorMessage = null;

    try {
      // Request microphone permission
      final status = await Permission.microphone.request();
      if (!status.isGranted) {
        throw Exception('Microphone permission denied');
      }

      // Create embed session
      final sessionId = await TNCBVoiceAgent.instance.createSession();
      if (sessionId == null) {
        throw Exception('Failed to create session');
      }

      // Get connection details
      final details = await TNCBVoiceAgent.instance.getConnectionDetails();
      if (details == null) {
        throw Exception('Failed to get connection details');
      }

      // Connect to LiveKit room
      _room = Room();
      
      _room!.addListener(_RoomListener(
        onParticipantConnected: (participant) {
          if (participant.identity.startsWith('agent')) {
            setState(() => _agentParticipant = participant);
          }
        },
        onParticipantDisconnected: (participant) {
          if (participant == _agentParticipant) {
            setState(() => _agentParticipant = null);
          }
        },
        onTrackSubscribed: (track, publication, participant) {
          if (track is AudioTrack && participant == _agentParticipant) {
            _setState(SessionState.speaking);
          }
        },
        onDisconnected: (reason) {
          _handleDisconnect();
        },
      ));

      await _room!.connect(
        details['serverUrl'] as String,
        details['participantToken'] as String,
        roomOptions: const RoomOptions(
          adaptiveStream: true,
          dynacast: true,
        ),
      );

      _localParticipant = _room!.localParticipant;
      
      // Enable microphone
      await _localParticipant!.setMicrophoneEnabled(true);

      _sessionStartTime = DateTime.now();
      _setState(SessionState.connected);

    } catch (e) {
      _errorMessage = e.toString();
      _setState(SessionState.error);
      widget.onError?.call(e.toString());
    }
  }

  Future<void> _disconnect() async {
    if (_room != null) {
      final duration = _sessionStartTime != null
          ? DateTime.now().difference(_sessionStartTime!).inSeconds
          : 0;
      
      await _room!.disconnect();
      _room = null;
      
      await TNCBVoiceAgent.instance.endSession(
        durationSeconds: duration,
        messagesCount: _messageCount,
      );

      widget.onSessionEnd?.call(duration, _messageCount);
    }

    _localParticipant = null;
    _agentParticipant = null;
    _sessionStartTime = null;
    _messageCount = 0;
    
    _setState(SessionState.disconnected);
  }

  void _handleDisconnect() {
    _disconnect();
  }

  void _toggleMute() {
    if (_localParticipant != null) {
      final isMuted = _localParticipant!.isMicrophoneEnabled();
      _localParticipant!.setMicrophoneEnabled(!isMuted);
      setState(() {});
    }
  }

  Color get _accentColor {
    if (widget.accentColor != null) return widget.accentColor!;
    
    final configColor = TNCBVoiceAgent.instance.effectiveConfig.accentColor;
    if (configColor != null) {
      try {
        return Color(int.parse(configColor.replaceFirst('#', '0xFF')));
      } catch (_) {}
    }
    
    return Theme.of(context).primaryColor;
  }

  @override
  Widget build(BuildContext context) {
    final config = TNCBVoiceAgent.instance.effectiveConfig;
    
    return Container(
      color: widget.backgroundColor ?? Theme.of(context).scaffoldBackgroundColor,
      child: SafeArea(
        child: Column(
          children: [
            // Header with branding
            if (widget.showHeader)
              _buildHeader(config),
            
            // Main content
            Expanded(
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Status indicator
                    _buildStatusIndicator(),
                    
                    const SizedBox(height: 24),
                    
                    // Status text
                    if (widget.showStatus)
                      Text(
                        _errorMessage ?? _state.statusText,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          color: _state == SessionState.error
                              ? Colors.red
                              : null,
                        ),
                      ),
                    
                    const SizedBox(height: 48),
                    
                    // Action button
                    _buildActionButton(),
                  ],
                ),
              ),
            ),
            
            // Controls
            if (_state.isActive)
              _buildControls(),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(config) {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          if (config.logoUrl != null)
            Image.network(
              config.logoUrl!,
              height: 32,
              errorBuilder: (_, __, ___) => const SizedBox.shrink(),
            ),
          if (config.companyName != null) ...[
            const SizedBox(width: 12),
            Text(
              config.companyName!,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
          const Spacer(),
          if (_state.isActive)
            IconButton(
              icon: const Icon(Icons.close),
              onPressed: _disconnect,
            ),
        ],
      ),
    );
  }

  Widget _buildStatusIndicator() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        final scale = _state == SessionState.listening
            ? 1.0 + (_pulseController.value * 0.2)
            : 1.0;
        
        return Transform.scale(
          scale: scale,
          child: Container(
            width: 120,
            height: 120,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: _getIndicatorColor().withOpacity(0.2),
              border: Border.all(
                color: _getIndicatorColor(),
                width: 3,
              ),
            ),
            child: Icon(
              _getIndicatorIcon(),
              size: 48,
              color: _getIndicatorColor(),
            ),
          ),
        );
      },
    );
  }

  Color _getIndicatorColor() {
    switch (_state) {
      case SessionState.disconnected:
        return Colors.grey;
      case SessionState.connecting:
        return Colors.orange;
      case SessionState.connected:
      case SessionState.listening:
        return _accentColor;
      case SessionState.speaking:
        return Colors.green;
      case SessionState.thinking:
        return Colors.purple;
      case SessionState.error:
        return Colors.red;
    }
  }

  IconData _getIndicatorIcon() {
    switch (_state) {
      case SessionState.disconnected:
        return Icons.mic_off;
      case SessionState.connecting:
        return Icons.sync;
      case SessionState.connected:
      case SessionState.listening:
        return Icons.mic;
      case SessionState.speaking:
        return Icons.volume_up;
      case SessionState.thinking:
        return Icons.psychology;
      case SessionState.error:
        return Icons.error_outline;
    }
  }

  Widget _buildActionButton() {
    if (_state == SessionState.disconnected || _state == SessionState.error) {
      return ElevatedButton.icon(
        onPressed: _connect,
        icon: const Icon(Icons.mic),
        label: Text(_state == SessionState.error ? 'Try Again' : 'Start Conversation'),
        style: ElevatedButton.styleFrom(
          backgroundColor: _accentColor,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
        ),
      );
    }
    
    if (_state == SessionState.connecting) {
      return const CircularProgressIndicator();
    }
    
    return const SizedBox.shrink();
  }

  Widget _buildControls() {
    final isMuted = _localParticipant?.isMicrophoneEnabled() == false;
    
    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Mute button
          IconButton(
            onPressed: _toggleMute,
            icon: Icon(isMuted ? Icons.mic_off : Icons.mic),
            style: IconButton.styleFrom(
              backgroundColor: isMuted ? Colors.red : Colors.grey.shade200,
              foregroundColor: isMuted ? Colors.white : Colors.black,
            ),
          ),
          
          const SizedBox(width: 16),
          
          // End button
          ElevatedButton(
            onPressed: _disconnect,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
            ),
            child: const Text('End'),
          ),
        ],
      ),
    );
  }
}

/// Internal room event listener
class _RoomListener extends RoomListener {
  final void Function(RemoteParticipant)? onParticipantConnected;
  final void Function(RemoteParticipant)? onParticipantDisconnected;
  final void Function(Track, RemoteTrackPublication, RemoteParticipant)? onTrackSubscribed;
  final void Function(DisconnectReason?)? onDisconnected;

  _RoomListener({
    this.onParticipantConnected,
    this.onParticipantDisconnected,
    this.onTrackSubscribed,
    this.onDisconnected,
  });

  @override
  void onParticipantConnected(RemoteParticipant participant) {
    this.onParticipantConnected?.call(participant);
  }

  @override
  void onParticipantDisconnected(RemoteParticipant participant) {
    this.onParticipantDisconnected?.call(participant);
  }

  @override
  void onTrackSubscribed(
    Track track,
    RemoteTrackPublication publication,
    RemoteParticipant participant,
  ) {
    this.onTrackSubscribed?.call(track, publication, participant);
  }

  @override
  void onDisconnected(DisconnectReason? reason) {
    this.onDisconnected?.call(reason);
  }
}
