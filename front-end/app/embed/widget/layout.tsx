import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Voice Assistant Widget',
  description: 'Embedded voice assistant',
};

export default function EmbedLayout({ children }: { children: React.ReactNode }) {
  return <div className="h-screen overflow-hidden">{children}</div>;
}
