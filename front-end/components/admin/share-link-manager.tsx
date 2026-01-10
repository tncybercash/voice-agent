'use client';

import { useCallback, useEffect, useState } from 'react';
import { ArrowSquareOut, ArrowsClockwise, Copy, Pencil, Plus, Trash } from '@phosphor-icons/react';

interface ShareLink {
  id: string;
  code: string;
  name: string;
  description: string | null;
  custom_greeting: string | null;
  branding: {
    logo_url: string | null;
    accent_color: string | null;
    company_name: string | null;
  };
  is_active: boolean;
  expires_at: string | null;
  max_sessions: number | null;
  total_sessions: number;
  total_messages: number;
  last_used_at: string | null;
  created_at: string;
  url: string;
}

interface CreateShareLinkForm {
  name: string;
  description: string;
  custom_greeting: string;
  company_name: string;
  logo_url: string;
  accent_color: string;
  expires_at: string;
  max_sessions: string;
}

const defaultForm: CreateShareLinkForm = {
  name: '',
  description: '',
  custom_greeting: '',
  company_name: '',
  logo_url: '',
  accent_color: '#3b82f6',
  expires_at: '',
  max_sessions: '',
};

export function ShareLinkManager() {
  const [links, setLinks] = useState<ShareLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<CreateShareLinkForm>(defaultForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const loadLinks = useCallback(async () => {
    try {
      const response = await fetch('/api/share-links?include_inactive=true');
      const data = await response.json();
      if (data.success) {
        setLinks(data.data);
      }
    } catch (err) {
      console.error('Error loading share links:', err);
      setError('Failed to load share links');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLinks();
  }, [loadLinks]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const payload = {
        name: form.name,
        description: form.description || null,
        custom_greeting: form.custom_greeting || null,
        branding: {
          company_name: form.company_name || null,
          logo_url: form.logo_url || null,
          accent_color: form.accent_color || null,
        },
        expires_at: form.expires_at || null,
        max_sessions: form.max_sessions ? parseInt(form.max_sessions) : null,
      };

      const url = editingId ? `/api/share-links/${editingId}` : '/api/share-links';

      const response = await fetch(url, {
        method: editingId ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (data.success) {
        await loadLinks();
        setShowForm(false);
        setEditingId(null);
        setForm(defaultForm);
      } else {
        setError(data.error || 'Failed to save');
      }
    } catch (err) {
      console.error('Error saving:', err);
      setError('Failed to save share link');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (link: ShareLink) => {
    setForm({
      name: link.name,
      description: link.description || '',
      custom_greeting: link.custom_greeting || '',
      company_name: link.branding.company_name || '',
      logo_url: link.branding.logo_url || '',
      accent_color: link.branding.accent_color || '#3b82f6',
      expires_at: link.expires_at ? link.expires_at.split('T')[0] : '',
      max_sessions: link.max_sessions?.toString() || '',
    });
    setEditingId(link.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this share link?')) return;

    try {
      const response = await fetch(`/api/share-links/${id}`, {
        method: 'DELETE',
      });
      const data = await response.json();

      if (data.success) {
        await loadLinks();
      } else {
        setError(data.error || 'Failed to delete');
      }
    } catch (err) {
      console.error('Error deleting:', err);
      setError('Failed to delete share link');
    }
  };

  const handleToggleActive = async (link: ShareLink) => {
    try {
      const response = await fetch(`/api/share-links/${link.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !link.is_active }),
      });
      const data = await response.json();

      if (data.success) {
        await loadLinks();
      }
    } catch (err) {
      console.error('Error toggling:', err);
    }
  };

  const copyToClipboard = async (link: ShareLink) => {
    const fullUrl = `${window.location.origin}/s/${link.code}`;
    await navigator.clipboard.writeText(fullUrl);
    setCopiedId(link.id);
    setTimeout(() => setCopiedId(null), 2000);
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
          <h1 className="text-2xl font-bold">Share Links</h1>
          <p className="text-muted-foreground">
            Create shareable links to give others access to your voice assistant
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadLinks} className="hover:bg-muted rounded-lg p-2" title="Refresh">
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
            Create Link
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

      {/* Create/Edit Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background mx-4 max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl shadow-xl">
            <div className="p-6">
              <h2 className="mb-4 text-xl font-semibold">
                {editingId ? 'Edit Share Link' : 'Create Share Link'}
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
                    placeholder="e.g., Customer Support Link"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium">Description</label>
                  <textarea
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    className="bg-background w-full rounded-lg border px-3 py-2"
                    rows={2}
                    placeholder="Internal notes about this link"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium">Custom Greeting</label>
                  <textarea
                    value={form.custom_greeting}
                    onChange={(e) => setForm({ ...form, custom_greeting: e.target.value })}
                    className="bg-background w-full rounded-lg border px-3 py-2"
                    rows={2}
                    placeholder="Override the default greeting for this link"
                  />
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
                  <h3 className="mb-3 font-medium">Limits</h3>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-sm">Expires On</label>
                      <input
                        type="date"
                        value={form.expires_at}
                        onChange={(e) => setForm({ ...form, expires_at: e.target.value })}
                        className="bg-background w-full rounded-lg border px-3 py-2"
                      />
                    </div>

                    <div>
                      <label className="mb-1 block text-sm">Max Sessions</label>
                      <input
                        type="number"
                        value={form.max_sessions}
                        onChange={(e) => setForm({ ...form, max_sessions: e.target.value })}
                        className="bg-background w-full rounded-lg border px-3 py-2"
                        placeholder="Unlimited"
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

      {/* Links List */}
      {links.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed py-12 text-center">
          <h3 className="mb-2 text-lg font-medium">No share links yet</h3>
          <p className="text-muted-foreground mb-4">
            Create your first share link to let others access your voice assistant
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="bg-primary text-primary-foreground inline-flex items-center gap-2 rounded-lg px-4 py-2"
          >
            <Plus className="h-4 w-4" />
            Create Link
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {links.map((link) => (
            <div
              key={link.id}
              className={`rounded-xl border p-4 ${!link.is_active ? 'opacity-60' : ''}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{link.name}</h3>
                    {!link.is_active && (
                      <span className="bg-muted rounded px-2 py-0.5 text-xs">Inactive</span>
                    )}
                    {link.branding.company_name && (
                      <span className="bg-primary/10 text-primary rounded px-2 py-0.5 text-xs">
                        {link.branding.company_name}
                      </span>
                    )}
                  </div>
                  {link.description && (
                    <p className="text-muted-foreground mt-1 text-sm">{link.description}</p>
                  )}

                  <div className="text-muted-foreground mt-3 flex items-center gap-4 text-sm">
                    <span className="flex items-center gap-1">
                      <code className="bg-muted rounded px-2 py-0.5">/s/{link.code}</code>
                    </span>
                    <span>{link.total_sessions} sessions</span>
                    <span>{link.total_messages} messages</span>
                    {link.last_used_at && <span>Last used: {formatDate(link.last_used_at)}</span>}
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => copyToClipboard(link)}
                    className="hover:bg-muted rounded-lg p-2"
                    title="Copy link"
                  >
                    <Copy className={`h-4 w-4 ${copiedId === link.id ? 'text-green-500' : ''}`} />
                  </button>
                  <a
                    href={`/s/${link.code}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:bg-muted rounded-lg p-2"
                    title="Open link"
                  >
                    <ArrowSquareOut className="h-4 w-4" />
                  </a>
                  <button
                    onClick={() => handleEdit(link)}
                    className="hover:bg-muted rounded-lg p-2"
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleToggleActive(link)}
                    className="hover:bg-muted rounded-lg p-2"
                    title={link.is_active ? 'Deactivate' : 'Activate'}
                  >
                    <span
                      className={`block h-4 w-4 rounded-full ${link.is_active ? 'bg-green-500' : 'bg-muted'}`}
                    />
                  </button>
                  <button
                    onClick={() => handleDelete(link.id)}
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
