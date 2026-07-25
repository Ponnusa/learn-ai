'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';
import { useTranslation } from '@/hooks/useTranslation';

const STORAGE_KEY = 'learnai-student-classrooms-tour-v1';
const EVENT_KEY   = 'start-student-classrooms-tour';
const SELECTORS: (string | undefined)[] = [
  undefined,
  '[data-tour="join-code-input"]',
  undefined,
];

export function StudentClassroomsTour() {
  const { t } = useTranslation();
  const [show, setShow] = useState(false);

  const steps: TourStep[] = t.tours.studentClassrooms.map((s, i) => ({
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
    window.addEventListener(EVENT_KEY, onTrigger);
    return () => window.removeEventListener(EVENT_KEY, onTrigger);
  }, []);

  if (!show) return null;
  return (
    <SpotlightTour steps={steps} storageKey={STORAGE_KEY} onDone={() => setShow(false)} />
  );
}
