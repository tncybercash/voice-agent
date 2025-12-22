import { headers } from 'next/headers';
import { getAppConfig } from '@/lib/utils';
import { ThemeToggle } from '@/components/app/theme-toggle';

interface LayoutProps {
  children: React.ReactNode;
}

export default async function Layout({ children }: LayoutProps) {
  const hdrs = await headers();
  const { companyName } = await getAppConfig(hdrs);

  return (
    <>
      <header className="fixed top-0 left-0 z-40 hidden w-full flex-row justify-start p-6 md:flex">
        <div className="flex items-center gap-3">
          {/* Light mode icon */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img 
            src="/Icon_light.png" 
            alt={`${companyName} Icon`} 
            className="block size-10 dark:hidden drop-shadow-sm" 
          />
          {/* Dark mode icon */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/Icon_dark.png"
            alt={`${companyName} Icon`}
            className="hidden size-10 dark:block drop-shadow-sm"
          />
          {/* Theme Toggle */}
          <ThemeToggle className="bg-background/80 backdrop-blur-sm rounded-full p-1 border border-border/50" />
        </div>
      </header>

      {children}
    </>
  );
}
