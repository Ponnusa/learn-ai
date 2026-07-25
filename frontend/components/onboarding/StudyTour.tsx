'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-study-tour-v1';
const EVENT_KEY   = 'start-study-tour';

const STEPS: TourStep[] = [
  {
    title: 'Study Sets',
    body: 'Upload any PDF — textbook chapter, lecture notes, past paper — and AI automatically creates flashcards, a quiz, and a personal tutor chat for it.',
  },
  {
    title: 'Create your first set',
    body: 'Click here to upload a PDF. AI will read it and build your study material in about 30 seconds.',
    targetSelector: '[data-tour="new-study-set"]',
  },
  {
    title: 'Inside a study set',
    body: 'Each set has:\n📚 Flashcards — swipe through key concepts\n✏️ Quiz — test yourself with auto-graded questions\n💬 Chat tutor — ask anything about the material',
  },
];

export function StudyTour() {
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
