import 'package:flutter/material.dart';
import 'models/session_state.dart';
import 'voice_agent_widget.dart';

/// Floating Action Button for voice agent
/// 
/// A convenient way to add the voice agent to any screen
/// with a floating button that opens a modal dialog.
class TNCBVoiceAgentFAB extends StatefulWidget {
  /// Position of the FAB
  final FABPosition position;
  
  /// Custom background color for the FAB
  final Color? backgroundColor;
  
  /// Custom icon color
  final Color? iconColor;
  
  /// Size of the FAB
  final FABSize size;
  
  /// Whether to show notification badge when agent is speaking
  final bool showBadge;
  
  /// Custom icon (when not in session)
  final IconData? icon;
  
  /// Tooltip text
  final String? tooltip;
  
  /// Callback when session state changes
  final void Function(SessionState state)? onStateChange;
  
  /// Callback when session ends
  final void Function(int durationSeconds, int messageCount)? onSessionEnd;
  
  /// Callback when an error occurs
  final void Function(String error)? onError;
  
  /// Whether to use bottom sheet instead of dialog
  final bool useBottomSheet;
  
  /// Height of the bottom sheet (as fraction of screen height)
  final double bottomSheetHeightFraction;

  const TNCBVoiceAgentFAB({
    super.key,
    this.position = FABPosition.bottomRight,
    this.backgroundColor,
    this.iconColor,
    this.size = FABSize.regular,
    this.showBadge = true,
    this.icon,
    this.tooltip,
    this.onStateChange,
    this.onSessionEnd,
    this.onError,
    this.useBottomSheet = true,
    this.bottomSheetHeightFraction = 0.7,
  });

  @override
  State<TNCBVoiceAgentFAB> createState() => _TNCBVoiceAgentFABState();
}

class _TNCBVoiceAgentFABState extends State<TNCBVoiceAgentFAB>
    with SingleTickerProviderStateMixin {
  SessionState _currentState = SessionState.disconnected;
  bool _isOpen = false;
  late AnimationController _animationController;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 200),
    );
    _scaleAnimation = Tween<double>(begin: 1.0, end: 0.95).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  void _handleStateChange(SessionState state) {
    setState(() => _currentState = state);
    widget.onStateChange?.call(state);
  }

  void _openAgent() {
    setState(() => _isOpen = true);
    
    if (widget.useBottomSheet) {
      _showBottomSheet();
    } else {
      _showDialog();
    }
  }

  void _showBottomSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        height: MediaQuery.of(context).size.height * widget.bottomSheetHeightFraction,
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          child: TNCBVoiceAgentWidget(
            onStateChange: _handleStateChange,
            onError: widget.onError,
            onSessionEnd: (duration, messages) {
              widget.onSessionEnd?.call(duration, messages);
              Navigator.of(context).pop();
            },
          ),
        ),
      ),
    ).then((_) {
      setState(() => _isOpen = false);
    });
  }

  void _showDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => Dialog(
        insetPadding: const EdgeInsets.all(16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: SizedBox(
            width: double.infinity,
            height: MediaQuery.of(context).size.height * 0.6,
            child: TNCBVoiceAgentWidget(
              onStateChange: _handleStateChange,
              onError: widget.onError,
              onSessionEnd: (duration, messages) {
                widget.onSessionEnd?.call(duration, messages);
                Navigator.of(context).pop();
              },
            ),
          ),
        ),
      ),
    ).then((_) {
      setState(() => _isOpen = false);
    });
  }

  double get _fabSize {
    switch (widget.size) {
      case FABSize.small:
        return 48;
      case FABSize.regular:
        return 56;
      case FABSize.large:
        return 72;
    }
  }

  IconData get _icon {
    if (widget.icon != null && !_currentState.isActive) {
      return widget.icon!;
    }
    
    switch (_currentState) {
      case SessionState.disconnected:
        return Icons.support_agent;
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

  Color get _backgroundColor {
    if (widget.backgroundColor != null) return widget.backgroundColor!;
    
    if (_currentState.isActive) {
      switch (_currentState) {
        case SessionState.speaking:
          return Colors.green;
        case SessionState.thinking:
          return Colors.purple;
        case SessionState.error:
          return Colors.red;
        default:
          return Theme.of(context).primaryColor;
      }
    }
    
    return Theme.of(context).primaryColor;
  }

  @override
  Widget build(BuildContext context) {
    return Positioned(
      left: widget.position.isLeft ? 16 : null,
      right: widget.position.isRight ? 16 : null,
      top: widget.position.isTop ? 16 : null,
      bottom: widget.position.isBottom ? 16 : null,
      child: ScaleTransition(
        scale: _scaleAnimation,
        child: Stack(
          children: [
            // Main FAB
            GestureDetector(
              onTapDown: (_) => _animationController.forward(),
              onTapUp: (_) {
                _animationController.reverse();
                _openAgent();
              },
              onTapCancel: () => _animationController.reverse(),
              child: Tooltip(
                message: widget.tooltip ?? 'Talk to Agent',
                child: Container(
                  width: _fabSize,
                  height: _fabSize,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _backgroundColor,
                    boxShadow: [
                      BoxShadow(
                        color: _backgroundColor.withOpacity(0.3),
                        blurRadius: 12,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Icon(
                    _icon,
                    size: _fabSize * 0.45,
                    color: widget.iconColor ?? Colors.white,
                  ),
                ),
              ),
            ),
            
            // Badge indicator
            if (widget.showBadge && _currentState.isActive)
              Positioned(
                right: 0,
                top: 0,
                child: Container(
                  width: 16,
                  height: 16,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _currentState == SessionState.speaking
                        ? Colors.green
                        : Theme.of(context).primaryColor,
                    border: Border.all(
                      color: Theme.of(context).scaffoldBackgroundColor,
                      width: 2,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// FAB position options
enum FABPosition {
  topLeft,
  topRight,
  bottomLeft,
  bottomRight,
}

extension FABPositionExtension on FABPosition {
  bool get isLeft => this == FABPosition.topLeft || this == FABPosition.bottomLeft;
  bool get isRight => this == FABPosition.topRight || this == FABPosition.bottomRight;
  bool get isTop => this == FABPosition.topLeft || this == FABPosition.topRight;
  bool get isBottom => this == FABPosition.bottomLeft || this == FABPosition.bottomRight;
}

/// FAB size options
enum FABSize {
  small,
  regular,
  large,
}
