'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';
import { useTranslation } from '@/hooks/useTranslation';

const STORAGE_KEY = 'learnai-course-detail-tour-v1';
const EVENT_KEY   = 'start-course-detail-tour';
const SELECTORS: (string | undefined)[] = [
  undefined,
  '[data-tour="upload-chapter"]',
  '[data-tour="add-unit"]',
  '[data-tour="publish-btn"]',
];

export function CourseDetailTour() {
  const { t } = useTranslation();
  const [show, setShow] = useState(false);

  const steps: TourStep[] = t.tours.courseDetail.map((s, i) => ({
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
