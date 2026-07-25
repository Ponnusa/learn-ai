'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-teacher-classrooms-tour-v1';
const EVENT_KEY   = 'start-teacher-classrooms-tour';

const STEPS: TourStep[] = [
  {
    title: 'Classrooms',
    body: 'Group students into classrooms, assign courses, and share a join code — students enrol themselves in seconds.',
  },
  {
    title: 'Create a classroom',
    body: 'Name it, pick a subject and grade. A unique 6-character join code is generated automatically — no email invites needed.',
    targetSelector: '[data-tour="new-classroom"]',
  },
  {
    title: 'Share the join code',
    body: 'Copy the bold code shown on each classroom card and send it to your students. They go to their Classrooms page and enter it to enrol.\n\nFrom inside the classroom you can assign courses and track student progress.',
  },
];

export function TeacherClassroomsTour() {
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
