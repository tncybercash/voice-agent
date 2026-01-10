/// Configuration for the voice agent
class AgentConfig {
  /// Custom greeting message
  final String? greeting;
  
  /// Logo URL for branding
  final String? logoUrl;
  
  /// Accent color (hex string)
  final String? accentColor;
  
  /// Company name for branding
  final String? companyName;
  
  /// Widget position
  final WidgetPosition position;
  
  /// Widget theme
  final WidgetTheme theme;
  
  /// Widget size
  final WidgetSize size;
  
  /// Button text
  final String buttonText;

  AgentConfig({
    this.greeting,
    this.logoUrl,
    this.accentColor,
    this.companyName,
    this.position = WidgetPosition.bottomRight,
    this.theme = WidgetTheme.auto,
    this.size = WidgetSize.medium,
    this.buttonText = 'Chat with us',
  });

  factory AgentConfig.fromJson(Map<String, dynamic> json) {
    final branding = json['branding'] as Map<String, dynamic>? ?? {};
    final widget = json['widget'] as Map<String, dynamic>? ?? {};
    
    return AgentConfig(
      greeting: json['greeting'] as String?,
      logoUrl: branding['logo_url'] as String?,
      accentColor: branding['accent_color'] as String?,
      companyName: branding['company_name'] as String?,
      position: WidgetPosition.fromString(widget['position'] as String? ?? 'bottom-right'),
      theme: WidgetTheme.fromString(widget['theme'] as String? ?? 'auto'),
      size: WidgetSize.fromString(widget['size'] as String? ?? 'medium'),
      buttonText: widget['button_text'] as String? ?? 'Chat with us',
    );
  }

  Map<String, dynamic> toJson() => {
    'greeting': greeting,
    'branding': {
      'logo_url': logoUrl,
      'accent_color': accentColor,
      'company_name': companyName,
    },
    'widget': {
      'position': position.value,
      'theme': theme.value,
      'size': size.value,
      'button_text': buttonText,
    },
  };
}

/// Widget position options
enum WidgetPosition {
  bottomRight('bottom-right'),
  bottomLeft('bottom-left'),
  topRight('top-right'),
  topLeft('top-left');

  final String value;
  const WidgetPosition(this.value);

  static WidgetPosition fromString(String value) {
    return WidgetPosition.values.firstWhere(
      (e) => e.value == value,
      orElse: () => WidgetPosition.bottomRight,
    );
  }
}

/// Widget theme options
enum WidgetTheme {
  auto('auto'),
  light('light'),
  dark('dark');

  final String value;
  const WidgetTheme(this.value);

  static WidgetTheme fromString(String value) {
    return WidgetTheme.values.firstWhere(
      (e) => e.value == value,
      orElse: () => WidgetTheme.auto,
    );
  }
}

/// Widget size options
enum WidgetSize {
  small('small'),
  medium('medium'),
  large('large');

  final String value;
  const WidgetSize(this.value);

  static WidgetSize fromString(String value) {
    return WidgetSize.values.firstWhere(
      (e) => e.value == value,
      orElse: () => WidgetSize.medium,
    );
  }
}
