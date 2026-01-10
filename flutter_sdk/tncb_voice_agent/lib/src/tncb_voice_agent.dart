import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import 'models/agent_config.dart';

/// Main class for TNCB Voice Agent SDK
/// 
/// Initialize the SDK before using any widgets:
/// ```dart
/// await TNCBVoiceAgent.init(
///   apiKey: 'your-api-key',
///   serverUrl: 'https://your-server.com',
/// );
/// ```
class TNCBVoiceAgent {
  static TNCBVoiceAgent? _instance;
  static TNCBVoiceAgent get instance {
    if (_instance == null) {
      throw Exception('TNCBVoiceAgent not initialized. Call TNCBVoiceAgent.init() first.');
    }
    return _instance!;
  }

  final String apiKey;
  final String serverUrl;
  final AgentConfig? config;
  
  String? _visitorId;
  String? _embedSessionId;
  AgentConfig? _remoteConfig;

  TNCBVoiceAgent._({
    required this.apiKey,
    required this.serverUrl,
    this.config,
  });

  /// Initialize the SDK
  /// 
  /// [apiKey] - Your embed API key
  /// [serverUrl] - The voice agent server URL
  /// [config] - Optional configuration overrides
  static Future<TNCBVoiceAgent> init({
    required String apiKey,
    required String serverUrl,
    AgentConfig? config,
  }) async {
    _instance = TNCBVoiceAgent._(
      apiKey: apiKey,
      serverUrl: serverUrl,
      config: config,
    );
    
    await _instance!._initialize();
    return _instance!;
  }

  /// Check if SDK is initialized
  static bool get isInitialized => _instance != null;

  /// Get visitor ID (persistent across sessions)
  String get visitorId => _visitorId ?? '';

  /// Get current embed session ID
  String? get embedSessionId => _embedSessionId;

  /// Get remote configuration from server
  AgentConfig? get remoteConfig => _remoteConfig;

  /// Get effective configuration (local overrides remote)
  AgentConfig get effectiveConfig {
    if (config != null) return config!;
    if (_remoteConfig != null) return _remoteConfig!;
    return AgentConfig();
  }

  Future<void> _initialize() async {
    // Load or generate visitor ID
    final prefs = await SharedPreferences.getInstance();
    _visitorId = prefs.getString('tncb_visitor_id');
    if (_visitorId == null) {
      _visitorId = const Uuid().v4();
      await prefs.setString('tncb_visitor_id', _visitorId!);
    }

    // Fetch remote configuration
    await _fetchRemoteConfig();
  }

  Future<void> _fetchRemoteConfig() async {
    try {
      final response = await http.get(
        Uri.parse('$serverUrl/api/embed/config'),
        headers: {'X-API-Key': apiKey},
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['success'] == true && data['data'] != null) {
          _remoteConfig = AgentConfig.fromJson(data['data']);
        }
      }
    } catch (e) {
      print('[TNCBVoiceAgent] Failed to fetch remote config: $e');
    }
  }

  /// Create a new embed session
  Future<String?> createSession({Map<String, dynamic>? metadata}) async {
    try {
      final response = await http.post(
        Uri.parse('$serverUrl/api/embed/session'),
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
        },
        body: json.encode({
          'visitor_id': _visitorId,
          'metadata': metadata,
        }),
      );

      if (response.statusCode == 201) {
        final data = json.decode(response.body);
        if (data['success'] == true && data['data'] != null) {
          _embedSessionId = data['data']['embed_session_id'];
          return _embedSessionId;
        }
      }
    } catch (e) {
      print('[TNCBVoiceAgent] Failed to create session: $e');
    }
    return null;
  }

  /// End the current embed session
  Future<void> endSession({int? durationSeconds, int? messagesCount}) async {
    if (_embedSessionId == null) return;

    try {
      await http.post(
        Uri.parse('$serverUrl/api/embed/session/$_embedSessionId/end'),
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
        },
        body: json.encode({
          'duration_seconds': durationSeconds,
          'messages_count': messagesCount,
        }),
      );
    } catch (e) {
      print('[TNCBVoiceAgent] Failed to end session: $e');
    } finally {
      _embedSessionId = null;
    }
  }

  /// Get LiveKit connection details
  Future<Map<String, dynamic>?> getConnectionDetails() async {
    try {
      final response = await http.post(
        Uri.parse('$serverUrl/api/connection-details'),
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
          if (_embedSessionId != null) 'X-Embed-Session': _embedSessionId!,
        },
        body: json.encode({
          'embed_session_id': _embedSessionId,
        }),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
    } catch (e) {
      print('[TNCBVoiceAgent] Failed to get connection details: $e');
    }
    return null;
  }

  /// Dispose the SDK instance
  static void dispose() {
    _instance = null;
  }
}
