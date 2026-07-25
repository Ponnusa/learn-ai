'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-messages-tour-v1';
const EVENT_KEY   = 'start-messages-tour';

const TEACHER_STEPS: TourStep[] = [
  {
    title: 'Direct messages',
    body: 'Private, threaded conversations between you and individual students.',
  },
  {
    title: 'Starting a conversation',
    body: 'Go to a student\'s profile page and click "Message" to open a thread.\n\nNew messages from students appear here with an unread badge. Replies are instant — no email needed.',
  },
];

const STUDENT_STEPS: TourStep[] = [
  {
    title: 'Messages',
    body: 'Direct messages between you and your teachers — private and instant.',
  },
  {
    title: 'How it works',
    body: 'Your teacher can message you directly from the Students view.\nYou reply here or from inside your classroom.\n\nCheck back for feedback on assignments and quiz results.',
  },
];

export function MessagesTour({ isTeacher }: { isTeacher: boolean }) {
  const [show, setShow] = useState(false);
  const steps = isTeacher ? TEACHER_STEPS : STUDENT_STEPS;

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
    <SpotlightTour steps={steps} storageKey={STORAGE_KEY} onDone={() => setShow(false)} />
  );
}
