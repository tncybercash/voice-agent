'use client';

import { useState } from 'react';
import { Key, LinkSimple, SquaresFour } from '@phosphor-icons/react';
import { EmbedKeyManager } from '@/components/admin/embed-key-manager';
import { ShareLinkManager } from '@/components/admin/share-link-manager';

type Tab = 'share-links' | 'embed-keys';

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>('share-links');

  const tabs = [
    { id: 'share-links' as Tab, label: 'Share Links', icon: LinkSimple },
    { id: 'embed-keys' as Tab, label: 'Embed Keys', icon: Key },
  ];

  return (
    <div className="bg-background min-h-screen">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <div className="flex items-center gap-3">
            <SquaresFour className="h-6 w-6" />
            <h1 className="text-xl font-bold">Admin Dashboard</h1>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="border-b">
        <div className="mx-auto max-w-6xl px-6">
          <nav className="flex gap-4">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 border-b-2 px-4 py-3 transition-colors ${
                  activeTab === tab.id
                    ? 'border-primary text-primary'
                    : 'text-muted-foreground hover:text-foreground border-transparent'
                }`}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Content */}
      <main>
        {activeTab === 'share-links' && <ShareLinkManager />}
        {activeTab === 'embed-keys' && <EmbedKeyManager />}
      </main>
    </div>
  );
}
