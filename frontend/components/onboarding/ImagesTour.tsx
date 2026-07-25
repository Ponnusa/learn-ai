'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-images-tour-v1';
const EVENT_KEY   = 'start-images-tour';

const STEPS: TourStep[] = [
  {
    title: 'Educational Diagrams',
    body: 'Generate textbook-quality labelled diagrams from any concept in ~30 seconds. Great for visual learners or making study notes.',
  },
  {
    title: 'Describe what to draw',
    body: 'Type any educational concept. The AI extracts key elements, plans the diagram, generates it with GPT-image-1, then scores it for accuracy.',
    targetSelector: '[data-tour="image-input"]',
  },
  {
    title: 'Quick examples',
    body: 'These chips are translated to your language — click one to try it immediately. Switch language in settings to get localised examples.',
    targetSelector: '[data-tour="image-examples"]',
  },
  {
    title: 'Quality score & details',
    body: 'Each diagram shows a quality score (0–100), what visual elements were included, and the learning goal. Click any past diagram to zoom in.',
  },
];

export function ImagesTour() {
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
