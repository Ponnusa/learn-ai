'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-videos-tour-v1';
const EVENT_KEY   = 'start-videos-tour';

const STEPS: TourStep[] = [
  {
    title: 'Video Studio',
    body: 'Turn any topic into an animated educational video — maths, physics, chemistry, and more.\nVideos are generated with Manim and take ~2 minutes.',
  },
  {
    title: 'Describe your topic',
    body: 'Type any concept here. Be specific for best results:\n"Explain Faraday\'s law of induction" → beautiful animated explainer.',
    targetSelector: '[data-tour="video-input"]',
  },
  {
    title: 'Quick-start examples',
    body: 'Click any chip to pre-fill the input with a ready-to-go topic. All examples are translated to your language.',
    targetSelector: '[data-tour="video-examples"]',
  },
  {
    title: 'Your video library',
    body: 'Every video you generate is saved here. You can re-watch, view the transcript, or go back to the original chat conversation.',
  },
];

export function VideosTour() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    try { if (localStorage.getItem(STORAGE_KEY)) return; } catch {}
    const t = setTimeout(() => setShow(true), 900);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    function onTrigger() {
      try { localStorage.removeItem(STORAGE_KEY); } catch {}
      setShow(true);
    }
    window.addEventListener(EVENT_KEY, onTrigger);
    return () => window.removeEventListener(EVENT_KEY, onTrigger);
  }, []);

  if (!show) return null;
  return (
    <SpotlightTour
      steps={STEPS}
      storageKey={STORAGE_KEY}
      onDone={() => setShow(false)}
    />
  );
}
