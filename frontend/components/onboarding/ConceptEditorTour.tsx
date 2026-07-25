'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-concept-editor-tour-v1';
const EVENT_KEY   = 'start-concept-editor-tour';

const STEPS: TourStep[] = [
  {
    title: 'Concept editor',
    body: 'This is where you author, review, and approve content for one concept. Four tabs cover every stage — from drafting with AI to publishing assets for students.',
  },
  {
    title: 'Four tabs, one workflow',
    body: 'Studio → chat with AI to draft the explanation.\nTextbook → review and arrange content blocks students will read.\nResources → attach images or diagrams.\nAssets → approve quiz, flashcards, audio narration, and animated video.',
    targetSelector: '[data-tour="concept-tabs"]',
  },
  {
    title: 'Studio: draft with AI',
    body: 'Ask the AI to write a summary, add more examples, or rephrase a section. When you\'re happy, send the content to the Textbook or apply it as the summary and transcript.',
  },
  {
    title: 'Approve assets for students',
    body: 'Switch to the Assets tab to listen to the AI narration, watch the animated video, and review the quiz. Approve each one when ready — only approved assets appear to students.',
  },
];

export function ConceptEditorTour() {
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
