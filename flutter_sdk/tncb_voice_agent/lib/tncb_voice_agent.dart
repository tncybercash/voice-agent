/// TNCB Voice Agent Flutter SDK
/// 
/// A Flutter package for embedding voice assistants in mobile applications.
/// 
/// ## Getting Started
/// 
/// ```dart
/// import 'package:tncb_voice_agent/tncb_voice_agent.dart';
/// 
/// // Initialize the SDK
/// await TNCBVoiceAgent.init(
///   apiKey: 'your-api-key',
///   serverUrl: 'https://your-server.com',
/// );
/// 
/// // Use the widget
/// TNCBVoiceAgentWidget()
/// 
/// // Or use the FAB
/// TNCBVoiceAgentFAB()
/// ```
library tncb_voice_agent;

export 'src/tncb_voice_agent.dart';
export 'src/voice_agent_widget.dart';
export 'src/voice_agent_fab.dart';
export 'src/models/agent_config.dart';
export 'src/models/session_state.dart';
