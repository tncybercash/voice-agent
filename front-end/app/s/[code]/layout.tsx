import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Voice Assistant',
  description: 'Shared voice assistant',
};

export default function ShareLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
