import type { Metadata } from 'next';
import { ThemeProvider } from '@/components/app/theme-provider';
import '@/styles/globals.css';

export const metadata: Metadata = {
  title: 'Admin Dashboard - Voice Agent',
  description: 'Manage share links and embed keys',
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
