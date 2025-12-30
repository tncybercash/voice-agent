import { headers } from 'next/headers';
import { ThemeToggle } from '@/components/app/theme-toggle';
import { getAppConfig } from '@/lib/utils';

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
            className="block size-10 dark:hidden"
          />
          {/* Dark mode icon */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/Icon_dark.png"
            alt={`${companyName} Icon`}
            className="hidden size-10 dark:block"
          />
          {/* Theme Toggle */}
          <ThemeToggle className="bg-background/80 border-border/50 rounded-full border p-1 backdrop-blur-sm" />
        </div>
      </header>

      {children}
    </>
  );
}
