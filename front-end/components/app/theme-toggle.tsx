'use client';

import { useTheme } from 'next-themes';
import { MoonIcon, SunIcon } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const { theme, setTheme } = useTheme();

  return (
    <div
      className={cn(
        'text-foreground bg-background border-gold/30 flex flex-row gap-1 overflow-hidden rounded-full border p-1',
        className
      )}
    >
      <span className="sr-only">Color scheme toggle</span>
      <button
        type="button"
        onClick={() => setTheme('light')}
        suppressHydrationWarning
        className={cn(
          'cursor-pointer rounded-full p-2 transition-colors',
          theme === 'light' ? 'bg-gold/20' : 'hover:bg-gold/10'
        )}
      >
        <span className="sr-only">Enable light color scheme</span>
        <SunIcon
          suppressHydrationWarning
          size={16}
          weight="bold"
          className={cn(theme !== 'light' && 'opacity-40')}
        />
      </button>
      <button
        type="button"
        onClick={() => setTheme('dark')}
        suppressHydrationWarning
        className={cn(
          'cursor-pointer rounded-full p-2 transition-colors',
          theme === 'dark' ? 'bg-gold/20' : 'hover:bg-gold/10'
        )}
      >
        <span className="sr-only">Enable dark color scheme</span>
        <MoonIcon
          suppressHydrationWarning
          size={16}
          weight="bold"
          className={cn(theme !== 'dark' && 'opacity-40')}
        />
      </button>
    </div>
  );
}
