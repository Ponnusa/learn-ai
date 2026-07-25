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
  RefreshCw, Volume2, Video, Send, LayoutList, Wand2, X, FileImage, Scissors,
  ChevronUp, ChevronDown, Shuffle, AlignJustify, Star, Paperclip,
} from 'lucide-react';
import { ConceptTextbook } from '@/components/course/ConceptTextbook';
import { PDFContextPicker } from '@/components/course/PDFContextPicker';
import { useSessionStore } from '@/store/sessionStore';
import { preprocessMath } from '@/lib/preprocessMath';
import { KATEX_OPTIONS } from '@/lib/mathConfig';
import { SmilesBlock } from '@/components/chat/SmilesBlock';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Tab            = 'studio' | 'textbook' | 'resources' | 'assets';
type ResourceType   = 'image' | 'pdf' | 'video';
interface Resource  { id: string; type: ResourceType; title: string; mime_type?: string; video_url?: string; file_url?: string; position: number; text_extracted?: boolean; }
type PipelineStatus = 'draft' | 'summarizing' | 'ready' | 'approved' | 'failed';
type AssetStatus    = 'none' | 'generating' | 'ready' | 'approved' | 'failed';

interface ConceptImage { id: string; url: string; caption: string; }
interface QuizQuestion {
  id: string; question: string; options: string[]; correct_idx: number;
  explanation: string; position: number;
  status: 'draft' | 'approved'; difficulty: 'easy' | 'medium' | 'hard';
}
interface Flashcard    { id: string; front: string; back: string; position: number; status: 'draft' | 'approved'; }
interface ChatMsg {
  id: string; role: 'user' | 'assistant'; content: string;
  suggestions?: string[]; created_at: string;
  images?: string[]; imagePages?: number[];
  videoBlockId?: string;
  videoSourceMsgId?: string;
  videoStatus?: string;
  videoUrl?: string;
  videoError?: string;
  videoId?: number;
  videoInTextbook?: boolean;
  inTextbook?: boolean;
  quizDraft?: boolean;
  quizCount?: number;
  flashcardDraft?: boolean;
  flashcardCount?: number;
}

interface ConceptDetail {
  id: string; title: string; description?: string;
  content_text?: string; study_set_id?: string; course_id: string;
  source_text?: string; ai_summary?: string; ai_transcript?: string;
  pipeline_status: PipelineStatus; approved_at?: string;
  chapter_ref?: string; page_start?: number;
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
  quiz_mode: 'ordered' | 'difficulty' | 'shuffle';
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


  const [pdfUrl,        setPdfUrl]        = useState<string | null>(null);
  const [pdfFile,       setPdfFile]       = useState<File | null>(null);
  const [pdfReady,      setPdfReady]      = useState(false);
  const [selectedPages, setSelectedPages] = useState<number[]>([]);
  const [pickerOpen,    setPickerOpen]    = useState(false);
  const [lightbox,      setLightbox]      = useState<{ url: string; page: number } | null>(null);
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
  const [approvingA,        setApprovingA]        = useState<Record<string, boolean>>({});
  const [addingToTextbook,  setAddingToTextbook]  = useState<'audio' | null>(null);
  const [addedToTextbook,   setAddedToTextbook]   = useState<Set<string>>(new Set());
  const [addingMsgBlock,    setAddingMsgBlock]    = useState<string | null>(null);

  // Resources → Textbook
  const [resAddedToTextbook,  setResAddedToTextbook]  = useState<Set<string>>(new Set());
  const [addingResToTextbook, setAddingResToTextbook] = useState<string | null>(null);

