'use client';
import { useState, useEffect } from 'react';
import { SpotlightTour, TourStep } from './SpotlightTour';

const STORAGE_KEY = 'learnai-home-tour-v1';

const STEPS: TourStep[] = [
  {
    title: 'Welcome to LearnX-AI 👋',
    body: 'A 30-second tour to show you what this chat can do.\nPress Next or use → to continue.',
  },
  {
    title: 'Ask anything',
    body: 'Type any question here — maths, physics, chemistry.\nFormulas, equations, and chemical structures render beautifully inline.',
    targetSelector: '[data-tour="chat-input"]',
  },
  {
    title: 'Jump-start with examples',
    body: 'Click a suggestion to try it instantly.\nThe aspirin example renders a 2-D molecular diagram using SMILES notation.',
    targetSelector: '[data-tour="starter-prompts"]',
  },
  {
    title: 'Upload a photo or PDF',
    body: 'Snap a photo of a textbook page, homework problem, or lab diagram — the AI will read it and answer your question about it.',
    targetSelector: '[data-tour="image-upload"]',
  },
  {
    title: 'Do more after the reply',
    body: 'Once the AI answers, action buttons appear below:\n\n🎬 Animate it — animated visual explainer\n🔊 Read aloud — text-to-speech in your language\n📝 Quiz me — instant comprehension quiz\n🎨 Sketch it — AI-drawn illustration\n\nExplore freely — everything is saved automatically.',
  },
];

export function HomeTour() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY)) return;
    } catch {}
    const t = setTimeout(() => setShow(true), 900);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    function onTrigger() {
      try { localStorage.removeItem(STORAGE_KEY); } catch {}
      setShow(true);
    }
    window.addEventListener('start-home-tour', onTrigger);
    return () => window.removeEventListener('start-home-tour', onTrigger);
  }, []);

  if (!show) return null;
  return (
    <SpotlightTour
      steps={STEPS}
      storageKey={STORAGE_KEY}
      persistOnDone={false}
      onDone={() => setShow(false)}
    />
  );
}
