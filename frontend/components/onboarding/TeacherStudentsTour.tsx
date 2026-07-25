'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-teacher-students-tour-v1';
const EVENT_KEY   = 'start-teacher-students-tour';

const STEPS: TourStep[] = [
  {
    title: 'Students overview',
    body: 'Every student across all your classrooms in one list — quiz scores, flashcard backlog, last activity, and a risk flag.',
  },
  {
    title: 'At-risk filter',
    body: 'Toggle this to surface students flagged as at-risk — low quiz scores (< 40%) or no activity in 7+ days. Select multiple to bulk-assign practice.',
    targetSelector: '[data-tour="risk-filter"]',
  },
  {
    title: 'Drill into a student',
    body: 'Click any student to see their full breakdown:\n📊 Concept-by-concept quiz history\n🃏 Flashcard schedule\n📈 Progress heatmap\n💬 Message them directly',
  },
];

export function TeacherStudentsTour() {
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
