'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-course-detail-tour-v1';
const EVENT_KEY   = 'start-course-detail-tour';

const STEPS: TourStep[] = [
  {
    title: 'Your course workspace',
    body: 'Each course is made of units (chapters) and concepts (topics). Upload a PDF and AI fills in the structure automatically, or build it unit by unit.',
  },
  {
    title: 'Upload a chapter PDF',
    body: 'Drop any textbook chapter here. AI detects units, extracts key concepts, and queues up summaries, quizzes, flashcards and animated videos — one click.',
    targetSelector: '[data-tour="upload-chapter"]',
  },
  {
    title: 'Add units manually',
    body: 'Prefer to build by hand? Add a unit, then add concept topics inside it. You can always attach a PDF to a unit later for AI generation.',
    targetSelector: '[data-tour="add-unit"]',
  },
  {
    title: 'Publish & assign',
    body: 'When the course is ready, publish it and assign it to a classroom. Students see it instantly in their classroom view.',
    targetSelector: '[data-tour="publish-btn"]',
  },
];

export function CourseDetailTour() {
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
