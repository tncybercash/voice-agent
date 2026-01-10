'use client';

import { useCallback, useEffect, useState } from 'react';
import { ArrowsClockwise, Code, Copy, Key, Pencil, Plus, Trash } from '@phosphor-icons/react';

interface EmbedKey {
  id: string;
  key_prefix: string;
  api_key?: string; // Only present on creation
  name: string;
  description: string | null;
  branding: {
    logo_url: string | null;
    accent_color: string | null;
    company_name: string | null;
  };
  widget_config: {
    position: string;
    theme: string;
    size: string;
    button_text: string;
  };
  is_active: boolean;
  allowed_domains: string[];
  rate_limit_rpm: number;
  max_concurrent_sessions: number;
  total_sessions: number;
  total_messages: number;
  last_used_at: string | null;
  created_at: string;
}

interface CreateEmbedKeyForm {
  name: string;
  description: string;
  allowed_domains: string;
  custom_greeting: string;
  company_name: string;
  logo_url: string;
  accent_color: string;
  position: string;
  theme: string;
  size: string;
  button_text: string;
  rate_limit_rpm: string;
  max_concurrent_sessions: string;
}

const defaultForm: CreateEmbedKeyForm = {
  name: '',
  description: '',
  allowed_domains: '',
  custom_greeting: '',
  company_name: '',
  logo_url: '',
  accent_color: '#3b82f6',
  position: 'bottom-right',
  theme: 'auto',
  size: 'medium',
  button_text: 'Chat with us',
  rate_limit_rpm: '60',
  max_concurrent_sessions: '10',
};

