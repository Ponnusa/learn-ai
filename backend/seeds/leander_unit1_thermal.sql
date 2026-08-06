-- ============================================================
-- Seed: Leander ISD 6th Grade Science — Unit 1 (Thermal Energy)
-- "How can containers keep stuff from warming up or cooling down?"
-- Aug 25 – Oct 28 | 18 lessons | TEKS: 6.6A-D, 6.8B, 7.8A-C
--
-- Run ONCE against production DB to pre-load the demo curriculum.
-- Re-running is safe: INSERT ... ON CONFLICT DO NOTHING.
-- ============================================================

INSERT INTO curriculum_contexts (
  id,
  name,
  driving_question,
  teks_codes,
  grade_level,
  subject,
  active_lesson,
  lesson_count,
  key_ideas,
  vocabulary,
  inquiry_guardrail,
  unit_start_date,
  unit_end_date
) VALUES (
  '00000000-0000-0000-0000-000000000001',  -- fixed UUID for easy reference

  '6th Grade Science – Unit 1: Thermal Energy',

  'How can containers keep stuff from warming up or cooling down?',

  ARRAY['6.6A','6.6B','6.6C','6.6D','6.8B','7.8A','7.8B','7.8C'],

  '6th Grade',
  'Science',

  1,   -- active_lesson (teacher updates this as the unit progresses)
  18,  -- lesson_count

  '[
    "The rate of energy transfer between systems speeds up or slows down depending on the number of particle collisions — more contact means faster transfer, less contact (e.g. air gaps) means slower transfer",
    "The rate of energy transfer between matter and light speeds up or slows down depending on how much light is absorbed — dark or non-reflective surfaces absorb more, reflective surfaces absorb less",
    "The amount of matter in a substance (mass) affects the rate of energy transfer and how much energy is needed to increase the substance''s temperature",
    "Objects designed to keep things cold or hot share design features that create air insulation and have transparent or reflective surfaces",
    "Energy transfer can be slowed or sped up by changing the structure of a container — this is the structure-to-function relationship in engineering design"
  ]'::jsonb,

  ARRAY[
    'thermal energy','temperature','energy transfer',
    'conduction','convection','radiation',
    'insulation','particle collision','absorption','reflection',
    'criteria','constraints','system',
    'structure','function','model',
    'minimize','maximize'
  ],

  'This is an INQUIRY-BASED unit. Students discover science principles through hands-on experiments (Cold Cup Challenge) and class discussion (Scientists Circle, Driving Question Board). '
  'NEVER give direct answers to the driving question or state the key ideas outright. '
  'Instead, guide students with questions: "What did you notice in your data?", "Why do you think that cup performed better?", "How does that connect to what you observed?". '
  'Help students connect their observations to the science concepts. '
  'Reference the Driving Question Board (DQB) when appropriate — students track their own understanding there. '
  'Use the unit vocabulary naturally in your responses so students build familiarity with the terms.',

  '2026-08-25',
  '2026-10-28'
)
ON CONFLICT (id) DO NOTHING;
