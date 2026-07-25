'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-teacher-courses-tour-v1';
const EVENT_KEY   = 'start-teacher-courses-tour';

const STEPS: TourStep[] = [
  {
    title: 'Course Builder',
    body: 'Build structured courses with units, concepts, and AI-generated quizzes, flashcards, and videos — all from your own content.',
  },
  {
    title: 'Create your first course',
    body: 'Give it a name, subject, and grade level. Once created, add units and upload concept material (text, images, PDFs).',
    targetSelector: '[data-tour="new-course"]',
  },
  {
    title: 'What happens inside',
    body: 'Each concept gets:\n📝 AI summary & transcript\n🃏 Flashcard deck with spaced repetition\n✏️ Auto-graded quiz\n🎬 Animated video\n\nPublish the course to make it visible to your classroom.',
  },
];

export function TeacherCoursesTour() {
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
