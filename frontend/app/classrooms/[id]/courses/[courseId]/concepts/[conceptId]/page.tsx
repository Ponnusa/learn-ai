'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft, BookOpen, Zap, Loader2, ImageIcon } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ConceptImage { id: string; url: string; caption: string; }
interface ConceptDetail {
  id: string; title: string; description?: string;
  content_text?: string; study_set_id?: string;
  images: ConceptImage[];
}

export default function StudentConceptDetailPage() {
  const router      = useRouter();
  const params      = useParams();
  const classroomId = params.id        as string;
  const courseId    = params.courseId  as string;
  const conceptId   = params.conceptId as string;
  const { user, token } = useSessionStore();

  const [concept,    setConcept]    = useState<ConceptDetail | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [activating, setActivating] = useState(false);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setConcept(d); })
      .finally(() => setLoading(false));
  }, [user, conceptId]);

  async function startLearning() {
    if (!concept) return;
    setActivating(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/activate`, {
        method: 'POST', headers,
      });
      if (res.ok) {
        const { study_set_id } = await res.json();
        if (study_set_id) router.push(`/study/${study_set_id}`);
      }
    } finally { setActivating(false); }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );
  if (!concept) return null;

  const hasContent = concept.content_text || concept.images.length > 0;

  return (
    <div className="p-6 max-w-2xl mx-auto">
      {/* Back */}
      <button onClick={() => router.push(`/classrooms/${classroomId}/courses/${courseId}`)}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> Back to course
      </button>

      {/* Title */}
      <h1 className="text-[var(--tx1)] text-2xl font-bold mb-1">{concept.title}</h1>
      {concept.description && (
        <p className="text-[var(--tx6)] text-sm mb-6">{concept.description}</p>
      )}

      {/* Teacher explanation */}
      {concept.content_text && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-6 mb-6">
          <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <BookOpen size={12} /> Explanation
          </h2>
          <div className="text-[var(--tx2)] text-sm leading-relaxed whitespace-pre-wrap">
            {concept.content_text}
          </div>
        </div>
      )}

      {/* Images */}
      {concept.images.length > 0 && (
        <div className="mb-6">
          <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <ImageIcon size={12} /> Illustrations
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {concept.images.map(img => (
              <figure key={img.id}
                className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
                <img
                  src={`${API_BASE}${img.url}`}
                  alt={img.caption || concept.title}
                  className="w-full aspect-video object-contain bg-[var(--ov2)]"
                />
                {img.caption && (
                  <figcaption className="px-3 py-2 text-xs text-[var(--tx6)]">
                    {img.caption}
                  </figcaption>
                )}
              </figure>
            ))}
          </div>
        </div>
      )}

      {/* CTA */}
      <div className={`rounded-2xl border p-5 text-center ${
        concept.study_set_id
          ? 'bg-[var(--surface)] border-[var(--bd)]'
          : 'bg-[var(--ov1)] border-dashed border-[var(--bd)]'
      }`}>
        {concept.study_set_id ? (
          <>
            {hasContent
              ? <p className="text-[var(--tx3)] text-sm mb-3">Ready to put this into practice?</p>
              : <p className="text-[var(--tx3)] text-sm mb-3">{concept.title}</p>
            }
            <button onClick={startLearning} disabled={activating}
              className="inline-flex items-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-500
                         text-white font-medium rounded-xl transition-all disabled:opacity-40">
              {activating ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
              Start learning
            </button>
          </>
        ) : (
          <>
            <p className="text-[var(--tx3)] text-sm font-medium mb-1">Study materials coming soon</p>
            <p className="text-[var(--tx7)] text-xs">
              Your teacher is preparing videos and flashcards for this concept
            </p>
          </>
        )}
      </div>
    </div>
  );
}
