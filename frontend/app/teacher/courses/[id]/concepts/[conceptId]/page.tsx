'use client';
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { MathText } from '@/components/ui/MathText';
import {
  ArrowLeft, BookOpen, Upload, Trash2, ImageIcon,
  Loader2, Check, Plus, FileText, Mic2,
  CheckCircle, Circle, AlertCircle, Zap, HelpCircle, Layers,
  RefreshCw, Volume2, Video, Send, Sparkles, LayoutList,
} from 'lucide-react';
import { ConceptTextbook } from '@/components/course/ConceptTextbook';
import { useSessionStore } from '@/store/sessionStore';
import { preprocessMath } from '@/lib/preprocessMath';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Tab            = 'summary' | 'transcript' | 'resources' | 'assets' | 'textbook';
type ResourceType   = 'image' | 'pdf' | 'video';
interface Resource  { id: string; type: ResourceType; title: string; mime_type?: string; video_url?: string; file_url?: string; position: number; text_extracted?: boolean; }
type PipelineStatus = 'draft' | 'summarizing' | 'ready' | 'approved' | 'failed';
type AssetStatus    = 'none' | 'generating' | 'ready' | 'approved' | 'failed';

interface ConceptImage { id: string; url: string; caption: string; }
interface QuizQuestion { id: string; question: string; options: string[]; correct_idx: number; explanation: string; }
interface Flashcard    { id: string; front: string; back: string; }
interface ChatMsg      { id: string; role: 'user' | 'assistant'; content: string; created_at: string; }

interface ConceptDetail {
  id: string; title: string; description?: string;
  content_text?: string; study_set_id?: string; course_id: string;
  source_text?: string; ai_summary?: string; ai_transcript?: string;
  pipeline_status: PipelineStatus; approved_at?: string;
  chapter_ref?: string;
  quiz_status: AssetStatus; flashcard_status: AssetStatus;
  audio_status: AssetStatus; video_status: AssetStatus;
  has_audio: boolean; has_video: boolean;
  audio_url?: string; video_url?: string;
  images: ConceptImage[];
}

interface Assets {
  quiz_status: AssetStatus; flashcard_status: AssetStatus;
  audio_status: AssetStatus; video_status: AssetStatus;
  video_error?: string; video_stage?: string;
  has_audio: boolean;
  audio_url?: string; video_url?: string;
  audio_duration_sec?: number;
  quiz: QuizQuestion[]; flashcards: Flashcard[];
}

