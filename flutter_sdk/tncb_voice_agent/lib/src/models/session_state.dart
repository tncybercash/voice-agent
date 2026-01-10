/// State of the voice agent session
enum SessionState {
  /// Not connected
  disconnected,
  
  /// Connecting to server
  connecting,
  
  /// Connected and ready
  connected,
  
  /// Actively listening to user
  listening,
  
  /// Agent is speaking
  speaking,
  
  /// Processing user input
  thinking,
  
  /// Error state
  error,
}

/// Extension methods for SessionState
extension SessionStateExtension on SessionState {
  /// Human-readable status text
  String get statusText {
    switch (this) {
      case SessionState.disconnected:
        return 'Tap to start';
      case SessionState.connecting:
        return 'Connecting...';
      case SessionState.connected:
        return 'Ready';
      case SessionState.listening:
        return 'Listening...';
      case SessionState.speaking:
        return 'Speaking...';
      case SessionState.thinking:
        return 'Thinking...';
      case SessionState.error:
        return 'Error occurred';
    }
  }

  /// Whether the session is active
  bool get isActive {
    return this == SessionState.connected ||
           this == SessionState.listening ||
           this == SessionState.speaking ||
           this == SessionState.thinking;
  }

  /// Whether user can interact
  bool get canInteract {
    return this == SessionState.connected ||
           this == SessionState.listening;
  }
}
