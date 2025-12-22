import { Button } from '@/components/livekit/button';

function WelcomeImage() {
  return (
    <div className="relative">
       {/* eslint-disable-next-line @next/next/no-img-element */}
        <img 
          src="/logo_light.png" 
          alt="AI Assistant" 
          className="block dark:hidden w-150 h-40 object-contain"
        />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img 
          src="/logo_dark.png" 
          alt="AI Assistant" 
          className="hidden dark:block w-150 h-40 object-contain"
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

        <h1 className="text-foreground text-2xl font-semibold mb-2">
          Batsi : Voice AI Assistant
        </h1>

        <p className="text-muted-foreground max-w-prose pt-1 leading-6">
          Experience seamless banking with our AI-powered voice assistant.
        </p>

        <Button 
          variant="primary" 
          size="lg" 
          onClick={onStartCall} 
          className="mt-8 w-64 font-mono bg-gold hover:bg-gold-dark text-primary-foreground transition-all duration-300 hover:scale-105"
        >
          {startButtonText}
        </Button>
      </section>
    </div>
  );
};
