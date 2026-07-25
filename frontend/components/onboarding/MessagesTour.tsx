'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour } from './SpotlightTour';
import { useTranslation } from '@/hooks/useTranslation';

const STORAGE_KEY = 'learnai-messages-tour-v1';
const EVENT_KEY   = 'start-messages-tour';

export function MessagesTour({ isTeacher }: { isTeacher: boolean }) {
  const { t } = useTranslation();
  const [show, setShow] = useState(false);

  const steps = isTeacher ? t.tours.messagesTeacher : t.tours.messagesStudent;

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