export function EmbedKeyManager() {
  const [keys, setKeys] = useState<EmbedKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<CreateEmbedKeyForm>(defaultForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [showCode, setShowCode] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const loadKeys = useCallback(async () => {
    try {
      const response = await fetch('/api/embed-keys?include_inactive=true');
      const data = await response.json();
      if (data.success) {
        setKeys(data.data);
      }
    } catch (err) {
      console.error('Error loading embed keys:', err);
      setError('Failed to load embed keys');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    // Parse domains
    const domains = form.allowed_domains
      .split('\n')
      .map((d) => d.trim())
      .filter((d) => d.length > 0);

    if (domains.length === 0 && !editingId) {
      setError('At least one domain is required');
      setSaving(false);
      return;
    }

    try {
      const payload = {
        name: form.name,
        description: form.description || null,
        allowed_domains: domains.length > 0 ? domains : undefined,
        custom_greeting: form.custom_greeting || null,
        branding: {
          company_name: form.company_name || null,
          logo_url: form.logo_url || null,
          accent_color: form.accent_color || null,
        },
        widget_config: {
          position: form.position,
          theme: form.theme,
          size: form.size,
          button_text: form.button_text,
        },
        rate_limit_rpm: parseInt(form.rate_limit_rpm) || 60,
        max_concurrent_sessions: parseInt(form.max_concurrent_sessions) || 10,
      };

      const url = editingId ? `/api/embed-keys/${editingId}` : '/api/embed-keys';

      const response = await fetch(url, {
        method: editingId ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (data.success) {
        // If creating new key, show the API key
        if (!editingId && data.data.api_key) {
          setNewKey(data.data.api_key);
        }
        await loadKeys();
        setShowForm(false);
        setEditingId(null);
        setForm(defaultForm);
      } else {
        setError(data.error || 'Failed to save');
      }
    } catch (err) {
      console.error('Error saving:', err);
      setError('Failed to save embed key');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (key: EmbedKey) => {
    setForm({
      name: key.name,
      description: key.description || '',
      allowed_domains: key.allowed_domains.join('\n'),
      custom_greeting: '',
      company_name: key.branding.company_name || '',
      logo_url: key.branding.logo_url || '',
      accent_color: key.branding.accent_color || '#3b82f6',
      position: key.widget_config.position || 'bottom-right',
      theme: key.widget_config.theme || 'auto',
      size: key.widget_config.size || 'medium',
      button_text: key.widget_config.button_text || 'Chat with us',
      rate_limit_rpm: key.rate_limit_rpm.toString(),
      max_concurrent_sessions: key.max_concurrent_sessions.toString(),
    });
    setEditingId(key.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this API key? This cannot be undone.')) return;

    try {
      const response = await fetch(`/api/embed-keys/${id}`, {
        method: 'DELETE',
      });
      const data = await response.json();

      if (data.success) {
        await loadKeys();
      } else {
        setError(data.error || 'Failed to delete');
      }
    } catch (err) {
      console.error('Error deleting:', err);
      setError('Failed to delete embed key');
    }
  };

  const handleRegenerate = async (id: string) => {
    if (!confirm('Regenerate this API key? The old key will stop working immediately.')) return;

    try {
      const response = await fetch(`/api/embed-keys/${id}/regenerate`, {
        method: 'POST',
      });
      const data = await response.json();

      if (data.success && data.data.api_key) {
        setNewKey(data.data.api_key);
        await loadKeys();
      } else {
        setError(data.error || 'Failed to regenerate');
      }
    } catch (err) {
      console.error('Error regenerating:', err);
      setError('Failed to regenerate key');
    }
  };

  const handleToggleActive = async (key: EmbedKey) => {
    try {
      const response = await fetch(`/api/embed-keys/${key.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !key.is_active }),
      });
      const data = await response.json();

      if (data.success) {
        await loadKeys();
      }
    } catch (err) {
      console.error('Error toggling:', err);
    }
  };

  const copyToClipboard = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const generateEmbedCode = (key: EmbedKey) => {
    return `<!-- TNCB Voice Agent Widget -->
<script>
  (function() {
    var script = document.createElement('script');
    script.src = '${window.location.origin}/embed/tncb-agent.js';
    script.async = true;
    script.onload = function() {
      TNCBAgent.init({
        apiKey: 'YOUR_API_KEY',
        position: '${key.widget_config.position}',
        theme: '${key.widget_config.theme}'
      });
    };
    document.head.appendChild(script);
  })();
</script>`;
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="bg-muted h-8 w-1/4 rounded"></div>
          <div className="bg-muted h-32 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Embed API Keys</h1>
          <p className="text-muted-foreground">
            Create API keys to embed the voice assistant on external websites
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadKeys} className="hover:bg-muted rounded-lg p-2" title="Refresh">
            <ArrowsClockwise className="h-5 w-5" />
          </button>
          <button
            onClick={() => {
              setForm(defaultForm);
              setEditingId(null);
              setShowForm(true);
            }}
            className="bg-primary text-primary-foreground flex items-center gap-2 rounded-lg px-4 py-2 hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            Create Key
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-destructive/10 text-destructive mb-4 rounded-lg p-4">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">
            Dismiss
          </button>
        </div>
      )}

      {/* New Key Modal */}
      {newKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background mx-4 w-full max-w-lg rounded-xl p-6 shadow-xl">
            <h2 className="mb-2 text-xl font-semibold">🔑 API Key Created!</h2>
            <p className="text-muted-foreground mb-4">
              Copy this key now. It will not be shown again.
            </p>

            <div className="bg-muted flex items-center gap-2 rounded-lg p-3 font-mono text-sm break-all">
              {newKey}
              <button
                onClick={() => copyToClipboard(newKey, 'new-key')}
                className="hover:bg-background ml-auto rounded p-2"
              >
                <Copy className={`h-4 w-4 ${copiedId === 'new-key' ? 'text-green-500' : ''}`} />
              </button>
            </div>

            <button
              onClick={() => setNewKey(null)}
              className="bg-primary text-primary-foreground mt-4 w-full rounded-lg px-4 py-2"
            >
              I have copied my key
            </button>
          </div>
        </div>
      )}

      {/* Create/Edit Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background mx-4 max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl shadow-xl">
            <div className="p-6">
              <h2 className="mb-4 text-xl font-semibold">
                {editingId ? 'Edit API Key' : 'Create API Key'}
              </h2>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="mb-1 block text-sm font-medium">Name *</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="bg-background w-full rounded-lg border px-3 py-2"
                    required
                    placeholder="e.g., Production Website"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium">Description</label>
                  <textarea
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    className="bg-background w-full rounded-lg border px-3 py-2"
                    rows={2}
                    placeholder="Internal notes about this key"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium">
                    Allowed Domains *{' '}
                    <span className="text-muted-foreground font-normal">(one per line)</span>
                  </label>
                  <textarea
                    value={form.allowed_domains}
                    onChange={(e) => setForm({ ...form, allowed_domains: e.target.value })}
                    className="bg-background w-full rounded-lg border px-3 py-2 font-mono text-sm"
                    rows={3}
                    placeholder="example.com&#10;*.example.com&#10;localhost"
                    required={!editingId}
                  />
                  <p className="text-muted-foreground mt-1 text-xs">
                    Use *.domain.com for wildcard subdomains
                  </p>
                </div>

                <div className="border-t pt-4">
                  <h3 className="mb-3 font-medium">Branding</h3>

                  <div className="space-y-3">
                    <div>
                      <label className="mb-1 block text-sm">Company Name</label>
                      <input
                        type="text"
                        value={form.company_name}
                        onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                        className="bg-background w-full rounded-lg border px-3 py-2"
                        placeholder="Your Company"
                      />
                    </div>

                    <div>
                      <label className="mb-1 block text-sm">Logo URL</label>
                      <input
                        type="url"
                        value={form.logo_url}
                        onChange={(e) => setForm({ ...form, logo_url: e.target.value })}
                        className="bg-background w-full rounded-lg border px-3 py-2"
                        placeholder="https://example.com/logo.png"
                      />
                    </div>

                    <div>
                      <label className="mb-1 block text-sm">Accent Color</label>
                      <div className="flex gap-2">
                        <input
                          type="color"
                          value={form.accent_color}
                          onChange={(e) => setForm({ ...form, accent_color: e.target.value })}
                          className="h-10 w-20 cursor-pointer rounded"
                        />
                        <input
                          type="text"
                          value={form.accent_color}
                          onChange={(e) => setForm({ ...form, accent_color: e.target.value })}
                          className="bg-background flex-1 rounded-lg border px-3 py-2"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <h3 className="mb-3 font-medium">Widget Settings</h3>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-sm">Position</label>
                      <select
                        value={form.position}
                        onChange={(e) => setForm({ ...form, position: e.target.value })}
                        className="bg-background w-full rounded-lg border px-3 py-2"
                      >
                        <option value="bottom-right">Bottom Right</option>
                        <option value="bottom-left">Bottom Left</option>
                        <option value="top-right">Top Right</option>
                        <option value="top-left">Top Left</option>
                      </select>
                    </div>

                    <div>
                      <label className="mb-1 block text-sm">Theme</label>
                      <select
                        value={form.theme}
                        onChange={(e) => setForm({ ...form, theme: e.target.value })}
                        className="bg-background w-full rounded-lg border px-3 py-2"
                      >
                        <option value="auto">Auto</option>
                        <option value="light">Light</option>
                        <option value="dark">Dark</option>
                      </select>
                    </div>

                    <div>
                      <label className="mb-1 block text-sm">Size</label>
                      <select
                        value={form.size}
                        onChange={(e) => setForm({ ...form, size: e.target.value })}
                        className="bg-background w-full rounded-lg border px-3 py-2"
                      >
                        <option value="small">Small</option>
                        <option value="medium">Medium</option>
                        <option value="large">Large</option>
                      </select>
                    </div>

                    <div>
                      <label className="mb-1 block text-sm">Button Text</label>
                      <input
                        type="text"
                        value={form.button_text}
                        onChange={(e) => setForm({ ...form, button_text: e.target.value })}
                        className="bg-background w-full rounded-lg border px-3 py-2"
                        placeholder="Chat with us"
                      />
                    </div>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <h3 className="mb-3 font-medium">Rate Limits</h3>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-sm">Requests/Min</label>
                      <input
                        type="number"
                        value={form.rate_limit_rpm}
                        onChange={(e) => setForm({ ...form, rate_limit_rpm: e.target.value })}
                        className="bg-background w-full rounded-lg border px-3 py-2"
                        min="1"
                      />
                    </div>

                    <div>
                      <label className="mb-1 block text-sm">Max Sessions</label>
                      <input
                        type="number"
                        value={form.max_concurrent_sessions}
                        onChange={(e) =>
                          setForm({ ...form, max_concurrent_sessions: e.target.value })
                        }
                        className="bg-background w-full rounded-lg border px-3 py-2"
                        min="1"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex justify-end gap-2 border-t pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setShowForm(false);
                      setEditingId(null);
                      setForm(defaultForm);
                    }}
                    className="hover:bg-muted rounded-lg px-4 py-2"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="bg-primary text-primary-foreground rounded-lg px-4 py-2 hover:opacity-90 disabled:opacity-50"
                  >
                    {saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Embed Code Modal */}
      {showCode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background mx-4 w-full max-w-2xl rounded-xl p-6 shadow-xl">
            <h2 className="mb-2 text-xl font-semibold">Embed Code</h2>
            <p className="text-muted-foreground mb-4">
              Add this code to your website HTML before the closing &lt;/body&gt; tag.
            </p>

            <pre className="bg-muted overflow-x-auto rounded-lg p-4 text-sm">
              <code>{generateEmbedCode(keys.find((k) => k.id === showCode)!)}</code>
            </pre>

            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => {
                  const key = keys.find((k) => k.id === showCode);
                  if (key) copyToClipboard(generateEmbedCode(key), 'embed-code');
                }}
                className="hover:bg-muted flex items-center gap-2 rounded-lg px-4 py-2"
              >
                <Copy className={`h-4 w-4 ${copiedId === 'embed-code' ? 'text-green-500' : ''}`} />
                Copy Code
              </button>
              <button
                onClick={() => setShowCode(null)}
                className="bg-primary text-primary-foreground rounded-lg px-4 py-2"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Keys List */}
      {keys.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed py-12 text-center">
          <Key className="text-muted-foreground mx-auto mb-4 h-12 w-12" />
          <h3 className="mb-2 text-lg font-medium">No API keys yet</h3>
          <p className="text-muted-foreground mb-4">
            Create an API key to embed the voice assistant on external websites
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="bg-primary text-primary-foreground inline-flex items-center gap-2 rounded-lg px-4 py-2"
          >
            <Plus className="h-4 w-4" />
            Create Key
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {keys.map((key) => (
            <div
              key={key.id}
              className={`rounded-xl border p-4 ${!key.is_active ? 'opacity-60' : ''}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <Key className="text-muted-foreground h-4 w-4" />
                    <h3 className="font-semibold">{key.name}</h3>
                    {!key.is_active && (
                      <span className="bg-muted rounded px-2 py-0.5 text-xs">Inactive</span>
                    )}
                  </div>

                  <div className="mt-2 flex items-center gap-2">
                    <code className="bg-muted rounded px-2 py-0.5 text-sm">
                      {key.key_prefix}...
                    </code>
                    {key.description && (
                      <span className="text-muted-foreground text-sm">• {key.description}</span>
                    )}
                  </div>

                  <div className="mt-2 flex flex-wrap gap-1">
                    {key.allowed_domains.map((domain) => (
                      <span
                        key={domain}
                        className="bg-primary/10 text-primary rounded px-2 py-0.5 text-xs"
                      >
                        {domain}
                      </span>
                    ))}
                  </div>

                  <div className="text-muted-foreground mt-3 flex items-center gap-4 text-sm">
                    <span>{key.total_sessions} sessions</span>
                    <span>{key.total_messages} messages</span>
                    {key.last_used_at && <span>Last used: {formatDate(key.last_used_at)}</span>}
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setShowCode(key.id)}
                    className="hover:bg-muted rounded-lg p-2"
                    title="Get embed code"
                  >
                    <Code className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleEdit(key)}
                    className="hover:bg-muted rounded-lg p-2"
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleRegenerate(key.id)}
                    className="hover:bg-muted rounded-lg p-2"
                    title="Regenerate key"
                  >
                    <ArrowsClockwise className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleToggleActive(key)}
                    className="hover:bg-muted rounded-lg p-2"
                    title={key.is_active ? 'Deactivate' : 'Activate'}
                  >
                    <span
                      className={`block h-4 w-4 rounded-full ${key.is_active ? 'bg-green-500' : 'bg-muted'}`}
                    />
                  </button>
                  <button
                    onClick={() => handleDelete(key.id)}
                    className="hover:bg-destructive/10 text-destructive rounded-lg p-2"
                    title="Delete"
                  >
                    <Trash className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