export default function ConceptEditorPage() {
  const router    = useRouter();
  const params    = useParams();
  const courseId  = params.id        as string;
  const conceptId = params.conceptId as string;
  const { user, token } = useSessionStore();
  const { t, tF } = useTranslation();

  const VIDEO_STAGE_LABEL: Record<string, string> = {
    pending:           t.assignments.stageWriting,
    transcript_ready:  t.assignments.stageAnimation,
    queued:            t.assignments.stageQueued,
    rendering:         t.assignments.stageRendering,
  };

  const PIPELINE_LABEL: Record<PipelineStatus, string> = {
    draft:       '',
    summarizing: t.teacher.statusGenerating,
    ready:       t.teacher.statusReadyReview,
    approved:    t.teacher.statusApproved,
    failed:      t.teacher.statusFailed,
  };

  const [concept,    setConcept]    = useState<ConceptDetail | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [activeTab,  setActiveTab]  = useState<Tab>('summary');
  const [showLeft,   setShowLeft]   = useState(true);

  const [summary,    setSummary]    = useState('');
  const [transcript, setTranscript] = useState('');
  const [savingSum,  setSavingSum]  = useState(false);
  const [savedSum,   setSavedSum]   = useState(false);
  const [savingTr,   setSavingTr]   = useState(false);
  const [savedTr,    setSavedTr]    = useState(false);
  const [approving,  setApproving]  = useState(false);

  const [pdfUrl,   setPdfUrl]   = useState<string | null>(null);
  const [pdfReady, setPdfReady] = useState(false);
  const pdfRef = useRef<string | null>(null);

  const [uploading,  setUploading]  = useState(false);
  const fileInputRef    = useRef<HTMLInputElement>(null);

  // Resources tab state
  const [resources,        setResources]        = useState<Resource[]>([]);
  const [resourcesLoaded,  setResourcesLoaded]  = useState(false);
  const [uploadingRes,     setUploadingRes]      = useState(false);
  const [videoUrlInput,    setVideoUrlInput]     = useState('');
  const [videoTitleInput,  setVideoTitleInput]   = useState('');
  const [addingVideo,      setAddingVideo]       = useState(false);
  const [showVideoForm,    setShowVideoForm]     = useState(false);
  const resFileRef = useRef<HTMLInputElement>(null);

  const [assets,          setAssets]         = useState<Assets | null>(null);
  const [assetsLoaded,    setAssetsLoaded]    = useState(false);
  const [generatingQuiz,  setGeneratingQuiz]  = useState(false);
  const [generatingCards, setGeneratingCards] = useState(false);
  const [generatingAudio, setGeneratingAudio] = useState(false);
  const [generatingVideo, setGeneratingVideo] = useState(false);
  const [approvingA,      setApprovingA]      = useState<Record<string, boolean>>({});

  const [pipelinePolling, setPipelinePolling] = useState(false);
  const [assetPolling,    setAssetPolling]    = useState(false);

  // Authoring chat — teacher-only, never shown to students
  const [chatMsgs,    setChatMsgs]    = useState<ChatMsg[]>([]);
  const [chatLoaded,  setChatLoaded]  = useState(false);
  const [chatInput,   setChatInput]   = useState('');
  const [chatSending, setChatSending] = useState(false);
  const [applyingId,  setApplyingId]  = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const authH = { Authorization: `Bearer ${token}` };
  const jsonH = { ...authH, 'Content-Type': 'application/json' };

  // Load PDF using chapter_ref if available, else fall back to course syllabus
  async function loadPdf(chapterRef?: string) {
    try {
      let blob: Blob | null = null;

      if (chapterRef) {
        const res = await fetch(`${API_BASE}/api/courses/chapters/${chapterRef}/pdf`, { headers: authH });
        if (res.ok) blob = await res.blob();
      }

      if (!blob) {
        const res = await fetch(`${API_BASE}/api/courses/${courseId}/syllabus`, { headers: authH });
        if (res.ok) blob = await res.blob();
      }

      if (blob) {
        if (pdfRef.current) URL.revokeObjectURL(pdfRef.current);
        const url = URL.createObjectURL(blob);
        pdfRef.current = url;
        setPdfUrl(url);
      }
    } finally { setPdfReady(true); }
  }

  const loadAssets = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/assets`, { headers: authH });
    if (res.ok) {
      const d: Assets = await res.json();
      setAssets(d);
      const anyGen = d.quiz_status === 'generating' || d.flashcard_status === 'generating'
        || d.audio_status === 'generating' || d.video_status === 'generating';
      setAssetPolling(anyGen);
    }
    setAssetsLoaded(true);
  }, [conceptId, token]);

  const loadChat = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/concept-chat`, { headers: authH });
    if (res.ok) setChatMsgs(await res.json());
    setChatLoaded(true);
  }, [conceptId, token]);

  const loadResources = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/resources`, { headers: authH });
    if (res.ok) setResources(await res.json());
    setResourcesLoaded(true);
  }, [conceptId, token]);

  async function uploadResourceFile(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploadingRes(true);
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append('file', file);
        form.append('title', file.name);
        const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/resources`, {
          method: 'POST', headers: authH, body: form,
        });
        if (res.ok) {
          const r: Resource = await res.json();
          setResources(prev => [...prev, r]);
        }
      }
    } finally { setUploadingRes(false); }
  }

  async function addVideoResource() {
    const url = videoUrlInput.trim();
    if (!url) return;
    setAddingVideo(true);
    try {
      const form = new FormData();
      form.append('type', 'video');
      form.append('title', videoTitleInput.trim() || 'Video');
      form.append('video_url', url);
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/resources`, {
        method: 'POST', headers: authH, body: form,
      });
      if (res.ok) {
        const r: Resource = await res.json();
        setResources(prev => [...prev, r]);
        setVideoUrlInput(''); setVideoTitleInput(''); setShowVideoForm(false);
      }
    } finally { setAddingVideo(false); }
  }

  async function deleteResource(id: string) {
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/resources/${id}`, {
      method: 'DELETE', headers: authH,
    });
    setResources(prev => prev.filter(r => r.id !== id));
  }

  async function sendChatMessage() {
    const message = chatInput.trim();
    if (!message || chatSending) return;
    setChatInput('');
    setChatMsgs(prev => [...prev, { id: `local-${Date.now()}`, role: 'user', content: message, created_at: new Date().toISOString() }]);
    setChatSending(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/concept-chat`, {
        method: 'POST', headers: jsonH, body: JSON.stringify({ message }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not send message');
      setChatMsgs(prev => [...prev, data]);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setChatSending(false);
    }
  }

  async function applyChatMessage(messageId: string) {
    setApplyingId(messageId);
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/concept-chat/apply`, {
        method: 'POST', headers: jsonH, body: JSON.stringify({ message_id: messageId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not apply this draft');
      setSummary(data.ai_summary || '');
      if (data.ai_transcript) setTranscript(data.ai_transcript);
      setConcept(prev => prev ? { ...prev, pipeline_status: data.pipeline_status, ai_summary: data.ai_summary, ai_transcript: data.ai_transcript } : prev);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setApplyingId(null);
    }
  }

  // Sequential init: load concept → then PDF (needs chapter_ref from concept)
  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }

    (async () => {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, { headers: authH });
      if (res.ok) {
        const d: ConceptDetail = await res.json();
        setConcept(d);
        setSummary(d.ai_summary || d.content_text || '');
        setTranscript(d.ai_transcript || '');
        if (d.pipeline_status === 'summarizing') setPipelinePolling(true);
        loadPdf(d.chapter_ref);
      }
      setLoading(false);
    })();

    return () => { if (pdfRef.current) URL.revokeObjectURL(pdfRef.current); };
  }, [user, conceptId]);

  // Load assets when Assets tab first opens
  useEffect(() => {
    if (activeTab === 'assets' && !assetsLoaded) loadAssets();
  }, [activeTab, assetsLoaded]);

  // Load resources when Resources tab first opens
  useEffect(() => {
    if (activeTab === 'resources' && !resourcesLoaded) loadResources();
  }, [activeTab, resourcesLoaded]);

  // Load the authoring chat when Summary tab first opens
  useEffect(() => {
    if (activeTab === 'summary' && !chatLoaded) loadChat();
  }, [activeTab, chatLoaded]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMsgs]);

  // Poll while pipeline summary is generating
  useEffect(() => {
    if (!pipelinePolling) return;
    const iv = setInterval(async () => {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, { headers: authH });
      if (!res.ok) return;
      const d: ConceptDetail = await res.json();
      if (d.pipeline_status !== 'summarizing') {
        setConcept(d); setSummary(d.ai_summary || ''); setTranscript(d.ai_transcript || '');
        setPipelinePolling(false);
      }
    }, 3000);
    return () => clearInterval(iv);
  }, [pipelinePolling, conceptId, token]);

  // Poll while any asset is generating
  useEffect(() => {
    if (!assetPolling) return;
    const iv = setInterval(async () => {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/assets`, { headers: authH });
      if (!res.ok) return;
      const d: Assets = await res.json();
      setAssets(d);
      const anyGen = d.quiz_status === 'generating' || d.flashcard_status === 'generating'
        || d.audio_status === 'generating' || d.video_status === 'generating';
      if (!anyGen) {
        setAssetPolling(false);
        setGeneratingQuiz(false); setGeneratingCards(false);
        setGeneratingAudio(false); setGeneratingVideo(false);
      }
    }, 3000);
    return () => clearInterval(iv);
  }, [assetPolling, conceptId, token]);

  async function generateExplanation() {
    const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/summarize`, {
      method: 'POST', headers: authH,
    });
    const data = await res.json();
    if (!res.ok) { alert(data.detail || 'Could not generate an explanation'); return; }
    setConcept(prev => prev ? { ...prev, pipeline_status: 'summarizing' } : prev);
    setPipelinePolling(true);
  }

  async function saveSummary() {
    setSavingSum(true); setSavedSum(false);
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, {
      method: 'PATCH', headers: jsonH, body: JSON.stringify({ ai_summary: summary }),
    });
    setSavedSum(true); setSavingSum(false);
    setTimeout(() => setSavedSum(false), 2000);
  }

  async function saveTranscript() {
    setSavingTr(true); setSavedTr(false);
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, {
      method: 'PATCH', headers: jsonH, body: JSON.stringify({ ai_transcript: transcript }),
    });
    setSavedTr(true); setSavingTr(false);
    setTimeout(() => setSavedTr(false), 2000);
  }

  async function approveConcept() {
    setApproving(true);
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, {
      method: 'PATCH', headers: jsonH,
      body: JSON.stringify({ ai_summary: summary, ai_transcript: transcript, approve: true }),
    });
    setConcept(prev => prev ? { ...prev, pipeline_status: 'approved' } : prev);
    setApproving(false);
  }

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files?.length) return;
    setUploading(true);
    for (const file of Array.from(files)) {
      const fd = new FormData(); fd.append('file', file);
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/images`, {
        method: 'POST', headers: authH, body: fd,
      });
      if (res.ok) {
        const img: ConceptImage = await res.json();
        setConcept(prev => prev ? { ...prev, images: [...prev.images, img] } : prev);
      }
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function updateCaption(imgId: string, caption: string) {
    setConcept(prev => prev ? { ...prev, images: prev.images.map(i => i.id === imgId ? { ...i, caption } : i) } : prev);
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/images/${imgId}`, {
      method: 'PATCH', headers: jsonH, body: JSON.stringify({ caption }),
    });
  }

  async function deleteImage(imgId: string) {
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/images/${imgId}`, { method: 'DELETE', headers: authH });
    setConcept(prev => prev ? { ...prev, images: prev.images.filter(i => i.id !== imgId) } : prev);
  }

  async function triggerGenerate(type: 'quiz' | 'flashcards' | 'audio' | 'video') {
    if (type === 'quiz')       setGeneratingQuiz(true);
    if (type === 'flashcards') setGeneratingCards(true);
    if (type === 'audio')      setGeneratingAudio(true);
    if (type === 'video')      setGeneratingVideo(true);
    const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/generate/${type}`, {
      method: 'POST', headers: authH,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Generation failed' }));
      alert(err.detail || 'Failed to start generation');
      if (type === 'quiz')       setGeneratingQuiz(false);
      if (type === 'flashcards') setGeneratingCards(false);
      if (type === 'audio')      setGeneratingAudio(false);
      if (type === 'video')      setGeneratingVideo(false);
      return;
    }
    setAssetPolling(true);
    await loadAssets();
  }

  async function clearAsset(type: 'quiz' | 'flashcards') {
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/${type}`, { method: 'DELETE', headers: authH });
    await loadAssets();
  }

  async function approveAsset(type: 'quiz' | 'flashcards' | 'audio' | 'video') {
    setApprovingA(prev => ({ ...prev, [type]: true }));
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/assets/approve`, {
      method: 'POST', headers: jsonH, body: JSON.stringify({ [type]: true }),
    });
    setAssets(prev => prev ? { ...prev, [`${type}_status`]: 'approved' as AssetStatus } : prev);
    setApprovingA(prev => ({ ...prev, [type]: false }));
  }

  if (loading) return (
    <div className="h-full flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );
  if (!concept) return null;

  const status      = concept.pipeline_status;
  const isGenerating = status === 'summarizing';
  const isApproved   = status === 'approved';
  const hasPipeline  = status !== 'draft';
  const wordCount    = transcript.trim().split(/\s+/).filter(Boolean).length;
  const hasAISrc     = !!(concept.ai_summary || concept.source_text);

  return (
    <div className="h-full flex overflow-hidden">

      {/* ── Left panel: Chapter PDF ── */}
      <div className={`border-r border-[var(--bd)] flex flex-col overflow-hidden transition-all duration-200 ${showLeft ? 'w-2/5' : 'w-0'}`}>
        {showLeft && (
          pdfUrl
            ? <iframe src={pdfUrl} className="flex-1 w-full" title="Chapter PDF" />
            : <div className="flex-1 flex flex-col items-center justify-center gap-2 text-[var(--tx7)]">
                {!pdfReady
                  ? <Loader2 size={20} className="animate-spin text-purple-400" />
                  : <>
                      <FileText size={28} />
                      <p className="text-sm">{t.teacher.noPdfAvailable}</p>
                      <p className="text-xs text-[var(--tx8)] text-center px-4">
                        {t.teacher.pdfStoredNote}
                      </p>
                    </>}
              </div>
        )}
      </div>

      {/* ── Right panel ── */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 max-w-2xl mx-auto">

          {/* Nav */}
          <div className="flex items-center justify-between mb-5">
            <button onClick={() => router.push(`/teacher/courses/${courseId}`)}
              className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm transition-colors">
              <ArrowLeft size={15} /> {t.teacher.backToCourse}
            </button>
            <div className="flex items-center gap-2">
              {concept.chapter_ref && (
                <button
                  onClick={() => router.push(`/teacher/courses/${courseId}/chapters/${concept.chapter_ref}/studio`)}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-purple-500/30
                             text-purple-400 hover:bg-purple-500/10 transition-all"
                >
                  <Sparkles size={12} /> Studio
                </button>
              )}
              <button onClick={() => setShowLeft(p => !p)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-[var(--ov1)] hover:bg-[var(--ov2)] text-[var(--tx3)] transition-colors">
                <BookOpen size={13} />{showLeft ? t.teacher.hidePanel : t.teacher.showPanel}
              </button>
            </div>
          </div>

          {/* Title + pipeline badge */}
          <div className="mb-5">
            <h1 className="text-[var(--tx1)] text-xl font-bold">{concept.title}</h1>
            {concept.description && <p className="text-[var(--tx6)] text-sm mt-0.5">{concept.description}</p>}
            {hasPipeline && (
              <span className={`inline-flex items-center gap-1.5 mt-2 text-xs px-2.5 py-1 rounded-full font-medium ${
                isApproved   ? 'bg-green-500/15 text-green-400' :
                isGenerating ? 'bg-amber-500/15 text-amber-400' :
                status === 'failed' ? 'bg-red-500/15 text-red-400' :
                'bg-blue-500/15 text-blue-400'
              }`}>
                {isGenerating && <Loader2 size={10} className="animate-spin" />}
                {isApproved   && <CheckCircle size={10} />}
                {status === 'ready' && <Circle size={10} className="fill-blue-400" />}
                {PIPELINE_LABEL[status]}
              </span>
            )}
          </div>

          {/* Tab bar */}
          <div className="flex gap-1 border-b border-[var(--bd)] mb-6 overflow-x-auto">
            {([
              ['summary',    t.teacher.tabSummary,    BookOpen],
              ['transcript', t.teacher.tabTranscript, Mic2],
              ['resources',  t.teacher.tabResources,  ImageIcon],
              ['assets',     t.teacher.tabAssets,     Zap],
              ['textbook',   'Textbook',              LayoutList],
            ] as [Tab, string, React.ComponentType<{ size: number }>][]).map(([tabId, label, Icon]) => (
              <button key={tabId} onClick={() => setActiveTab(tabId)}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 -mb-px whitespace-nowrap transition-colors ${
                  activeTab === tabId ? 'text-purple-400 border-purple-400' : 'text-[var(--tx7)] border-transparent hover:text-[var(--tx3)]'
                }`}>
                <Icon size={12} />{label}
              </button>
            ))}
          </div>

          {/* ── Summary ── */}
          {activeTab === 'summary' && (
            <div>
              {isGenerating ? (
                <div className="flex flex-col items-center gap-3 py-16 text-[var(--tx7)]">
                  <Loader2 size={28} className="text-purple-400 animate-spin" />
                  <p className="text-sm">{t.teacher.aiWritingSummary}</p>
                  <p className="text-xs text-[var(--tx8)]">{t.teacher.generatingEstimate}</p>
                </div>
              ) : (
                <>
                  {status === 'failed' && (
                    <div className="flex items-center gap-2 text-red-400 text-sm mb-4">
                      <AlertCircle size={14} /> {t.teacher.conceptGenFailed}
                    </div>
                  )}

                  {/* ── Authoring chat (teacher-only) ── */}
                  <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl mb-5 overflow-hidden">
                    <div className="px-4 py-2.5 border-b border-[var(--bd)] flex items-center gap-1.5">
                      <Sparkles size={12} className="text-purple-400" />
                      <p className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider">{t.teacher.draftWithAI}</p>
                      <span className="text-[var(--tx8)] text-[10px]">{t.teacher.teacherOnlyNote}</span>
                    </div>

                    <div className="max-h-80 overflow-y-auto px-4 py-3 space-y-3">
                      {!chatLoaded ? (
                        <div className="flex justify-center py-6"><Loader2 size={16} className="animate-spin text-[var(--tx7)]" /></div>
                      ) : chatMsgs.length === 0 ? (
                        <p className="text-[var(--tx7)] text-xs py-2">
                          Ask AI to draft a summary and transcript, request changes ("add 2 more examples"),
                          or give it style instructions — it can see the concept's source text{concept.images.length > 0 ? ' and image' : ''}.
                        </p>
                      ) : (
                        chatMsgs.map(m => (
                          <div key={m.id} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                            <div className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm ${
                              m.role === 'user'
                                ? 'bg-purple-600 text-white whitespace-pre-wrap'
                                : 'bg-[var(--ov1)] text-[var(--tx2)] border border-[var(--bd)]'
                            }`}>
                              {m.role === 'assistant' ? (
                                <div className="ai-content leading-relaxed [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0">
                                  <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                    {preprocessMath(m.content)}
                                  </ReactMarkdown>
                                </div>
                              ) : m.content}
                              {m.role === 'assistant' && /SUMMARY/i.test(m.content) && (
                                <div className="mt-2 pt-2 border-t border-[var(--bd)]">
                                  <button onClick={() => applyChatMessage(m.id)} disabled={applyingId === m.id}
                                    className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg bg-purple-600/15 hover:bg-purple-600/25
                                               text-purple-400 transition-all disabled:opacity-50">
                                    {applyingId === m.id ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                                    {t.teacher.useAsDraft}
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                      {chatSending && (
                        <div className="flex justify-start">
                          <div className="bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-3.5 py-2.5">
                            <Loader2 size={13} className="animate-spin text-[var(--tx7)]" />
                          </div>
                        </div>
                      )}
                      <div ref={chatEndRef} />
                    </div>

                    <form onSubmit={e => { e.preventDefault(); sendChatMessage(); }}
                      className="flex gap-2 px-3 py-2.5 border-t border-[var(--bd)]">
                      <input value={chatInput} onChange={e => setChatInput(e.target.value)}
                        placeholder={t.teacher.chatPlaceholder}
                        disabled={chatSending}
                        className="flex-1 bg-[var(--ov1)] border border-[var(--bd)] rounded-lg px-3 py-1.5
                                   text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors" />
                      <button type="submit" disabled={chatSending || !chatInput.trim()}
                        className="flex items-center justify-center w-8 h-8 rounded-lg bg-purple-600 hover:bg-purple-500
                                   text-white transition-all disabled:opacity-40 shrink-0">
                        <Send size={13} />
                      </button>
                    </form>
                  </div>

                  <div className="flex items-center justify-between mb-2">
                    <label className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider">
                      {hasPipeline ? t.teacher.summaryLabel : t.teacher.summaryForStudents}
                    </label>
                    {!hasPipeline && concept.source_text && (
                      <button onClick={generateExplanation}
                        className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-[var(--bd)]
                                   text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all">
                        <Zap size={11} /> {t.teacher.generateExplanation}
                      </button>
                    )}
                  </div>
                  <textarea value={summary} onChange={e => setSummary(e.target.value)}
                    placeholder={t.teacher.explanationPlaceholder} rows={12}
                    className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-3
                               text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60 resize-y transition-colors leading-relaxed" />
                  <div className="flex items-center gap-3 mt-3">
                    <button onClick={saveSummary} disabled={savingSum}
                      className="flex items-center gap-2 px-4 py-2 bg-[var(--ov2)] hover:bg-[var(--ov3)] text-[var(--tx2)] text-sm rounded-xl transition-all disabled:opacity-40">
                      {savingSum ? <Loader2 size={13} className="animate-spin" /> : savedSum ? <Check size={13} className="text-green-400" /> : null}
                      {savingSum ? t.saving : savedSum ? t.saved : t.save}
                    </button>
                    {!isApproved && (
                      <button onClick={approveConcept} disabled={approving}
                        className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm font-medium rounded-xl transition-all disabled:opacity-40">
                        {approving ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle size={13} />}
                        {approving ? t.teacher.approving : t.teacher.approveConcept}
                      </button>
                    )}
                    {isApproved && <span className="flex items-center gap-1.5 text-green-400 text-sm"><CheckCircle size={14} /> {t.teacher.approvedBadge}</span>}
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── Transcript ── */}
          {activeTab === 'transcript' && (
            <div>
              {isGenerating ? (
                <div className="flex flex-col items-center gap-3 py-16 text-[var(--tx7)]">
                  <Loader2 size={28} className="text-purple-400 animate-spin" />
                  <p className="text-sm">{t.teacher.aiWritingTranscript}</p>
                </div>
              ) : (
                <>
                  <label className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider block mb-2">
                    {t.teacher.transcriptLabel}
                  </label>
                  <textarea value={transcript} onChange={e => setTranscript(e.target.value)}
                    placeholder={t.teacher.transcriptPlaceholder} rows={14}
                    className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-3
                               text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60 resize-y transition-colors leading-relaxed font-mono" />
                  <div className="flex items-center justify-between mt-2">
                    <p className="text-[var(--tx8)] text-xs">{tF(t.teacher.wordCount, { n: wordCount, min: Math.round(wordCount / 130) })}</p>
                    <button onClick={saveTranscript} disabled={savingTr}
                      className="flex items-center gap-2 px-4 py-2 bg-[var(--ov2)] hover:bg-[var(--ov3)] text-[var(--tx2)] text-sm rounded-xl transition-all disabled:opacity-40">
                      {savingTr ? <Loader2 size={13} className="animate-spin" /> : savedTr ? <Check size={13} className="text-green-400" /> : null}
                      {savingTr ? t.saving : savedTr ? t.saved : t.save}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── Resources ── */}
          {activeTab === 'resources' && (
            <div>
              {/* Upload bar */}
              <div className="flex items-center gap-2 mb-4 flex-wrap">
                <button onClick={() => resFileRef.current?.click()} disabled={uploadingRes}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-[var(--ov1)] hover:bg-[var(--ov2)] text-[var(--tx3)] transition-colors disabled:opacity-40">
                  {uploadingRes ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />} {t.teacher.uploadImagePdf}
                </button>
                <input ref={resFileRef} type="file" accept="image/*,application/pdf" multiple className="hidden"
                  onChange={e => uploadResourceFile(e.target.files)} />
                <button onClick={() => setShowVideoForm(v => !v)}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-[var(--ov1)] hover:bg-[var(--ov2)] text-[var(--tx3)] transition-colors">
                  <Plus size={12} /> {t.teacher.addVideoUrl}
                </button>
              </div>

              {/* Video URL form */}
              {showVideoForm && (
                <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl p-4 mb-4 space-y-2">
                  <input value={videoTitleInput} onChange={e => setVideoTitleInput(e.target.value)}
                    placeholder={t.teacher.titleOptional}
                    className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-lg px-3 py-2 text-sm text-[var(--tx1)] placeholder:text-[var(--tx8)] outline-none focus:border-purple-500" />
                  <div className="flex gap-2">
                    <input value={videoUrlInput} onChange={e => setVideoUrlInput(e.target.value)}
                      placeholder={t.teacher.videoUrlPlaceholder}
                      className="flex-1 bg-[var(--ov1)] border border-[var(--bd)] rounded-lg px-3 py-2 text-sm text-[var(--tx1)] placeholder:text-[var(--tx8)] outline-none focus:border-purple-500" />
                    <button onClick={addVideoResource} disabled={addingVideo || !videoUrlInput.trim()}
                      className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-lg transition-colors disabled:opacity-40">
                      {addingVideo ? <Loader2 size={14} className="animate-spin" /> : t.teacher.addBtn}
                    </button>
                  </div>
                </div>
              )}

              {!resourcesLoaded ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 size={22} className="text-purple-400 animate-spin" />
                </div>
              ) : resources.length === 0 ? (
                <div className="border border-dashed border-[var(--bd)] rounded-xl p-10 text-center">
                  <ImageIcon size={24} className="text-[var(--tx8)] mx-auto mb-2" />
                  <p className="text-[var(--tx7)] text-sm">{t.teacher.noResourcesYet}</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {resources.map(r => (
                    <div key={r.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
                      {r.type === 'image' && r.file_url && (
                        <div className="relative aspect-video bg-[var(--ov2)]">
                          <img src={`${API_BASE}${r.file_url}`} alt={r.title} className="w-full h-full object-contain" />
                        </div>
                      )}
                      {r.type === 'pdf' && (
                        <div className="flex items-center gap-3 px-4 py-3 bg-[var(--ov1)]">
                          <FileText size={20} className="text-purple-400 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-[var(--tx1)] font-medium truncate">{r.title}</p>
                            {r.text_extracted === false ? (
                              <p className="text-xs text-amber-400">{t.teacher.scannedPdf}</p>
                            ) : (
                              <p className="text-xs text-[var(--tx7)]">{t.teacher.pdfExtracted}</p>
                            )}
                          </div>
                          {r.file_url && (
                            <a href={`${API_BASE}${r.file_url}`} target="_blank" rel="noreferrer"
                              className="text-xs text-purple-400 hover:text-purple-300 shrink-0">Preview</a>
                          )}
                        </div>
                      )}
                      {r.type === 'video' && (
                        <div className="flex items-center gap-3 px-4 py-3 bg-[var(--ov1)]">
                          <Video size={20} className="text-purple-400 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-[var(--tx1)] font-medium truncate">{r.title}</p>
                            <p className="text-xs text-[var(--tx7)] truncate">{r.video_url}</p>
                          </div>
                          {r.video_url && (
                            <a href={r.video_url} target="_blank" rel="noreferrer"
                              className="text-xs text-purple-400 hover:text-purple-300 shrink-0">Open</a>
                          )}
                        </div>
                      )}
                      <div className="flex items-center justify-between px-3 py-2 border-t border-[var(--bd)]">
                        <p className="text-xs text-[var(--tx6)] truncate">{r.title}</p>
                        <button onClick={() => deleteResource(r.id)}
                          className="p-1 text-[var(--tx8)] hover:text-red-400 transition-colors shrink-0">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Assets ── */}
          {activeTab === 'assets' && (
            <div className="space-y-4">
              {!assetsLoaded ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 size={24} className="text-purple-400 animate-spin" />
                </div>
              ) : assets ? (
                <>
                  <AssetSection
                    title={t.teacher.assetQuiz} icon={<HelpCircle size={14} />}
                    status={assets.quiz_status}
                    isGenerating={generatingQuiz || assets.quiz_status === 'generating'}
                    canGenerate={hasAISrc} canApprove={assets.quiz_status === 'ready'}
                    approving={!!approvingA['quiz']}
                    onGenerate={() => triggerGenerate('quiz')}
                    onApprove={() => approveAsset('quiz')}
                    onClear={() => clearAsset('quiz')}
                  >
                    {assets.quiz.length > 0 && assets.quiz_status !== 'generating' && (
                      <div className="space-y-3 mt-3 px-4 pb-4">
                        {assets.quiz.map((q, qi) => (
                          <div key={q.id} className="bg-[var(--ov1)] border border-[var(--bd)] rounded-xl p-4">
                            <p className="text-[var(--tx1)] text-sm font-medium mb-2">{qi + 1}. <MathText inline>{q.question}</MathText></p>
                            <ul className="space-y-1">
                              {q.options.map((opt, oi) => (
                                <li key={oi} className={`text-xs px-3 py-1.5 rounded-lg ${
                                  oi === q.correct_idx ? 'bg-green-500/15 text-green-400 font-medium' : 'text-[var(--tx6)]'
                                }`}>
                                  {String.fromCharCode(65 + oi)}. <MathText inline>{opt}</MathText>
                                </li>
                              ))}
                            </ul>
                            {q.explanation && (
                              <p className="text-[var(--tx7)] text-xs mt-2 pt-2 border-t border-[var(--bd)]">
                                <span>💡 </span><MathText inline>{q.explanation}</MathText>
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </AssetSection>

                  <AssetSection
                    title={t.teacher.assetFlashcards} icon={<Layers size={14} />}
                    status={assets.flashcard_status}
                    isGenerating={generatingCards || assets.flashcard_status === 'generating'}
                    canGenerate={hasAISrc} canApprove={assets.flashcard_status === 'ready'}
                    approving={!!approvingA['flashcards']}
                    onGenerate={() => triggerGenerate('flashcards')}
                    onApprove={() => approveAsset('flashcards')}
                    onClear={() => clearAsset('flashcards')}
                  >
                    {assets.flashcards.length > 0 && assets.flashcard_status !== 'generating' && (
                      <div className="grid grid-cols-2 gap-2 mt-3 px-4 pb-4">
                        {assets.flashcards.map(card => (
                          <div key={card.id} className="bg-[var(--ov1)] border border-[var(--bd)] rounded-xl p-3">
                            <p className="text-[var(--tx1)] text-xs font-semibold mb-1"><MathText inline>{card.front}</MathText></p>
                            <p className="text-[var(--tx6)] text-xs leading-relaxed"><MathText inline>{card.back}</MathText></p>
                          </div>
                        ))}
                      </div>
                    )}
                  </AssetSection>

                  <AssetSection
                    title={t.teacher.assetAudio} icon={<Volume2 size={14} />}
                    status={assets.audio_status}
                    isGenerating={generatingAudio || assets.audio_status === 'generating'}
                    canGenerate={!!(concept.ai_transcript || concept.ai_summary)}
                    canApprove={assets.audio_status === 'ready'}
                    approving={!!approvingA['audio']}
                    onGenerate={() => triggerGenerate('audio')}
                    onApprove={() => approveAsset('audio')}
                    noReset
                  >
                    {assets.audio_url && assets.audio_status !== 'generating' && (
                      <div className="px-4 pb-4 mt-3">
                        <div className="bg-[var(--ov1)] border border-[var(--bd)] rounded-xl p-4">
                          <audio controls src={`${API_BASE}${assets.audio_url}`} className="w-full" />
                          {assets.audio_duration_sec && (
                            <p className="text-[var(--tx8)] text-xs mt-1.5">{tF(t.teacher.audioFromTranscript, { min: Math.round(assets.audio_duration_sec / 60) })}</p>
                          )}
                        </div>
                      </div>
                    )}
                  </AssetSection>

                  <AssetSection
                    title={t.teacher.assetVideo} icon={<Video size={14} />}
                    status={assets.video_status}
                    isGenerating={generatingVideo || assets.video_status === 'generating'}
                    canGenerate={!!(concept.ai_transcript || concept.ai_summary)}
                    canApprove={assets.video_status === 'ready'}
                    approving={!!approvingA['video']}
                    onGenerate={() => triggerGenerate('video')}
                    onApprove={() => approveAsset('video')}
                    noReset
                    hint={!(concept.ai_transcript || concept.ai_summary) ? t.teacher.generateNeedsSummary : undefined}
                  >
                    {assets.video_status === 'generating' && (
                      <div className="px-4 pb-4 mt-3">
                        <p className="text-[var(--tx7)] text-xs">
                          {(assets.video_stage && VIDEO_STAGE_LABEL[assets.video_stage]) || t.teacher.videoGenerating}
                        </p>
                      </div>
                    )}
                    {assets.video_url && assets.video_status !== 'generating' && (
                      <div className="px-4 pb-4 mt-3">
                        <div className="bg-[var(--ov1)] border border-[var(--bd)] rounded-xl overflow-hidden">
                          <video controls src={`${API_BASE}${assets.video_url}`} className="w-full aspect-video" />
                        </div>
                        <p className="text-[var(--tx8)] text-xs mt-2">
                          {t.teacher.animatedWithManim}
                        </p>
                      </div>
                    )}
                    {assets.video_status === 'failed' && assets.video_error && (
                      <div className="px-4 pb-4 mt-3">
                        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3">
                          <p className="text-red-400 text-xs font-mono break-words">{assets.video_error}</p>
                        </div>
                      </div>
                    )}
                  </AssetSection>
                </>
              ) : null}
            </div>
          )}

          {/* ── Textbook blocks ── */}
          {activeTab === 'textbook' && (
            <div>
              <p className="text-[var(--tx6)] text-xs mb-4">
                Content blocks are shown to students as an ordered textbook page. Use Studio chat to generate them, or save explanations directly.
              </p>
              <ConceptTextbook
                conceptId={conceptId}
                token={token!}
                editable
              />
            </div>
          )}

          {/* ── Study Set ── */}
        </div>
      </div>
    </div>
  );
}

// ── AssetSection helper ───────────────────────────────────────────────────────

function AssetSection({
  title, icon, status, isGenerating, canGenerate, canApprove, approving, noReset, hint,
  onGenerate, onApprove, onClear, children,
}: {
  title: string; icon: React.ReactNode;
  status: AssetStatus; isGenerating: boolean; canGenerate: boolean;
  canApprove: boolean; approving: boolean; noReset?: boolean; hint?: string;
  onGenerate: () => void; onApprove: () => void; onClear?: () => void;
  children?: React.ReactNode;
}) {
  const { t, tF } = useTranslation();

  const ASSET_BADGE: Record<AssetStatus, { label: string; cls: string }> = {
    none:       { label: t.teacher.assetNotGenerated, cls: 'bg-[var(--ov2)] text-[var(--tx7)]' },
    generating: { label: t.teacher.assetGenerating,  cls: 'bg-amber-500/15 text-amber-400' },
    ready:      { label: t.teacher.assetReadyReview,  cls: 'bg-blue-500/15 text-blue-400' },
    approved:   { label: t.teacher.assetApproved,     cls: 'bg-green-500/15 text-green-400' },
    failed:     { label: t.teacher.assetFailed,       cls: 'bg-red-500/15 text-red-400' },
  };

  const badge      = ASSET_BADGE[status];
  const isApproved = status === 'approved';
  const hasContent = status !== 'none';

  return (
    <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--bd)]">
        <div className="flex items-center gap-2">
          <span className="text-[var(--tx3)]">{icon}</span>
          <span className="text-[var(--tx1)] text-sm font-semibold">{title}</span>
          <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${badge.cls}`}>
            {isGenerating && <Loader2 size={9} className="animate-spin" />}
            {badge.label}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {canApprove && !isApproved && (
            <button onClick={onApprove} disabled={approving}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-all disabled:opacity-40">
              {approving ? <Loader2 size={9} className="animate-spin" /> : <CheckCircle size={9} />}
              {t.teacher.approveBtn}
            </button>
          )}
          {isApproved && (
            <span className="flex items-center gap-1 text-green-400 text-xs font-medium">
              <CheckCircle size={10} /> {t.teacher.assetApproved}
            </span>
          )}
          {!noReset && hasContent && !isGenerating && (
            <button onClick={onClear}
              className="p-1.5 text-[var(--tx7)] hover:text-red-400 rounded-lg transition-colors" title="Clear and regenerate">
              <Trash2 size={11} />
            </button>
          )}
          {(!hasContent || status === 'failed') && !isGenerating && (
            <button onClick={onGenerate} disabled={!canGenerate}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              title={!canGenerate ? (hint ?? undefined) : undefined}>
              <Zap size={10} /> {t.teacher.generateBtn}
            </button>
          )}
          {(status === 'ready' || isApproved) && !isGenerating && (
            <button onClick={onGenerate} disabled={!canGenerate}
              className="flex items-center gap-1 text-xs px-2.5 py-1.5 text-[var(--tx7)] hover:text-purple-400 rounded-lg transition-colors">
              <RefreshCw size={10} /> {t.teacher.redoBtn}
            </button>
          )}
        </div>
      </div>

      {isGenerating && (
        <div className="flex items-center justify-center gap-2 py-8 text-[var(--tx7)]">
          <Loader2 size={16} className="text-purple-400 animate-spin" />
          <span className="text-sm">{t.teacher.assetGenerating}</span>
        </div>
      )}

      {!isGenerating && status === 'none' && (
        <div className="px-4 py-6 text-center text-[var(--tx8)] text-xs">
          {hint || (canGenerate ? tF(t.teacher.generatePrompt, { asset: title.toLowerCase() }) : t.teacher.generateNeedsSummary)}
        </div>
      )}

      {!isGenerating && children}
    </div>
  );
}
