/**
 * TNCB Voice Agent - Embeddable Widget SDK
 * 
 * Usage:
 *   TNCBAgent.init({
 *     apiKey: 'your-api-key',
 *     position: 'bottom-right',
 *     theme: 'auto'
 *   });
 */

(function(window, document) {
  'use strict';

  // SDK Version
  const VERSION = '1.0.0';

  // Default configuration
  const DEFAULTS = {
    position: 'bottom-right',
    theme: 'auto',
    size: 'medium',
    buttonText: 'Chat with us',
    buttonIcon: null,
    zIndex: 999999,
    baseUrl: window.location.origin
  };

  // Size configurations
  const SIZES = {
    small: { width: 320, height: 450, buttonSize: 48 },
    medium: { width: 380, height: 550, buttonSize: 56 },
    large: { width: 440, height: 650, buttonSize: 64 }
  };

  // Position configurations
  const POSITIONS = {
    'bottom-right': { bottom: '20px', right: '20px' },
    'bottom-left': { bottom: '20px', left: '20px' },
    'top-right': { top: '20px', right: '20px' },
    'top-left': { top: '20px', left: '20px' }
  };

  // State
  let state = {
    initialized: false,
    isOpen: false,
    config: null,
    elements: {
      container: null,
      button: null,
      widget: null,
      iframe: null
    }
  };

  // Event callbacks
  let callbacks = {
    onReady: null,
    onOpen: null,
    onClose: null,
    onSessionStart: null,
    onSessionEnd: null,
    onError: null
  };

  /**
   * Initialize the widget
   * @param {Object} options - Configuration options
   */
  function init(options = {}) {
    if (state.initialized) {
      console.warn('[TNCBAgent] Already initialized');
      return;
    }

    if (!options.apiKey) {
      console.error('[TNCBAgent] API key is required');
      trigger('error', { message: 'API key is required' });
      return;
    }

    // Merge configuration
    state.config = {
      ...DEFAULTS,
      ...options
    };

    // Validate position
    if (!POSITIONS[state.config.position]) {
      state.config.position = 'bottom-right';
    }

    // Validate size
    if (!SIZES[state.config.size]) {
      state.config.size = 'medium';
    }

    // Create widget elements
    createWidget();

    // Set up message listener for iframe communication
    window.addEventListener('message', handleMessage);

    state.initialized = true;
    trigger('ready', { version: VERSION });

    console.log('[TNCBAgent] Initialized', VERSION);
  }

  /**
   * Create the widget DOM elements
   */
  function createWidget() {
    const config = state.config;
    const sizeConfig = SIZES[config.size];
    const posConfig = POSITIONS[config.position];

    // Create container
    const container = document.createElement('div');
    container.id = 'tncb-agent-container';
    container.style.cssText = `
      position: fixed;
      z-index: ${config.zIndex};
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      ${Object.entries(posConfig).map(([k, v]) => `${k}: ${v}`).join('; ')};
    `;

    // Create toggle button
    const button = document.createElement('button');
    button.id = 'tncb-agent-button';
    button.setAttribute('aria-label', config.buttonText);
    button.style.cssText = `
      width: ${sizeConfig.buttonSize}px;
      height: ${sizeConfig.buttonSize}px;
      border-radius: 50%;
      border: none;
      background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
      color: white;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      transition: transform 0.2s, box-shadow 0.2s;
      outline: none;
    `;
    
    // Button hover effects
    button.onmouseenter = () => {
      button.style.transform = 'scale(1.05)';
      button.style.boxShadow = '0 6px 16px rgba(0, 0, 0, 0.2)';
    };
    button.onmouseleave = () => {
      button.style.transform = 'scale(1)';
      button.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
    };

    // Button icon (microphone)
    button.innerHTML = `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
        <line x1="12" x2="12" y1="19" y2="22"></line>
      </svg>
    `;
    button.onclick = toggle;

    // Create widget container (initially hidden)
    const widget = document.createElement('div');
    widget.id = 'tncb-agent-widget';
    widget.style.cssText = `
      position: absolute;
      width: ${sizeConfig.width}px;
      height: ${sizeConfig.height}px;
      background: white;
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
      overflow: hidden;
      display: none;
      flex-direction: column;
      ${config.position.includes('bottom') ? 'bottom' : 'top'}: ${sizeConfig.buttonSize + 12}px;
      ${config.position.includes('right') ? 'right' : 'left'}: 0;
    `;

    // Create close button
    const closeButton = document.createElement('button');
    closeButton.id = 'tncb-agent-close';
    closeButton.setAttribute('aria-label', 'Close');
    closeButton.style.cssText = `
      position: absolute;
      top: 8px;
      right: 8px;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      border: none;
      background: rgba(0, 0, 0, 0.05);
      color: #666;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10;
      transition: background 0.2s;
    `;
    closeButton.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    `;
    closeButton.onclick = close;
    closeButton.onmouseenter = () => closeButton.style.background = 'rgba(0, 0, 0, 0.1)';
    closeButton.onmouseleave = () => closeButton.style.background = 'rgba(0, 0, 0, 0.05)';

    // Create iframe
    const iframe = document.createElement('iframe');
    iframe.id = 'tncb-agent-iframe';
    iframe.style.cssText = `
      width: 100%;
      height: 100%;
      border: none;
    `;
    iframe.allow = 'microphone; autoplay';
    
    // Build iframe URL with config
    const iframeUrl = new URL(`${config.baseUrl}/embed/widget`);
    iframeUrl.searchParams.set('key', config.apiKey);
    if (config.theme !== 'auto') {
      iframeUrl.searchParams.set('theme', config.theme);
    }
    iframe.src = iframeUrl.toString();

    // Assemble widget
    widget.appendChild(closeButton);
    widget.appendChild(iframe);
    container.appendChild(widget);
    container.appendChild(button);

    // Store references
    state.elements = { container, button, widget, iframe };

    // Add to DOM
    document.body.appendChild(container);

    // Apply theme
    applyTheme();
  }

  /**
   * Apply theme based on configuration or system preference
   */
  function applyTheme() {
    const config = state.config;
    const widget = state.elements.widget;
    
    let isDark = false;
    
    if (config.theme === 'dark') {
      isDark = true;
    } else if (config.theme === 'light') {
      isDark = false;
    } else {
      // Auto - check system preference
      isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    }

    if (isDark) {
      widget.style.background = '#1f1f1f';
      widget.style.color = '#fff';
    } else {
      widget.style.background = '#fff';
      widget.style.color = '#000';
    }
  }

  /**
   * Toggle widget open/close
   */
  function toggle() {
    if (state.isOpen) {
      close();
    } else {
      open();
    }
  }

  /**
   * Open the widget
   */
  function open() {
    if (!state.initialized || state.isOpen) return;

    const { widget, button } = state.elements;
    widget.style.display = 'flex';
    button.innerHTML = `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    `;
    
    state.isOpen = true;
    trigger('open');
  }

  /**
   * Close the widget
   */
  function close() {
    if (!state.initialized || !state.isOpen) return;

    const { widget, button } = state.elements;
    widget.style.display = 'none';
    button.innerHTML = `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
        <line x1="12" x2="12" y1="19" y2="22"></line>
      </svg>
    `;
    
    state.isOpen = false;
    trigger('close');
  }

  /**
   * Destroy the widget
   */
  function destroy() {
    if (!state.initialized) return;

    window.removeEventListener('message', handleMessage);
    
    if (state.elements.container) {
      state.elements.container.remove();
    }

    state = {
      initialized: false,
      isOpen: false,
      config: null,
      elements: {
        container: null,
        button: null,
        widget: null,
        iframe: null
      }
    };

    callbacks = {
      onReady: null,
      onOpen: null,
      onClose: null,
      onSessionStart: null,
      onSessionEnd: null,
      onError: null
    };

    console.log('[TNCBAgent] Destroyed');
  }

  /**
   * Handle messages from iframe
   */
  function handleMessage(event) {
    if (!state.initialized) return;
    
    const data = event.data;
    if (!data || !data.type || !data.type.startsWith('tncb:')) return;

    const eventType = data.type.replace('tncb:', '');

    switch (eventType) {
      case 'session_start':
        trigger('sessionStart', data);
        break;
      case 'session_end':
        trigger('sessionEnd', data);
        break;
      case 'error':
        trigger('error', data);
        break;
    }
  }

  /**
   * Register event callback
   */
  function on(event, callback) {
    const key = `on${event.charAt(0).toUpperCase() + event.slice(1)}`;
    if (key in callbacks) {
      callbacks[key] = callback;
    }
  }

  /**
   * Remove event callback
   */
  function off(event) {
    const key = `on${event.charAt(0).toUpperCase() + event.slice(1)}`;
    if (key in callbacks) {
      callbacks[key] = null;
    }
  }

  /**
   * Trigger event callback
   */
  function trigger(event, data = {}) {
    const key = `on${event.charAt(0).toUpperCase() + event.slice(1)}`;
    if (callbacks[key] && typeof callbacks[key] === 'function') {
      callbacks[key](data);
    }
  }

  /**
   * Update widget position
   */
  function setPosition(position) {
    if (!state.initialized) return;
    if (!POSITIONS[position]) return;

    state.config.position = position;
    const { container, widget } = state.elements;
    const posConfig = POSITIONS[position];
    const sizeConfig = SIZES[state.config.size];

    // Reset all positions
    container.style.top = '';
    container.style.bottom = '';
    container.style.left = '';
    container.style.right = '';

    // Apply new position
    Object.entries(posConfig).forEach(([k, v]) => {
      container.style[k] = v;
    });

    // Update widget position
    widget.style.top = '';
    widget.style.bottom = '';
    widget.style[position.includes('bottom') ? 'bottom' : 'top'] = `${sizeConfig.buttonSize + 12}px`;
    widget.style[position.includes('right') ? 'right' : 'left'] = '0';
  }

  /**
   * Show the widget button
   */
  function show() {
    if (state.elements.container) {
      state.elements.container.style.display = 'block';
    }
  }

  /**
   * Hide the widget button
   */
  function hide() {
    if (state.elements.container) {
      state.elements.container.style.display = 'none';
    }
    if (state.isOpen) {
      close();
    }
  }

  // Public API
  window.TNCBAgent = {
    version: VERSION,
    init,
    open,
    close,
    toggle,
    destroy,
    on,
    off,
    setPosition,
    show,
    hide,
    isOpen: () => state.isOpen,
    isInitialized: () => state.initialized
  };

})(window, document);
