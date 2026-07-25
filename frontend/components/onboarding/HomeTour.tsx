'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';
import { useTranslation } from '@/hooks/useTranslation';

const STORAGE_KEY = 'learnai-home-tour-v1';
const SELECTORS: (string | undefined)[] = [
  undefined,
  '[data-tour="chat-input"]',
  '[data-tour="starter-prompts"]',
  '[data-tour="image-upload"]',
  undefined,
];

export function HomeTour() {
  const { t } = useTranslation();
  const [show, setShow] = useState(false);

  const steps: TourStep[] = t.tours.home.map((s, i) => ({
    ...s,
    ...(SELECTORS[i] ? { targetSelector: SELECTORS[i]! } : {}),
  }));

  useEffect(() => {
    try { if (localStorage.getItem(STORAGE_KEY)) return; } catch {}
    const timer = setTimeout(() => setShow(true), 900);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    function onTrigger() {
      try { localStorage.removeItem(STORAGE_KEY); } catch {}
      setShow(true);
    }
    window.addEventListener('start-home-tour', onTrigger);
    return () => window.removeEventListener('start-home-tour', onTrigger);
  }, []);

  if (!show) return null;
  return (
    <SpotlightTour
      steps={steps}
      storageKey={STORAGE_KEY}
      persistOnDone={false}
      onDone={() => setShow(false)}
    />
  );
}
