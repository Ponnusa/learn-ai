'use client';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface GradeState {
  grade: string | null;
  setGrade: (grade: string | null) => void;
}

export const useGradeStore = create<GradeState>()(
  persist(
    (set) => ({
      grade: null,
      setGrade: (grade) => set({ grade }),
    }),
    { name: 'learnai-grade' }
  )
);
