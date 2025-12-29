import { Button } from '@/components/livekit/button';

function WelcomeImage() {
  return (
    <div className="relative">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/logo_light.png"
        alt="AI Assistant"
        className="block h-40 w-150 object-contain dark:hidden"
      />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/logo_dark.png"
        alt="AI Assistant"
        className="hidden h-40 w-150 object-contain dark:block"
      />
    </div>
  );
}

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div ref={ref}>
      <section className="bg-background flex flex-col items-center justify-center text-center">
        <WelcomeImage />

        <h1 className="text-foreground mb-2 text-2xl font-semibold">Batsi : Voice AI Assistant</h1>

        <p className="text-muted-foreground max-w-prose pt-1 leading-6">
          Experience seamless banking with our AI-powered voice assistant.
        </p>

        <Button
          variant="primary"
          size="lg"
          onClick={onStartCall}
          className="mt-8 w-64 font-mono transition-all duration-300 hover:scale-105"
          style={{ backgroundColor: '#DAC256', color: '#000' }}
        >
          {startButtonText}
        </Button>
      </section>
    </div>
  );
};