  // Studio chat attachment (Option A)
  const [pendingAttach,   setPendingAttach]   = useState<{ file: File; dataUrl: string; name: string } | null>(null);
  const chatAttachRef = useRef<HTMLInputElement>(null);
  // In-memory map: userMessageId → attachment so "Add to Resources" button can upload it
  const msgAttachMap  = useRef<Map<string, { dataUrl: string; file: File; name: string; mimeType: string }>>(new Map());
  const [attachAddedToRes, setAttachAddedToRes] = useState<Set<string>>(new Set());
  const [addingAttachToRes, setAddingAttachToRes] = useState<string | null>(null);
  const [addedMsgBlocks,    setAddedMsgBlocks]    = useState<Set<string>>(new Set());
  const [generatingVideoMsg, setGeneratingVideoMsg] = useState<string | null>(null);
  const videoPollingRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());
  const [removedVideoBlocks, setRemovedVideoBlocks] = useState<Set<string>>(new Set());
  const [retryingManimMsgs,  setRetryingManimMsgs]  = useState<Set<string>>(new Set());
  const [showDraftPrompt,   setShowDraftPrompt]   = useState(false);

  // Studio quiz/flashcard generation config
  const [quizConfigOpen,       setQuizConfigOpen]       = useState(false);
  const [flashcardConfigOpen,  setFlashcardConfigOpen]  = useState(false);
  const [quizDifficulty,       setQuizDifficulty]       = useState<'easy'|'medium'|'hard'|'mixed'>('mixed');
  const [quizStyle,            setQuizStyle]            = useState<'multiple_choice'|'true_false'|'mixed'>('multiple_choice');
  const [quizCount,            setQuizCount]            = useState(5);
  const [flashcardCount,       setFlashcardCount]       = useState(10);
  const [flashcardFocus,       setFlashcardFocus]       = useState<'definitions'|'examples'|'mixed'>('mixed');
  const [generatingStudioQuiz, setGeneratingStudioQuiz] = useState(false);
  const [generatingStudioCards,setGeneratingStudioCards]= useState(false);

  const [assetPolling,    setAssetPolling]    = useState(false);
  const [quizItemBusy,   setQuizItemBusy]   = useState<Set<string>>(new Set());
  const [cardItemBusy,   setCardItemBusy]   = useState<Set<string>>(new Set());
  const [approvingAllQ,  setApprovingAllQ]  = useState(false);
  const [approvingAllC,  setApprovingAllC]  = useState(false);

  // Authoring chat — teacher-only, never shown to students
  const [chatMsgs,    setChatMsgs]    = useState<ChatMsg[]>([]);
  const [chatLoaded,  setChatLoaded]  = useState(false);
  const [chatInput,   setChatInput]   = useState('');
  const [chatSending, setChatSending] = useState(false);
  const chatEndRef      = useRef<HTMLDivElement>(null);
  const chatSendingRef  = useRef(false);
  const rightPanelRef   = useRef<HTMLDivElement>(null);
  const renderedIdsRef  = useRef<Set<string>>(new Set());
  const autoStartedRef  = useRef(false);
  const [chatAtTop,    setChatAtTop]    = useState(true);
  const [chatAtBottom, setChatAtBottom] = useState(false);

  const authH = { Authorization: `Bearer ${token}` };
  const jsonH = { ...authH, 'Content-Type': 'application/json' };

  // Load PDF using chapter_ref if available, else fall back to course syllabus
  function handlePanelScroll() {
    const el = rightPanelRef.current;
    if (!el) return;
    setChatAtTop(el.scrollTop < 60);
    setChatAtBottom(el.scrollTop + el.clientHeight >= el.scrollHeight - 60);
  }

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
    if (res.ok) {
      const msgs: ChatMsg[] = await res.json();
      setChatMsgs(msgs);
      // Resume polling for any video that was still generating when the page last closed
      for (const m of msgs) {
        if (m.videoBlockId && m.videoStatus && m.videoStatus !== 'ready' && m.videoStatus !== 'failed') {
          startVideoPolling(m.videoBlockId, m.id);
        }
      }
    }
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

  async function renderSelectedPageUrls(pageNums: number[]): Promise<string[]> {
    if (!pdfFile || pageNums.length === 0 || !(window as any).pdfjsLib) return [];
    try {
      const doc = await (window as any).pdfjsLib.getDocument({ data: await pdfFile.arrayBuffer() }).promise;
      const urls: string[] = [];
      for (const n of pageNums) {
        const page = await doc.getPage(n);
        const dpr  = window.devicePixelRatio || 1;
        const vp   = page.getViewport({ scale: 1.8 * dpr });
        const c    = document.createElement('canvas');
        c.width = vp.width; c.height = vp.height;
        await page.render({ canvasContext: c.getContext('2d')!, viewport: vp }).promise;
        urls.push(c.toDataURL('image/jpeg', 0.88));
      }
      return urls;
    } catch { return []; }
  }

  async function sendChatMessage(override?: string) {
    const message = (override ?? chatInput).trim();
    if (!message || chatSendingRef.current) return;
    chatSendingRef.current = true;
    setChatSending(true);
    const pages  = selectedPages.slice();
    const attach = pendingAttach;
    setChatInput('');
    setSelectedPages([]);
    setPendingAttach(null);
    const localId = `local-${Date.now()}`;
    try {
      const imageDataUrls = await renderSelectedPageUrls(pages);
      // Include image attachment in vision call (images only; PDFs skipped for vision)
      const allImageUrls = attach?.file.type.startsWith('image/')
        ? [...imageDataUrls, attach.dataUrl]
        : imageDataUrls;

      setChatMsgs(prev => [...prev, {
        id: localId,
        role: 'user',
        content: message,
        images:     allImageUrls.length > 0 ? allImageUrls : undefined,
        imagePages: imageDataUrls.length > 0 ? pages : undefined,
        created_at: new Date().toISOString(),
      }]);

      // Store attachment data so "Add to Resources" can re-upload it
      if (attach) {
        msgAttachMap.current.set(localId, {
          dataUrl: attach.dataUrl, file: attach.file,
          name: attach.name, mimeType: attach.file.type,
        });
      }

      const body: Record<string, unknown> = { message };
      if (allImageUrls.length > 0) {
        body.image_data_urls = allImageUrls;
        body.image_page_nums = pages;
      }
      const res  = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/concept-chat`, {
        method: 'POST', headers: jsonH, body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not send message');
      // Re-key the attachment from localId to the real user message ID (backend now returns it)
      const realUserMsgId = data.user_message_id ?? localId;
      if (attach && msgAttachMap.current.has(localId)) {
        msgAttachMap.current.set(realUserMsgId, msgAttachMap.current.get(localId)!);
        msgAttachMap.current.delete(localId);
      }
      // Replace localId with the real user message ID; append the assistant response separately
      const { user_message_id: _uid, ...assistantMsg } = data;
      setChatMsgs(prev =>
        prev.map(m => m.id === localId ? { ...m, id: realUserMsgId } : m).concat(assistantMsg)
      );
    } catch (err: any) {
      alert(err.message);
    } finally {
      chatSendingRef.current = false;
      setChatSending(false);
    }
  }

  const STUDIO_PROMPTS = t.teacher.studioPrompts;

  async function addMsgToTextbook(messageId: string) {
    setAddingMsgBlock(messageId);
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/concept-chat/apply`, {
        method: 'POST', headers: jsonH, body: JSON.stringify({ message_id: messageId, action: 'block' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not add block');
      setAddedMsgBlocks(prev => new Set([...prev, messageId]));
      setChatMsgs(prev => prev.map(m => m.id === messageId ? { ...m, inTextbook: true } : m));
    } catch (err: any) {
      alert(err.message);
    } finally {
      setAddingMsgBlock(null);
    }
  }

  async function addMsgAndVideoToTextbook(messageId: string, videoBlockId: string) {
    setAddingMsgBlock(messageId);
    try {
      // 1. Create the text block(s) — appended at the end of the textbook
      const textRes = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/concept-chat/apply`, {
        method: 'POST', headers: jsonH, body: JSON.stringify({ message_id: messageId, action: 'block' }),
      });
      const textBlock = await textRes.json();
      if (!textRes.ok) throw new Error(textBlock.detail || 'Could not add block');
      setAddedMsgBlocks(prev => new Set([...prev, messageId]));
      setChatMsgs(prev => prev.map(m => m.id === messageId ? { ...m, inTextbook: true } : m));

      // 2. Mark the video block as in-textbook and move it to the end (after the text block(s))
      const vidRes = await fetch(
        `${API_BASE}/api/courses/concepts/${conceptId}/content-blocks/${videoBlockId}/add-to-textbook`,
        { method: 'POST', headers: authH },
      );
      if (vidRes.ok) {
        setChatMsgs(prev => prev.map(m =>
          m.videoBlockId === videoBlockId ? { ...m, videoInTextbook: true } : m
        ));
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      setAddingMsgBlock(null);
    }
  }

  function startVideoPolling(blockId: string, msgId: string) {
    if (videoPollingRef.current.has(blockId)) return;
    const iv = setInterval(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/courses/concepts/${conceptId}/content-blocks/${blockId}/status`,
          { headers: authH },
        );
        if (!res.ok) return;
        const d = await res.json();
        const done = d.video_url || d.video_status === 'failed';
        setChatMsgs(prev => prev.map(m => m.id === msgId ? {
          ...m,
          videoStatus: d.video_status,
          videoUrl:    d.video_url   || undefined,
          videoError:  d.video_error || undefined,
          videoId:     d.video_id    ?? m.videoId,
        } : m));
        if (done) {
          clearInterval(videoPollingRef.current.get(blockId));
          videoPollingRef.current.delete(blockId);
        }
      } catch { /* ignore */ }
    }, 5000);
    videoPollingRef.current.set(blockId, iv);
  }

  async function addMsgAsVideo(messageId: string) {
    setGeneratingVideoMsg(messageId);
    try {
      const res = await fetch(
        `${API_BASE}/api/courses/concepts/${conceptId}/concept-chat/${messageId}/generate-video`,
        { method: 'POST', headers: jsonH, body: JSON.stringify({ title: (concept?.title ?? 'Concept') + ' — Video' }) },
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not start video generation');
      setChatMsgs(prev => [...prev, data]);
      startVideoPolling(data.videoBlockId, data.id);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setGeneratingVideoMsg(null);
    }
  }

  async function retryVideoGeneration(msgId: string, blockId: string) {
    setChatMsgs(prev => prev.map(m => m.id === msgId
      ? { ...m, videoStatus: 'pending', videoUrl: undefined, videoError: undefined } : m));
    try {
      const res = await fetch(
        `${API_BASE}/api/courses/concepts/${conceptId}/content-blocks/${blockId}/retry-video`,
        { method: 'POST', headers: authH },
      );
      if (!res.ok) throw new Error('Retry failed');
      startVideoPolling(blockId, msgId);
    } catch (err: any) {
      setChatMsgs(prev => prev.map(m => m.id === msgId
        ? { ...m, videoStatus: 'failed', videoError: err.message } : m));
    }
  }

  async function retryManimGeneration(msgId: string, videoId: number, blockId: string) {
    setRetryingManimMsgs(prev => new Set([...prev, msgId]));
    try {
      const res = await fetch(`${API_BASE}/api/videos/${videoId}/retry-manim`, {
        method: 'POST', headers: authH,
      });
      if (!res.ok) throw new Error('Retry failed');
      setChatMsgs(prev => prev.map(m => m.id === msgId
        ? { ...m, videoStatus: 'pending', videoUrl: undefined, videoError: undefined } : m));
      // Polling may have stalled — ensure it's running so status updates are picked up
      if (!videoPollingRef.current.has(blockId)) startVideoPolling(blockId, msgId);
    } catch (err: any) {
      alert(`Could not restart: ${err.message}`);
    } finally {
      setRetryingManimMsgs(prev => { const s = new Set(prev); s.delete(msgId); return s; });
    }
  }

  async function generateQuizFromStudio() {
    setQuizConfigOpen(false);
    setGeneratingStudioQuiz(true);
    try {
      const body: Record<string, unknown> = { difficulty: quizDifficulty, style: quizStyle, count: quizCount };
      if (selectedPages.length > 0) {
        body.image_data_urls = await renderSelectedPageUrls(selectedPages);
        setSelectedPages([]);
      }
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/concept-chat/generate-quiz`, {
        method: 'POST', headers: jsonH, body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Generation failed');
      setChatMsgs(prev => [...prev, data]);
      setAssetsLoaded(false); // force Assets tab refresh
    } catch (err: any) { alert(err.message); }
    finally { setGeneratingStudioQuiz(false); }
  }

  async function generateFlashcardsFromStudio() {
    setFlashcardConfigOpen(false);
    setGeneratingStudioCards(true);
    try {
      const body: Record<string, unknown> = { count: flashcardCount, focus: flashcardFocus };
      if (selectedPages.length > 0) {
        body.image_data_urls = await renderSelectedPageUrls(selectedPages);
        setSelectedPages([]);
      }
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/concept-chat/generate-flashcards`, {
        method: 'POST', headers: jsonH, body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Generation failed');
      setChatMsgs(prev => [...prev, data]);
      setAssetsLoaded(false);
    } catch (err: any) { alert(err.message); }
    finally { setGeneratingStudioCards(false); }
  }

  async function removeVideoFromTextbook(blockId: string) {
    try {
      const res = await fetch(
        `${API_BASE}/api/courses/concepts/${conceptId}/content-blocks/${blockId}`,
        { method: 'DELETE', headers: authH },
      );
      if (!res.ok) throw new Error('Could not remove from textbook');
      setRemovedVideoBlocks(prev => new Set([...prev, blockId]));
      setChatMsgs(prev => prev.map(m => m.videoBlockId === blockId ? { ...m, videoInTextbook: false } : m));
    } catch (err: any) {
      alert(err.message);
    }
  }

  async function addVideoBackToTextbook(msgId: string, videoId: number, oldBlockId: string) {
    try {
      const res = await fetch(
        `${API_BASE}/api/courses/concepts/${conceptId}/content-blocks`,
        { method: 'POST', headers: jsonH, body: JSON.stringify({ type: 'video', video_id: videoId }) },
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not add to textbook');
      setChatMsgs(prev => prev.map(m => m.id === msgId ? { ...m, videoBlockId: data.id, videoInTextbook: true } : m));
      setRemovedVideoBlocks(prev => { const s = new Set(prev); s.delete(oldBlockId); return s; });
    } catch (err: any) {
      alert(err.message);
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

  // Load the authoring chat when Studio tab first opens
  useEffect(() => {
    if (activeTab === 'studio' && !chatLoaded) loadChat();
  }, [activeTab, chatLoaded]);

  // Show draft prompt when teacher opens a concept with no chat history
  useEffect(() => {
    if (chatLoaded && chatMsgs.length === 0 && !autoStartedRef.current) {
      autoStartedRef.current = true;
      setShowDraftPrompt(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatLoaded]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMsgs.length]); // only scroll on new messages, not on in-place status updates

  // When chat history loads (or PDF becomes available), re-render page images for
  // messages that have imagePages stored in DB but no images in local state yet.
  useEffect(() => {
    if (!pdfFile) return;
    const toRender = chatMsgs.filter(
      m => m.imagePages?.length && !m.images && !renderedIdsRef.current.has(m.id),
    );
    if (!toRender.length) return;
    let cancelled = false;
    (async () => {
      // Ensure PDF.js is loaded (may not be if picker was never opened this session)
      if (!(window as any).pdfjsLib) {
        try {
          await new Promise<void>((res, rej) => {
            const s = document.createElement('script');
            s.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
            s.onload = () => res(); s.onerror = () => rej();
            document.head.appendChild(s);
          });
          (window as any).pdfjsLib.GlobalWorkerOptions.workerSrc =
            'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
        } catch { return; }
      }
      for (const msg of toRender) {
        if (cancelled) break;
        renderedIdsRef.current.add(msg.id);
        const urls = await renderSelectedPageUrls(msg.imagePages!);
        if (!cancelled && urls.length) {
          setChatMsgs(prev => prev.map(m => m.id === msg.id ? { ...m, images: urls } : m));
        }
      }
    })();
    return () => { cancelled = true; };
  }, [chatMsgs.length, pdfFile]); // eslint-disable-line react-hooks/exhaustive-deps

  // Resume video polling for any in-progress video cards after reload
  useEffect(() => {
    chatMsgs.forEach(m => {
      if (m.videoBlockId && !m.videoUrl && m.videoStatus !== 'failed') {
        startVideoPolling(m.videoBlockId, m.id);
      }
    });
  }, [chatMsgs.length]); // eslint-disable-line react-hooks/exhaustive-deps

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
        setGeneratingAudio(false);
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

  async function triggerGenerate(type: 'quiz' | 'flashcards' | 'audio') {
    if (type === 'quiz')       setGeneratingQuiz(true);
    if (type === 'flashcards') setGeneratingCards(true);
    if (type === 'audio')      setGeneratingAudio(true);
    const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/generate/${type}`, {
      method: 'POST', headers: authH,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Generation failed' }));
      alert(err.detail || 'Failed to start generation');
      if (type === 'quiz')       setGeneratingQuiz(false);
      if (type === 'flashcards') setGeneratingCards(false);
      if (type === 'audio')      setGeneratingAudio(false);
      return;
    }
    setAssetPolling(true);
    await loadAssets();
  }

  async function clearAsset(type: 'quiz' | 'flashcards') {
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/${type}`, { method: 'DELETE', headers: authH });
    await loadAssets();
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
    const statusKey = type === 'flashcards' ? 'flashcard_status' : `${type}_status`;
    setAssets(prev => prev ? { ...prev, [statusKey]: 'approved' as AssetStatus } : prev);
    setApprovingA(prev => ({ ...prev, [type]: false }));
  }

  // ── Resource → Textbook ──────────────────────────────────────────────────

  async function addResourceToTextbook(r: Resource) {
    if (addingResToTextbook) return;
    setAddingResToTextbook(r.id);
    try {
      const type = r.type === 'video' ? 'embed_video' : r.type === 'image' ? 'embed_image' : 'embed_pdf';
      const body = r.type === 'video' ? (r.video_url ?? '') : r.id;
      await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/content-blocks`, {
        method: 'POST', headers: jsonH,
        body: JSON.stringify({ type, body, title: r.title || '' }),
      });
      setResAddedToTextbook(prev => new Set([...prev, r.id]));
    } catch { /* ignore */ } finally { setAddingResToTextbook(null); }
  }

  // ── Studio chat attachment → Resources ────────────────────────────────────

  async function addAttachmentToResources(msgId: string) {
    const attach = msgAttachMap.current.get(msgId);
    if (!attach || addingAttachToRes) return;
    setAddingAttachToRes(msgId);
    try {
      const fd = new FormData();
      fd.append('file', attach.file, attach.name);
      fd.append('type', attach.mimeType.startsWith('image/') ? 'image' : 'pdf');
      fd.append('title', attach.name);
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/resources`, {
        method: 'POST', headers: authH, body: fd,
      });
      if (res.ok) {
        setAttachAddedToRes(prev => new Set([...prev, msgId]));
        setResourcesLoaded(false); // refresh next time Resources tab opens
      }
    } catch { /* ignore */ } finally { setAddingAttachToRes(null); }
  }

  // ── Per-question / per-card CRUD ─────────────────────────────────────────

  async function patchQuizQuestion(qId: string, patch: Record<string, unknown>) {
    setQuizItemBusy(s => new Set([...s, qId]));
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/quiz/${qId}`, {
      method: 'PATCH', headers: jsonH, body: JSON.stringify(patch),
    });
    await loadAssets();
    setQuizItemBusy(s => { const n = new Set(s); n.delete(qId); return n; });
  }

  async function deleteQuizQuestion(qId: string) {
    setQuizItemBusy(s => new Set([...s, qId]));
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/quiz/${qId}`, {
      method: 'DELETE', headers: authH,
    });
    setAssets(prev => prev ? { ...prev, quiz: prev.quiz.filter(q => q.id !== qId) } : prev);
    setQuizItemBusy(s => { const n = new Set(s); n.delete(qId); return n; });
  }

  async function approveAllQuiz() {
    setApprovingAllQ(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/quiz/approve-all`, {
        method: 'POST', headers: authH,
      });
      if (res.ok) await loadAssets();
    } finally {
      setApprovingAllQ(false);
    }
  }

  async function patchFlashcard(cId: string, patch: Record<string, unknown>) {
    setCardItemBusy(s => new Set([...s, cId]));
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/flashcards/${cId}`, {
      method: 'PATCH', headers: jsonH, body: JSON.stringify(patch),
    });
    await loadAssets();
    setCardItemBusy(s => { const n = new Set(s); n.delete(cId); return n; });
  }

  async function deleteFlashcard(cId: string) {
    setCardItemBusy(s => new Set([...s, cId]));
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/flashcards/${cId}`, {
      method: 'DELETE', headers: authH,
    });
    setAssets(prev => prev ? { ...prev, flashcards: prev.flashcards.filter(c => c.id !== cId) } : prev);
    setCardItemBusy(s => { const n = new Set(s); n.delete(cId); return n; });
  }

  async function approveAllFlashcards() {
    setApprovingAllC(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/flashcards/approve-all`, {
        method: 'POST', headers: authH,
      });
      if (res.ok) await loadAssets();
    } finally {
      setApprovingAllC(false);
    }
  }

  async function setQuizModeRemote(mode: 'ordered' | 'difficulty' | 'shuffle') {
    setAssets(prev => prev ? { ...prev, quiz_mode: mode } : prev);
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/quiz-mode`, {
      method: 'PATCH', headers: jsonH, body: JSON.stringify({ mode }),
    });
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

      {/* ── Left panel: native PDF iframe (full features) ── */}
      <div className={`border-r border-[var(--bd)] flex flex-col overflow-hidden transition-all duration-200 ${showLeft ? 'w-2/5' : 'w-0'}`}>
        {showLeft && (
          pdfUrl
            ? <iframe src={pdfUrl + (concept?.page_start ? `#page=${concept.page_start}` : '')} className="flex-1 w-full" title="Chapter PDF" />
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
      <div ref={rightPanelRef} onScroll={handlePanelScroll} className="flex-1 overflow-y-auto">

        {/* Floating scroll jump buttons — studio tab, when chat has messages */}
        {activeTab === 'studio' && chatMsgs.length > 2 && (
          <div className="fixed right-4 top-1/2 -translate-y-1/2 z-30 flex flex-col gap-2">
            <button
              onClick={() => rightPanelRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}
              title="Jump to top"
              className={`w-8 h-8 rounded-full flex items-center justify-center border border-[var(--bd)]
                          bg-[var(--surface)] shadow-md transition-all
                          ${chatAtTop
                            ? 'opacity-20 cursor-default pointer-events-none'
                            : 'text-[var(--tx6)] hover:border-purple-500/50 hover:text-purple-400'}`}>
              <ChevronUp size={14} />
            </button>
            <button
              onClick={() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })}
              title="Jump to bottom"
              className={`w-8 h-8 rounded-full flex items-center justify-center border border-[var(--bd)]
                          bg-[var(--surface)] shadow-md transition-all
                          ${chatAtBottom
                            ? 'opacity-20 cursor-default pointer-events-none'
                            : 'text-[var(--tx6)] hover:border-purple-500/50 hover:text-purple-400'}`}>
              <ChevronDown size={14} />
            </button>
          </div>
        )}

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
                <div className="px-4 py-3 space-y-3">
                  {!chatLoaded ? (
                    <div className="flex justify-center py-10"><Loader2 size={16} className="animate-spin text-[var(--tx7)]" /></div>
                  ) : chatMsgs.length === 0 && showDraftPrompt ? (
                    <div className="flex flex-col items-center gap-4 py-10 text-center">
                      <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                        <Wand2 size={18} className="text-purple-400" />
                      </div>
                      <div>
                        <p className="text-[var(--tx2)] text-sm font-medium mb-1">{t.teacher.studioGenerateTitle}</p>
                        <p className="text-[var(--tx7)] text-xs max-w-xs">{t.teacher.studioGenerateDesc}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            setShowDraftPrompt(false);
                            sendChatMessage(t.teacher.studioFirstDraftMsg);
                          }}
                          className="px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium transition-colors">
                          {t.teacher.studioGenerateBtn}
                        </button>
                        <button
                          onClick={() => setShowDraftPrompt(false)}
                          className="px-4 py-1.5 rounded-lg border border-[var(--bd)] hover:bg-[var(--ov2)] text-[var(--tx6)] text-xs transition-colors">
                          {t.skip}
                        </button>
                      </div>
                    </div>
                  ) : chatMsgs.length === 0 ? (
                    <div className="flex flex-col items-center gap-3 py-10 text-center">
                      <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                        <Wand2 size={18} className="text-purple-400" />
                      </div>
                      <p className="text-[var(--tx3)] text-sm font-medium">What would you like to create?</p>
                    </div>
                  ) : (
                    chatMsgs.map(m => {
                      // ── Quiz/flashcard draft confirmation card ───────────────
                      if (m.quizDraft || m.flashcardDraft) {
                        const icon  = m.quizDraft ? <HelpCircle size={12} className="text-green-400 shrink-0" /> : <Layers size={12} className="text-green-400 shrink-0" />;
                        const label = m.quizDraft ? t.teacher.assetQuiz : t.teacher.assetFlashcards;
                        return (
                          <div key={m.id} className="flex justify-start">
                            <div className="max-w-[85%] rounded-xl text-sm overflow-hidden bg-[var(--ov1)] border border-[var(--bd)]">
                              <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--bd)]">
                                {icon}
                                <span className="text-[var(--tx2)] text-xs font-medium">{label}</span>
                                <span className="ml-auto text-[10px] text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">{t.teacher.draftBadge}</span>
                              </div>
                              <div className="px-3.5 py-2.5 text-[var(--tx6)] text-xs">{m.content}</div>
                              <div className="px-3 py-2 border-t border-[var(--bd)]">
                                <button onClick={() => setActiveTab('assets')}
                                  className="flex items-center gap-1 text-xs text-[var(--tx7)] hover:text-purple-400 transition-colors">
                                  <CheckCircle size={11} /> {t.teacher.reviewInAssets}
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      }

                      // ── Video card — now rendered inline inside its parent AI message ──
                      if (m.videoBlockId !== undefined && m.videoSourceMsgId) return null;

                      // ── Normal message ──────────────────────────────────────
                      return (
                      <div key={m.id} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                        <div className={`max-w-[85%] rounded-xl text-sm overflow-hidden ${
                          m.role === 'user'
                            ? 'bg-purple-600 text-white'
                            : 'bg-[var(--ov1)] text-[var(--tx2)] border border-[var(--bd)]'
                        }`}>
                          {/* Attached page images — shown above the message text */}
                          {m.images && m.images.length > 0 && (
                            <div className="flex gap-1.5 flex-wrap p-2 pb-0 border-b border-white/15">
                              {m.images.map((url, ii) => {
                                const pageNum = m.imagePages?.[ii] ?? ii + 1;
                                return (
                                  <div key={ii} className="relative shrink-0 group/img">
                                    <img
                                      src={url}
                                      alt={`Page ${pageNum}`}
                                      onClick={() => setLightbox({ url, page: pageNum })}
                                      className="h-28 w-auto rounded border border-white/20 object-contain
                                                 bg-white/5 cursor-zoom-in hover:border-white/40 transition-colors"
                                    />
                                    <span className="absolute bottom-1 left-1 text-[9px] text-white/70
                                                     bg-black/60 px-1 py-0.5 rounded leading-none">
                                      p.{pageNum}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                          {/* File attachment card (image/PDF attached to this message) */}
                          {m.role === 'user' && msgAttachMap.current.has(m.id) && (() => {
                            const att = msgAttachMap.current.get(m.id)!;
                            const addedToRes = attachAddedToRes.has(m.id);
                            return (
                              <div className="flex items-center gap-2 px-3 py-2 border-t border-white/15">
                                {att.mimeType.startsWith('image/')
                                  ? <img src={att.dataUrl} alt={att.name}
                                      className="w-10 h-7 object-cover rounded border border-white/20 shrink-0" />
                                  : <FileText size={14} className="text-purple-300 shrink-0" />}
                                <span className="text-xs text-white/70 truncate flex-1">{att.name}</span>
                                <button
                                  onClick={() => addAttachmentToResources(m.id)}
                                  disabled={addedToRes || addingAttachToRes === m.id}
                                  className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full
                                             border border-white/25 text-white/70 hover:border-white/50
                                             hover:text-white transition-colors disabled:opacity-50 shrink-0">
                                  {addingAttachToRes === m.id
                                    ? <Loader2 size={9} className="animate-spin" />
                                    : addedToRes ? <Check size={9} className="text-green-300" />
                                    : <ImageIcon size={9} />}
                                  {addedToRes ? 'In Resources' : '+ Resources'}
                                </button>
                              </div>
                            );
                          })()}

                          <div className="px-3.5 py-2.5 whitespace-pre-wrap">
                          {m.role === 'assistant' ? (
                            <div className="ai-content leading-relaxed [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0">
                              <ReactMarkdown
                                remarkPlugins={[remarkMath]}
                                rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}
                                components={{
                                  code({ className, children }) {
                                    const lang = /language-(\w+)/.exec(className ?? '')?.[1];
                                    if (lang === 'smiles') return <SmilesBlock smiles={String(children).trim()} />;
                                    return <code className={className}>{children}</code>;
                                  },
                                }}
                              >
                                {preprocessMath(m.content)}
                              </ReactMarkdown>
                            </div>
                          ) : m.content}
                          </div>
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
                                {/* Text-only import */}
                                {(() => {
                                  const alreadyAdded = m.inTextbook || addedMsgBlocks.has(m.id);
                                  return (
                                    <button
                                      onClick={() => addMsgToTextbook(m.id)}
                                      disabled={addingMsgBlock === m.id || alreadyAdded}
                                      className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg
                                                 bg-purple-600/15 hover:bg-purple-600/25 text-purple-400
                                                 transition-all disabled:opacity-50">
                                      {addingMsgBlock === m.id
                                        ? <Loader2 size={11} className="animate-spin" />
                                        : alreadyAdded ? <Check size={11} /> : <LayoutList size={11} />}
                                      {alreadyAdded ? 'Added' : '+ Textbook'}
                                    </button>
                                  );
                                })()}
                                {/* Group import: text + video placed adjacently in textbook */}
                                {(() => {
                                  const vid = chatMsgs.find(v => v.videoSourceMsgId === m.id && !!v.videoBlockId && v.videoStatus !== 'failed');
                                  const alreadyAdded = m.inTextbook || addedMsgBlocks.has(m.id);
                                  if (!vid || alreadyAdded) return null;
                                  return (
                                    <button
                                      onClick={() => addMsgAndVideoToTextbook(m.id, vid.videoBlockId!)}
                                      disabled={addingMsgBlock === m.id}
                                      title="Add text and video to Textbook as adjacent blocks"
                                      className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg
                                                 bg-teal-600/15 hover:bg-teal-600/25 text-teal-400
                                                 transition-all disabled:opacity-50">
                                      {addingMsgBlock === m.id
                                        ? <Loader2 size={11} className="animate-spin" />
                                        : <LayoutList size={11} />}
                                      + Text & Video
                                    </button>
                                  );
                                })()}
                                {/* + Video: only when no video exists yet for this message */}
                                {!chatMsgs.some(v => v.videoSourceMsgId === m.id && v.videoStatus !== 'failed') && (
                                  <button
                                    onClick={() => addMsgAsVideo(m.id)}
                                    disabled={generatingVideoMsg === m.id}
                                    title="Generate an animated video"
                                    className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg
                                               bg-blue-600/15 hover:bg-blue-600/25 text-blue-400
                                               transition-all disabled:opacity-50">
                                    {generatingVideoMsg === m.id
                                      ? <Loader2 size={11} className="animate-spin" />
                                      : <Video size={11} />}
                                    {generatingVideoMsg === m.id ? 'Starting…' : '+ Video'}
                                  </button>
                                )}
                              </div>
                            </div>
                          )}
                          {/* ── Inline video section ─────────────────────────────
                              Video cards are no longer standalone chat items.
                              They render here, attached to the AI message that spawned them. */}
                          {m.role === 'assistant' && (() => {
                            const vid = chatMsgs.find(v => v.videoSourceMsgId === m.id && v.videoBlockId !== undefined);
                            if (!vid) return null;
                            const vidReady  = !!vid.videoUrl;
                            const vidFailed = vid.videoStatus === 'failed';
                            return (
                              <div className="border-t border-[var(--bd)]">
                                {/* Header row */}
                                <div className="flex items-center gap-2 px-3.5 py-2">
                                  <Video size={11} className="text-blue-400 shrink-0" />
                                  <span className="text-[var(--tx6)] text-xs font-medium">Animated Video</span>
                                  {!vidReady && !vidFailed && (
                                    <span className="ml-auto text-[10px] text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full">
                                      {vid.videoStatus === 'transcript_ready' ? 'Writing animation…'
                                      : vid.videoStatus === 'queued' || vid.videoStatus === 'rendering' ? 'Rendering…'
                                      : 'Generating script…'}
                                    </span>
                                  )}
                                  {vidFailed && <span className="ml-auto text-[10px] text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full">Failed</span>}
                                  {vidReady  && <span className="ml-auto text-[10px] text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">Ready</span>}
                                </div>
                                {/* Generating / rendering progress */}
                                {!vidReady && !vidFailed && (
                                  <div className="flex items-center gap-2 px-3.5 pb-3">
                                    <Loader2 size={13} className="animate-spin text-blue-400 shrink-0" />
                                    <span className="text-[var(--tx7)] text-xs">
                                      {vid.videoStatus === 'transcript_ready' ? 'Writing Manim animation code…'
                                      : vid.videoStatus === 'queued' || vid.videoStatus === 'rendering' ? 'Rendering video, this may take a few minutes…'
                                      : 'Writing animation script…'}
                                    </span>
                                    {vid.videoStatus === 'transcript_ready' && vid.videoId && vid.videoBlockId && (
                                      <button
                                        onClick={() => retryManimGeneration(vid.id, vid.videoId!, vid.videoBlockId!)}
                                        disabled={retryingManimMsgs.has(vid.id)}
                                        className="ml-auto flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full
                                                   border border-[var(--bd)] text-[var(--tx7)]
                                                   hover:text-orange-400 hover:border-orange-500/30 transition-colors
                                                   disabled:opacity-40 disabled:pointer-events-none">
                                        <RefreshCw size={9} /> Restart
                                      </button>
                                    )}
                                  </div>
                                )}
                                {/* Ready — player + actions */}
                                {vidReady && (
                                  <div>
                                    <video src={vid.videoUrl} controls className="w-full bg-black" preload="metadata" />
                                    <div className="px-3 py-2 border-t border-[var(--bd)] flex items-center gap-3">
                                      {vid.videoBlockId && vid.videoInTextbook && !removedVideoBlocks.has(vid.videoBlockId) ? (
                                        <>
                                          <button onClick={() => removeVideoFromTextbook(vid.videoBlockId!)}
                                            className="flex items-center gap-1 text-xs text-[var(--tx7)] hover:text-red-400 transition-colors">
                                            <X size={11} /> {t.teacher.removeFromTextbook}
                                          </button>
                                          <button onClick={() => setActiveTab('textbook')}
                                            className="flex items-center gap-1 text-xs text-[var(--tx7)] hover:text-purple-400 transition-colors">
                                            <LayoutList size={11} /> {t.teacher.viewInTextbook}
                                          </button>
                                        </>
                                      ) : vid.videoId ? (
                                        <button onClick={async () => {
                                          // Block exists but not yet in textbook: use add-to-textbook endpoint
                                          if (vid.videoBlockId && !removedVideoBlocks.has(vid.videoBlockId)) {
                                            try {
                                              const r = await fetch(
                                                `${API_BASE}/api/courses/concepts/${conceptId}/content-blocks/${vid.videoBlockId}/add-to-textbook`,
                                                { method: 'POST', headers: authH },
                                              );
                                              if (!r.ok) throw new Error('Could not add to textbook');
                                              setChatMsgs(prev => prev.map(m =>
                                                m.id === vid.id ? { ...m, videoInTextbook: true } : m
                                              ));
                                            } catch (err: any) { alert(err.message); }
                                          } else {
                                            // Block was deleted: create a new one
                                            addVideoBackToTextbook(vid.id, vid.videoId!, vid.videoBlockId ?? '');
                                          }
                                        }}
                                          className="flex items-center gap-1 text-xs text-[var(--tx7)] hover:text-green-400 transition-colors">
                                          <Plus size={11} /> {t.teacher.addToTextbook}
                                        </button>
                                      ) : null}
                                    </div>
                                  </div>
                                )}
                                {/* Failed — error + retry */}
                                {vidFailed && (
                                  <div className="px-3.5 pb-3">
                                    <p className="text-red-400 text-xs mb-2">{vid.videoError || 'Video generation failed'}</p>
                                    <button onClick={() => retryVideoGeneration(vid.id, vid.videoBlockId!)}
                                      className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg
                                                 border border-[var(--bd)] bg-[var(--ov2)]
                                                 text-[var(--tx6)] hover:text-red-400 hover:border-red-500/30 transition-colors">
                                      <RefreshCw size={10} /> Retry
                                    </button>
                                  </div>
                                )}
                              </div>
                            );
                          })()}
                        </div>
                      </div>
                      );
                    })
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

                {/* Studio generate quiz/flashcard buttons + config strip */}
                <div className="border-t border-[var(--bd)] px-3 py-2 flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => { setQuizConfigOpen(p => !p); setFlashcardConfigOpen(false); }}
                    disabled={generatingStudioQuiz}
                    className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border border-[var(--bd)]
                               bg-[var(--ov1)] text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400
                               transition-colors disabled:opacity-50">
                    {generatingStudioQuiz ? <Loader2 size={11} className="animate-spin" /> : <HelpCircle size={11} />}
                    {t.teacher.assetQuiz}
                  </button>
                  <button
                    onClick={() => { setFlashcardConfigOpen(p => !p); setQuizConfigOpen(false); }}
                    disabled={generatingStudioCards}
                    className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border border-[var(--bd)]
                               bg-[var(--ov1)] text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400
                               transition-colors disabled:opacity-50">
                    {generatingStudioCards ? <Loader2 size={11} className="animate-spin" /> : <Layers size={11} />}
                    {t.teacher.assetFlashcards}
                  </button>
                </div>

                {quizConfigOpen && (
                  <div className="border-t border-[var(--bd)] px-3 py-3 space-y-2.5 bg-[var(--ov1)]">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[var(--tx7)] text-xs w-16">{t.teacher.quizDifficulty}</span>
                      {(['easy','medium','hard','mixed'] as const).map(d => (
                        <button key={d} onClick={() => setQuizDifficulty(d)}
                          className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                            quizDifficulty === d
                              ? 'bg-purple-600 border-purple-500 text-white'
                              : 'border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40'}`}>
                          {t.teacher[`quizDiff_${d}` as keyof typeof t.teacher] as string}
                        </button>
                      ))}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[var(--tx7)] text-xs w-16">{t.teacher.quizStyle}</span>
                      {(['multiple_choice','true_false','mixed'] as const).map(s => (
                        <button key={s} onClick={() => setQuizStyle(s)}
                          className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                            quizStyle === s
                              ? 'bg-purple-600 border-purple-500 text-white'
                              : 'border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40'}`}>
                          {t.teacher[`quizStyle_${s}` as keyof typeof t.teacher] as string}
                        </button>
                      ))}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[var(--tx7)] text-xs w-16">{t.teacher.quizCount}</span>
                      {[3,5,10].map(n => (
                        <button key={n} onClick={() => setQuizCount(n)}
                          className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                            quizCount === n
                              ? 'bg-purple-600 border-purple-500 text-white'
                              : 'border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40'}`}>
                          {n}
                        </button>
                      ))}
                      <button onClick={generateQuizFromStudio}
                        className="ml-auto flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                                   bg-purple-600 hover:bg-purple-500 text-white font-medium transition-colors">
                        <Zap size={11} /> {t.teacher.generateBtn}
                      </button>
                    </div>
                  </div>
                )}

                {flashcardConfigOpen && (
                  <div className="border-t border-[var(--bd)] px-3 py-3 space-y-2.5 bg-[var(--ov1)]">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[var(--tx7)] text-xs w-16">{t.teacher.flashcardFocus}</span>
                      {(['definitions','examples','mixed'] as const).map(f => (
                        <button key={f} onClick={() => setFlashcardFocus(f)}
                          className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                            flashcardFocus === f
                              ? 'bg-purple-600 border-purple-500 text-white'
                              : 'border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40'}`}>
                          {t.teacher[`flashcardFocus_${f}` as keyof typeof t.teacher] as string}
                        </button>
                      ))}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[var(--tx7)] text-xs w-16">{t.teacher.quizCount}</span>
                      {[5,10,15].map(n => (
                        <button key={n} onClick={() => setFlashcardCount(n)}
                          className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                            flashcardCount === n
                              ? 'bg-purple-600 border-purple-500 text-white'
                              : 'border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40'}`}>
                          {n}
                        </button>
                      ))}
                      <button onClick={generateFlashcardsFromStudio}
                        className="ml-auto flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                                   bg-purple-600 hover:bg-purple-500 text-white font-medium transition-colors">
                        <Zap size={11} /> {t.teacher.generateBtn}
                      </button>
                    </div>
                  </div>
                )}

                {/* Pending file attachment preview */}
                {pendingAttach && (
                  <div className="flex items-center gap-2 px-3 py-2 border-t border-[var(--bd)] bg-[var(--ov1)]">
                    {pendingAttach.file.type.startsWith('image/')
                      ? <img src={pendingAttach.dataUrl} alt="attach"
                          className="w-10 h-7 object-cover rounded border border-[var(--bd)]" />
                      : <FileText size={16} className="text-purple-400 shrink-0" />}
                    <span className="text-xs text-[var(--tx6)] truncate flex-1">{pendingAttach.name}</span>
                    <button type="button" onClick={() => setPendingAttach(null)}
                      className="text-[var(--tx8)] hover:text-red-400 transition-colors p-0.5 shrink-0">
                      <X size={12} />
                    </button>
                  </div>
                )}

                {/* Selected pages context badge */}
                {selectedPages.length > 0 && (
                  <div className="flex items-center gap-2 px-3 py-2 border-t border-[var(--bd)] bg-violet-500/5">
                    <FileImage size={12} className="text-violet-400 shrink-0" />
                    <span className="text-[11px] text-violet-400 flex-1">
                      Page{selectedPages.length > 1 ? 's' : ''}{' '}
                      {selectedPages.slice().sort((a, b) => a - b).join(', ')} as context
                    </span>
                    <button onClick={() => setSelectedPages([])}
                      className="text-[var(--tx8)] hover:text-red-400 transition-colors shrink-0 p-0.5">
                      <X size={12} />
                    </button>
                  </div>
                )}

                {/* Hidden file input for chat attachments */}
                <input ref={chatAttachRef} type="file" accept="image/*,application/pdf" className="hidden"
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    const reader = new FileReader();
                    reader.onload = ev => setPendingAttach({ file, dataUrl: ev.target?.result as string, name: file.name });
                    reader.readAsDataURL(file);
                    e.target.value = '';
                  }} />

                <form onSubmit={e => { e.preventDefault(); sendChatMessage(); }}
                  className="flex gap-2 px-3 py-2.5 border-t border-[var(--bd)]">
                  {/* Attach image/PDF */}
                  <button type="button" onClick={() => chatAttachRef.current?.click()}
                    title="Attach image or PDF"
                    className={`flex items-center justify-center w-8 h-8 rounded-lg transition-colors shrink-0 ${
                      pendingAttach
                        ? 'bg-purple-500/20 text-purple-400'
                        : 'bg-[var(--ov1)] text-[var(--tx7)] hover:bg-[var(--ov2)] hover:text-[var(--tx3)]'
                    }`}>
                    <Paperclip size={13} />
                  </button>
                  {pdfFile && (
                    <button type="button" onClick={() => setPickerOpen(true)}
                      title="Select PDF pages as context"
                      className={[
                        'flex items-center justify-center w-8 h-8 rounded-lg transition-colors shrink-0',
                        selectedPages.length > 0
                          ? 'bg-violet-500/20 text-violet-400 hover:bg-violet-500/30'
                          : 'bg-[var(--ov1)] text-[var(--tx7)] hover:bg-violet-500/15 hover:text-violet-400',
                      ].join(' ')}>
                      <Scissors size={13} />
                    </button>
                  )}
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

                {/* PDF page picker modal */}
                {pickerOpen && pdfFile && (
                  <PDFContextPicker
                    file={pdfFile}
                    initial={selectedPages}
                    initialPage={concept?.page_start}
                    onClose={() => setPickerOpen(false)}
                    onAttach={pages => { setSelectedPages(pages); setPickerOpen(false); }}
                  />
                )}

                {/* Page image lightbox */}
                {lightbox && (
                  <div
                    className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 backdrop-blur-sm"
                    onClick={() => setLightbox(null)}
                  >
                    <div className="relative max-w-[90vw] max-h-[90vh] flex flex-col items-center gap-2"
                      onClick={e => e.stopPropagation()}>
                      <div className="flex items-center justify-between w-full px-1">
                        <span className="text-white/60 text-xs font-medium">Page {lightbox.page}</span>
                        <button onClick={() => setLightbox(null)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg
                                     text-white/40 hover:text-white/80 hover:bg-white/10 transition-colors">
                          <X size={15} />
                        </button>
                      </div>
                      <img
                        src={lightbox.url}
                        alt={`Page ${lightbox.page}`}
                        className="max-w-[90vw] max-h-[85vh] rounded-lg object-contain shadow-2xl
                                   border border-white/10"
                      />
                    </div>
                  </div>
                )}
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
                        <p className="text-xs text-[var(--tx6)] truncate flex-1 mr-2">{r.title}</p>
                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            onClick={() => addResourceToTextbook(r)}
                            disabled={!!addingResToTextbook || resAddedToTextbook.has(r.id)}
                            className="flex items-center gap-1 text-xs text-[var(--tx7)] hover:text-purple-400
                                       transition-colors disabled:opacity-50">
                            {addingResToTextbook === r.id
                              ? <Loader2 size={11} className="animate-spin" />
                              : resAddedToTextbook.has(r.id)
                              ? <Check size={11} className="text-green-400" />
                              : <LayoutList size={11} />}
                            {resAddedToTextbook.has(r.id) ? 'Added' : '+ Textbook'}
                          </button>
                          <button onClick={() => deleteResource(r.id)}
                            className="p-1 text-[var(--tx8)] hover:text-red-400 transition-colors">
                            <Trash2 size={13} />
                          </button>
                        </div>
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
                    canGenerate={hasAISrc}
                    canApprove={assets.quiz_status === 'ready' && assets.quiz.some(q => q.status === 'approved')}
                    approving={!!approvingA['quiz']}
                    onGenerate={() => triggerGenerate('quiz')}
                    onApprove={() => approveAsset('quiz')}
                    onClear={() => clearAsset('quiz')}
                  >
                    {assets.quiz.length > 0 && assets.quiz_status !== 'generating' && (
                      <div className="mt-3 pb-4">
                        {/* toolbar */}
                        <div className="flex items-center gap-2 flex-wrap px-4 mb-3">
                          {assets.quiz.some(q => q.status === 'draft') && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-medium">
                              {tF(t.teacher.draftCount, { n: assets.quiz.filter(q => q.status === 'draft').length })}
                            </span>
                          )}
                          <button onClick={approveAllQuiz} disabled={approvingAllQ}
                            className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border border-green-500/30
                                       text-green-400 hover:bg-green-500/10 transition-colors disabled:opacity-50">
                            {approvingAllQ ? <Loader2 size={10} className="animate-spin" /> : <CheckCircle size={10} />}
                            {t.teacher.approveAll}
                          </button>
                          <button onClick={() => {
                            const sorted = [...assets.quiz].sort((a, b) => {
                              const ord: Record<string, number> = { easy: 0, medium: 1, hard: 2 };
                              return ord[a.difficulty] - ord[b.difficulty];
                            });
                            setAssets(prev => prev ? { ...prev, quiz: sorted } : prev);
                          }}
                            className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border border-[var(--bd)]
                                       text-[var(--tx6)] hover:text-[var(--tx2)] transition-colors">
                            <Star size={10} /> {t.teacher.sortByDifficulty}
                          </button>
                          <div className="flex items-center gap-1 ml-auto">
                            <span className="text-[var(--tx7)] text-[10px]">{t.teacher.quizMode}:</span>
                            {(['ordered','difficulty','shuffle'] as const).map(mode => (
                              <button key={mode} onClick={() => setQuizModeRemote(mode)}
                                className={`text-[10px] px-2 py-0.5 rounded-full transition-colors ${
                                  assets.quiz_mode === mode
                                    ? 'bg-purple-600 text-white'
                                    : 'border border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40'
                                }`}>
                                {mode === 'ordered' ? t.teacher.quizMode_ordered
                                  : mode === 'difficulty' ? t.teacher.quizMode_difficulty
                                  : t.teacher.quizMode_shuffle}
                              </button>
                            ))}
                          </div>
                        </div>
                        {/* question cards */}
                        <div className="space-y-2 px-4">
                          {assets.quiz.map((q, qi) => (
                            <div key={q.id} className={`border rounded-xl p-3.5 transition-colors ${
                              q.status === 'draft'
                                ? 'border-amber-500/30 bg-amber-500/5'
                                : 'border-green-500/20 bg-green-500/5'
                            }`}>
                              <div className="flex items-start gap-2">
                                <span className="text-[var(--tx7)] text-xs font-mono mt-0.5 shrink-0">{qi + 1}.</span>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1.5">
                                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                                      q.difficulty === 'easy'   ? 'bg-green-500/15 text-green-400'
                                      : q.difficulty === 'hard' ? 'bg-red-500/15 text-red-400'
                                      : 'bg-blue-500/15 text-blue-400'
                                    }`}>
                                      {q.difficulty === 'easy' ? t.teacher.quizDiff_easy
                                        : q.difficulty === 'hard' ? t.teacher.quizDiff_hard
                                        : t.teacher.quizDiff_medium}
                                    </span>
                                    {q.status === 'draft' && (
                                      <span className="text-[10px] text-amber-400">{t.teacher.draftBadge}</span>
                                    )}
                                  </div>
                                  <p className="text-[var(--tx1)] text-sm font-medium mb-2">
                                    <MathText inline>{q.question}</MathText>
                                  </p>
                                  <ul className="space-y-1">
                                    {q.options.map((opt, oi) => (
                                      <li key={oi} className={`text-xs px-2.5 py-1 rounded-lg ${
                                        oi === q.correct_idx ? 'bg-green-500/15 text-green-400 font-medium' : 'text-[var(--tx6)]'
                                      }`}>
                                        {String.fromCharCode(65 + oi)}. <MathText inline>{opt}</MathText>
                                      </li>
                                    ))}
                                  </ul>
                                  {q.explanation && (
                                    <p className="text-[var(--tx7)] text-[11px] mt-2 pt-2 border-t border-[var(--bd)]">
                                      💡 <MathText inline>{q.explanation}</MathText>
                                    </p>
                                  )}
                                </div>
                                {/* actions */}
                                <div className="flex flex-col gap-1 shrink-0">
                                  <div className="flex gap-1">
                                    {q.status === 'draft' ? (
                                      <button onClick={() => patchQuizQuestion(q.id, { status: 'approved' })}
                                        disabled={quizItemBusy.has(q.id)}
                                        title={t.teacher.approveItem}
                                        className="p-1 rounded-lg text-green-400 hover:bg-green-500/15 transition-colors disabled:opacity-40">
                                        {quizItemBusy.has(q.id) ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                                      </button>
                                    ) : (
                                      <button onClick={() => patchQuizQuestion(q.id, { status: 'draft' })}
                                        disabled={quizItemBusy.has(q.id)}
                                        title={t.teacher.rejectItem}
                                        className="p-1 rounded-lg text-amber-400 hover:bg-amber-500/15 transition-colors disabled:opacity-40">
                                        {quizItemBusy.has(q.id) ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                                      </button>
                                    )}
                                    <button onClick={() => deleteQuizQuestion(q.id)}
                                      disabled={quizItemBusy.has(q.id)}
                                      title={t.delete}
                                      className="p-1 rounded-lg text-[var(--tx7)] hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40">
                                      <X size={13} />
                                    </button>
                                  </div>
                                  <div className="flex gap-1">
                                    <button onClick={() => patchQuizQuestion(q.id, { position: q.position - 1 })}
                                      disabled={quizItemBusy.has(q.id) || qi === 0}
                                      className="p-1 rounded-lg text-[var(--tx7)] hover:text-[var(--tx2)] transition-colors disabled:opacity-30">
                                      <ChevronUp size={13} />
                                    </button>
                                    <button onClick={() => patchQuizQuestion(q.id, { position: q.position + 1 })}
                                      disabled={quizItemBusy.has(q.id) || qi === assets.quiz.length - 1}
                                      className="p-1 rounded-lg text-[var(--tx7)] hover:text-[var(--tx2)] transition-colors disabled:opacity-30">
                                      <ChevronDown size={13} />
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </AssetSection>

                  <AssetSection
                    title={t.teacher.assetFlashcards} icon={<Layers size={14} />}
                    status={assets.flashcard_status}
                    isGenerating={generatingCards || assets.flashcard_status === 'generating'}
                    canGenerate={hasAISrc}
                    canApprove={assets.flashcard_status === 'ready' && assets.flashcards.some(c => c.status === 'approved')}
                    approving={!!approvingA['flashcards']}
                    onGenerate={() => triggerGenerate('flashcards')}
                    onApprove={() => approveAsset('flashcards')}
                    onClear={() => clearAsset('flashcards')}
                  >
                    {assets.flashcards.length > 0 && assets.flashcard_status !== 'generating' && (
                      <div className="mt-3 pb-4">
                        {/* toolbar */}
                        <div className="flex items-center gap-2 px-4 mb-3">
                          {assets.flashcards.some(c => c.status === 'draft') && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-medium">
                              {tF(t.teacher.draftCount, { n: assets.flashcards.filter(c => c.status === 'draft').length })}
                            </span>
                          )}
                          <button onClick={approveAllFlashcards} disabled={approvingAllC}
                            className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border border-green-500/30
                                       text-green-400 hover:bg-green-500/10 transition-colors disabled:opacity-50">
                            {approvingAllC ? <Loader2 size={10} className="animate-spin" /> : <CheckCircle size={10} />}
                            {t.teacher.approveAll}
                          </button>
                        </div>
                        {/* card grid */}
                        <div className="grid grid-cols-2 gap-2 px-4">
                          {assets.flashcards.map(card => (
                            <div key={card.id} className={`relative border rounded-xl p-3 ${
                              card.status === 'draft'
                                ? 'border-amber-500/30 bg-amber-500/5'
                                : 'border-green-500/20 bg-green-500/5'
                            }`}>
                              {card.status === 'draft' && (
                                <span className="absolute top-2 right-2 text-[9px] text-amber-400 font-medium">{t.teacher.draftBadge}</span>
                              )}
                              <p className="text-[var(--tx1)] text-xs font-semibold mb-1 pr-8"><MathText inline>{card.front}</MathText></p>
                              <p className="text-[var(--tx6)] text-xs leading-relaxed mb-2"><MathText inline>{card.back}</MathText></p>
                              <div className="flex gap-1 mt-1">
                                {card.status === 'draft' ? (
                                  <button onClick={() => patchFlashcard(card.id, { status: 'approved' })}
                                    disabled={cardItemBusy.has(card.id)}
                                    className="flex items-center gap-0.5 text-[10px] px-2 py-0.5 rounded-full border border-green-500/30 text-green-400 hover:bg-green-500/10 transition-colors disabled:opacity-40">
                                    {cardItemBusy.has(card.id) ? <Loader2 size={9} className="animate-spin" /> : <Check size={9} />}
                                    {t.teacher.approveItem}
                                  </button>
                                ) : (
                                  <button onClick={() => patchFlashcard(card.id, { status: 'draft' })}
                                    disabled={cardItemBusy.has(card.id)}
                                    className="flex items-center gap-0.5 text-[10px] px-2 py-0.5 rounded-full border border-amber-500/30 text-amber-400 hover:bg-amber-500/10 transition-colors disabled:opacity-40">
                                    {cardItemBusy.has(card.id) ? <Loader2 size={9} className="animate-spin" /> : <RefreshCw size={9} />}
                                    {t.teacher.rejectItem}
                                  </button>
                                )}
                                <button onClick={() => deleteFlashcard(card.id)}
                                  disabled={cardItemBusy.has(card.id)}
                                  className="ml-auto flex items-center gap-0.5 text-[10px] px-2 py-0.5 rounded-full border border-[var(--bd)] text-[var(--tx7)] hover:text-red-400 hover:border-red-500/30 transition-colors disabled:opacity-40">
                                  <X size={9} />
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
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

                  <div className="flex items-start gap-3 px-4 py-3 rounded-xl border border-[var(--bd)] bg-[var(--ov1)]">
                    <Video size={14} className="text-[var(--tx7)] mt-0.5 shrink-0" />
                    <div>
                      <p className="text-[var(--tx3)] text-sm font-medium mb-0.5">{t.teacher.assetVideo}</p>
                      <p className="text-[var(--tx7)] text-xs">
                        Generate animated videos in the{' '}
                        <button onClick={() => setActiveTab('studio')}
                          className="text-purple-400 hover:text-purple-300 underline underline-offset-2 transition-colors">
                          Studio
                        </button>
                        {' '}tab — chat with AI, then click "+ Video" on any response.
                      </p>
                    </div>
                  </div>
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
  onGenerate, onApprove = () => {}, onClear, children,
}: {
  title: string; icon: React.ReactNode;
  status: AssetStatus; isGenerating: boolean; canGenerate: boolean;
  canApprove: boolean; approving: boolean; noReset?: boolean; hint?: string;
  onGenerate: () => void; onApprove?: () => void; onClear?: () => void;
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
