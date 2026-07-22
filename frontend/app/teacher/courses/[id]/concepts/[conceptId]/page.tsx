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
  Loader2, Check, Plus, FileText,
  CheckCircle, Zap, HelpCircle, Layers,
  RefreshCw, Volume2, Video, Send, LayoutList, Wand2, X,
} from 'lucide-react';
import { ConceptTextbook } from '@/components/course/ConceptTextbook';
import { StudyPDFPane, PinnedCtx } from '@/components/study/StudyPDFPane';
import { useSessionStore } from '@/store/sessionStore';
import { preprocessMath } from '@/lib/preprocessMath';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Tab            = 'studio' | 'textbook' | 'resources' | 'assets';
type ResourceType   = 'image' | 'pdf' | 'video';
interface Resource  { id: string; type: ResourceType; title: string; mime_type?: string; video_url?: string; file_url?: string; position: number; text_extracted?: boolean; }
type PipelineStatus = 'draft' | 'summarizing' | 'ready' | 'approved' | 'failed';
type AssetStatus    = 'none' | 'generating' | 'ready' | 'approved' | 'failed';

interface ConceptImage { id: string; url: string; caption: string; }
interface QuizQuestion { id: string; question: string; options: string[]; correct_idx: number; explanation: string; }
interface Flashcard    { id: string; front: string; back: string; }
interface ChatMsg      { id: string; role: 'user' | 'assistant'; content: string; suggestions?: string[]; created_at: string; }

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
  audio_url?: string; video_url?: string; video_job_id?: number;
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
  const [activeTab,  setActiveTab]  = useState<Tab>('studio');
  const [showLeft,   setShowLeft]   = useState(true);


  const [pdfFile,  setPdfFile]  = useState<File | null>(null);
  const [pdfReady, setPdfReady] = useState(false);
  const [pinnedCtx, setPinnedCtx] = useState<PinnedCtx | null>(null);

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
  const [generatingVideo,   setGeneratingVideo]   = useState(false);
  const [approvingA,        setApprovingA]        = useState<Record<string, boolean>>({});
  const [addingToTextbook,  setAddingToTextbook]  = useState<'video' | 'audio' | null>(null);
  const [addedToTextbook,   setAddedToTextbook]   = useState<Set<string>>(new Set());
  const [addingMsgBlock,    setAddingMsgBlock]    = useState<string | null>(null);
  const [addedMsgBlocks,    setAddedMsgBlocks]    = useState<Set<string>>(new Set());
  const [generatingVideoMsg, setGeneratingVideoMsg] = useState<string | null>(null);
  const [videoGeneratedMsgs, setVideoGeneratedMsgs] = useState<Set<string>>(new Set());

  const [assetPolling,    setAssetPolling]    = useState(false);

  // Authoring chat — teacher-only, never shown to students
  const [chatMsgs,    setChatMsgs]    = useState<ChatMsg[]>([]);
  const [chatLoaded,  setChatLoaded]  = useState(false);
  const [chatInput,   setChatInput]   = useState('');
  const [chatSending, setChatSending] = useState(false);
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
        setPdfFile(new File([blob], 'chapter.pdf', { type: 'application/pdf' }));
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

  async function sendChatMessage(override?: string, imageDataUrl?: string) {
    const message = (override ?? chatInput).trim();
    if (!message || chatSending) return;
    // Resolve image: explicit arg first, then pinned context
    const imgUrl = imageDataUrl ?? pinnedCtx?.imageDataUrl ?? undefined;
    // For text context, prepend to message
    const fullMessage = pinnedCtx?.text
      ? `[Page ${pinnedCtx.pageNum} context]\n${pinnedCtx.text}\n\n${message}`
      : message;
    setChatInput('');
    setPinnedCtx(null);
    setChatMsgs(prev => [...prev, { id: `local-${Date.now()}`, role: 'user', content: message, created_at: new Date().toISOString() }]);
    setChatSending(true);
    try {
      const body: Record<string, unknown> = { message: fullMessage };
      if (imgUrl) body.image_data_url = imgUrl;
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/concept-chat`, {
        method: 'POST', headers: jsonH, body: JSON.stringify(body),
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

  const STUDIO_PROMPTS = [
    { label: 'Write an explanation',     text: 'Write a clear, student-friendly explanation of this concept with 2 worked examples.' },
    { label: 'Draft audio script',       text: 'Write a natural-sounding narration script for audio. Keep it conversational, around 150 words.' },
    { label: 'Step-by-step walkthrough', text: 'Break this concept down into clear numbered steps a student can follow.' },
    { label: 'Short introduction',       text: 'Write a short introductory paragraph (3–4 sentences) that hooks the student and explains why this concept matters.' },
    { label: 'Add examples',             text: 'Add 2 more worked examples to the last explanation.' },
    { label: 'Simplify',                 text: 'Rewrite the last response in simpler language for a beginner.' },
    { label: 'Add an analogy',           text: 'Add a real-world analogy that makes this concept easier to grasp.' },
    { label: 'Make it shorter',          text: 'Make the explanation more concise without losing the key ideas.' },
    { label: 'Add a summary',            text: 'Add a 2-sentence summary at the end.' },
  ];

  async function addMsgToTextbook(messageId: string) {
    setAddingMsgBlock(messageId);
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/concept-chat/apply`, {
        method: 'POST', headers: jsonH, body: JSON.stringify({ message_id: messageId, action: 'block' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not add block');
      setAddedMsgBlocks(prev => new Set([...prev, messageId]));
    } catch (err: any) {
      alert(err.message);
    } finally {
      setAddingMsgBlock(null);
    }
  }

  async function addMsgAsVideo(messageId: string, content: string) {
    setGeneratingVideoMsg(messageId);
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/content-blocks/generate-video`, {
        method: 'POST', headers: jsonH,
        body: JSON.stringify({ title: (concept?.title ?? 'Concept') + ' — Video', transcript: content }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not start video generation');
      setVideoGeneratedMsgs(prev => new Set([...prev, messageId]));
    } catch (err: any) {
      alert(err.message);
    } finally {
      setGeneratingVideoMsg(null);
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
        loadPdf(d.chapter_ref);
      }
      setLoading(false);
    })();

  }, [user, conceptId]);

  // Load assets when Assets tab first opens
  useEffect(() => {
    if (activeTab === 'assets' && !assetsLoaded) loadAssets();
  }, [activeTab, assetsLoaded]);

  // Load resources when Resources tab first opens
  useEffect(() => {
    if (activeTab === 'resources' && !resourcesLoaded) loadResources();
  }, [activeTab, resourcesLoaded]);

  // Load the authoring chat when Studio tab first opens
  useEffect(() => {
    if (activeTab === 'studio' && !chatLoaded) loadChat();
  }, [activeTab, chatLoaded]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMsgs]);

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

  async function addVideoToTextbook() {
    if (!assets?.video_job_id) return;
    setAddingToTextbook('video');
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/content-blocks`, {
        method: 'POST', headers: jsonH,
        body: JSON.stringify({
          type:     'video',
          title:    (concept?.title ?? 'Concept') + ' — Video',
          video_id: assets.video_job_id,
        }),
      });
      if (res.ok) setAddedToTextbook(prev => new Set([...prev, 'video']));
    } catch { /* ignore */ } finally {
      setAddingToTextbook(null);
    }
  }

  async function addAudioToTextbook() {
    if (!assets?.audio_url) return;
    setAddingToTextbook('audio');
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/content-blocks`, {
        method: 'POST', headers: jsonH,
        body: JSON.stringify({
          type:  'audio',
          title: (concept?.title ?? 'Concept') + ' — Audio narration',
          body:  `${API_BASE}${assets.audio_url}`,
        }),
      });
      if (res.ok) setAddedToTextbook(prev => new Set([...prev, 'audio']));
    } catch { /* ignore */ } finally {
      setAddingToTextbook(null);
    }
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

  const hasAISrc = !!(concept.ai_summary || concept.source_text);

  return (
    <div className="h-full flex overflow-hidden">

      {/* ── Left panel: Chapter PDF ── */}
      <div className={`border-r border-[var(--bd)] flex flex-col overflow-hidden transition-all duration-200 ${showLeft ? 'w-2/5' : 'w-0'}`}>
        {showLeft && (
          pdfFile
            ? <StudyPDFPane
                file={pdfFile}
                onClose={() => setShowLeft(false)}
                onFire={(prompt, imageDataUrl) => {
                  setActiveTab('studio');
                  sendChatMessage(prompt, imageDataUrl);
                }}
                onPin={ctx => {
                  setPinnedCtx(ctx);
                  setActiveTab('studio');
                }}
              />
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
              <button onClick={() => setShowLeft(p => !p)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-[var(--ov1)] hover:bg-[var(--ov2)] text-[var(--tx3)] transition-colors">
                <BookOpen size={13} />{showLeft ? t.teacher.hidePanel : t.teacher.showPanel}
              </button>
            </div>
          </div>

          {/* Title */}
          <div className="mb-5">
            <h1 className="text-[var(--tx1)] text-xl font-bold">{concept.title}</h1>
            {concept.description && <p className="text-[var(--tx6)] text-sm mt-0.5">{concept.description}</p>}
          </div>

          {/* Tab bar */}
          <div className="flex gap-1 border-b border-[var(--bd)] mb-6 overflow-x-auto">
            {([
              ['studio',    'Studio',                 Wand2],
              ['textbook',  'Textbook',               LayoutList],
              ['resources', t.teacher.tabResources,   ImageIcon],
              ['assets',    t.teacher.tabAssets,      Zap],
            ] as [Tab, string, React.ComponentType<{ size: number }>][]).map(([tabId, label, Icon]) => (
              <button key={tabId} onClick={() => setActiveTab(tabId)}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 -mb-px whitespace-nowrap transition-colors ${
                  activeTab === tabId ? 'text-purple-400 border-purple-400' : 'text-[var(--tx7)] border-transparent hover:text-[var(--tx3)]'
                }`}>
                <Icon size={12} />{label}
              </button>
            ))}
          </div>

          {/* ── Studio ── */}
          {activeTab === 'studio' && (
            <div>
              <p className="text-[var(--tx6)] text-xs mb-4">
                Chat with AI to draft content for this concept. It sees the source text{concept.images.length > 0 ? ' and attached image' : ''}.
                Add AI responses directly to the Textbook, or silently set the summary / transcript for quiz and audio generation.
              </p>

              <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
                <div className="max-h-[60vh] overflow-y-auto px-4 py-3 space-y-3">
                  {!chatLoaded ? (
                    <div className="flex justify-center py-10"><Loader2 size={16} className="animate-spin text-[var(--tx7)]" /></div>
                  ) : chatMsgs.length === 0 ? (
                    <div className="flex flex-col items-center gap-3 py-10 text-center">
                      <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                        <Wand2 size={18} className="text-purple-400" />
                      </div>
                      <p className="text-[var(--tx3)] text-sm font-medium">What would you like to create?</p>
                    </div>
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
                          {m.role === 'assistant' && (
                            <div className="mt-2 pt-2 border-t border-[var(--bd)] space-y-2">
                              {/* Contextual follow-up chips generated by the AI */}
                              {m.suggestions && m.suggestions.length > 0 && (
                                <div className="flex flex-wrap gap-1.5">
                                  {m.suggestions.map((s, si) => (
                                    <button key={si} onClick={() => sendChatMessage(s)} disabled={chatSending}
                                      className="text-xs px-2.5 py-1 rounded-full
                                                 border border-[var(--bd)] bg-[var(--ov1)]
                                                 text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400
                                                 transition-colors disabled:opacity-40">
                                      {s}
                                    </button>
                                  ))}
                                </div>
                              )}
                              {/* Action pills */}
                              <div className="flex flex-wrap gap-1.5">
                                <button
                                  onClick={() => addMsgToTextbook(m.id)}
                                  disabled={addingMsgBlock === m.id || addedMsgBlocks.has(m.id)}
                                  className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg
                                             bg-purple-600/15 hover:bg-purple-600/25 text-purple-400
                                             transition-all disabled:opacity-50">
                                  {addingMsgBlock === m.id
                                    ? <Loader2 size={11} className="animate-spin" />
                                    : addedMsgBlocks.has(m.id) ? <Check size={11} /> : <LayoutList size={11} />}
                                  {addedMsgBlocks.has(m.id) ? 'Added' : '+ Textbook'}
                                </button>
                                <button
                                  onClick={() => addMsgAsVideo(m.id, m.content)}
                                  disabled={generatingVideoMsg === m.id || videoGeneratedMsgs.has(m.id)}
                                  title="Generate an animated video from this content and add it to Textbook"
                                  className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg
                                             bg-blue-600/15 hover:bg-blue-600/25 text-blue-400
                                             transition-all disabled:opacity-50">
                                  {generatingVideoMsg === m.id
                                    ? <Loader2 size={11} className="animate-spin" />
                                    : videoGeneratedMsgs.has(m.id) ? <Check size={11} /> : <Video size={11} />}
                                  {videoGeneratedMsgs.has(m.id) ? 'Generating…' : '+ Video'}
                                </button>
                              </div>
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

                {/* Marquee prompt chips — two rows, opposite directions, pause on hover */}
                <style>{`
                  @keyframes marquee-l { from { transform: translateX(0) } to { transform: translateX(-50%) } }
                  @keyframes marquee-r { from { transform: translateX(-50%) } to { transform: translateX(0) } }
                  .sc-track-l { animation: marquee-l 30s linear infinite; }
                  .sc-track-r { animation: marquee-r 36s linear infinite; }
                  .sc-wrap:hover .sc-track-l,
                  .sc-wrap:hover .sc-track-r { animation-play-state: paused; }
                `}</style>
                <div className="sc-wrap border-t border-[var(--bd)] py-2.5 overflow-hidden space-y-2">
                  {[STUDIO_PROMPTS.slice(0, 5), STUDIO_PROMPTS.slice(5)].map((row, ri) => (
                    <div key={ri} className="flex">
                      <div className={`flex gap-2 ${ri === 0 ? 'sc-track-l' : 'sc-track-r'}`}>
                        {[...row, ...row].map((p, i) => (
                          <button key={i} onClick={() => sendChatMessage(p.text)} disabled={chatSending}
                            className="shrink-0 px-3 py-1.5 rounded-full
                                       border border-[var(--bd)] bg-[var(--ov1)]
                                       text-[var(--tx6)] text-xs whitespace-nowrap
                                       hover:border-purple-500/50 hover:text-purple-400 hover:bg-purple-500/5
                                       transition-colors disabled:opacity-40 cursor-pointer">
                            {p.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Pinned PDF context preview */}
                {pinnedCtx && (
                  <div className="flex items-center gap-2 px-3 py-2 border-t border-[var(--bd)] bg-purple-500/5">
                    {pinnedCtx.imageDataUrl && (
                      <img src={pinnedCtx.imageDataUrl} alt="PDF clip"
                        className="h-10 w-16 object-cover rounded border border-[var(--bd)] shrink-0" />
                    )}
                    <span className="text-[11px] text-purple-400 flex-1 truncate">
                      {pinnedCtx.type === 'region' ? 'Region clip' : `Page ${pinnedCtx.pageNum}`}
                      {pinnedCtx.text && ` — ${pinnedCtx.text.slice(0, 60)}…`}
                    </span>
                    <button onClick={() => setPinnedCtx(null)}
                      className="text-[var(--tx8)] hover:text-red-400 transition-colors shrink-0 p-0.5">
                      <X size={12} />
                    </button>
                  </div>
                )}

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
                        <button
                          onClick={addAudioToTextbook}
                          disabled={!!addingToTextbook || addedToTextbook.has('audio')}
                          className="mt-2 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-[var(--bd)]
                                     text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all
                                     disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {addingToTextbook === 'audio' ? <Loader2 size={11} className="animate-spin" /> :
                           addedToTextbook.has('audio') ? <Check size={11} className="text-green-400" /> :
                           <LayoutList size={11} />}
                          {addedToTextbook.has('audio') ? 'Added to Textbook' : '→ Add to Textbook'}
                        </button>
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
                        <div className="flex items-center gap-3 mt-2">
                          <p className="text-[var(--tx8)] text-xs flex-1">{t.teacher.animatedWithManim}</p>
                          <button
                            onClick={addVideoToTextbook}
                            disabled={!!addingToTextbook || addedToTextbook.has('video')}
                            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-[var(--bd)]
                                       text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all
                                       disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
                          >
                            {addingToTextbook === 'video' ? <Loader2 size={11} className="animate-spin" /> :
                             addedToTextbook.has('video') ? <Check size={11} className="text-green-400" /> :
                             <LayoutList size={11} />}
                            {addedToTextbook.has('video') ? 'Added to Textbook' : '→ Add to Textbook'}
                          </button>
                        </div>
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

          {/* ── Textbook ── */}
          {activeTab === 'textbook' && (
            <div>
              <p className="text-[var(--tx6)] text-xs mb-4">
                Ordered content shown to students. Use Studio to draft and add blocks. Each text block can generate its own audio narration.
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
