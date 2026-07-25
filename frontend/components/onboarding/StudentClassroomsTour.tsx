'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-student-classrooms-tour-v1';
const EVENT_KEY   = 'start-student-classrooms-tour';

const STEPS: TourStep[] = [
  {
    title: 'Your classrooms',
    body: 'Each classroom contains courses your teacher has assigned. Work through concepts, take quizzes, and review flashcards with spaced repetition.',
  },
  {
    title: 'Join a classroom',
    body: 'Enter the 6-character code your teacher shared and press Join. You\'ll immediately see their assigned courses.',
    targetSelector: '[data-tour="join-code-input"]',
  },
  {
    title: 'Inside a classroom',
    body: 'Each concept has:\n🃏 Flashcards — spaced repetition reminders\n✏️ Quiz — scored and reported to your teacher\n💬 AI tutor chat — ask anything about the topic\n🎬 Video — animated explanation',
  },
];

export function StudentClassroomsTour() {
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
    <SpotlightTour steps={STEPS} storageKey={STORAGE_KEY} onDone={() => setShow(false)} />
  );
}
