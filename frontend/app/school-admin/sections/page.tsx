'use client';
import { useEffect, useState } from 'react';
import { Layers, Loader2, Plus, Pencil, Trash2, Users } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Section {
  id: string; name: string; grade: string | null; section_label: string | null;
  teacher_id: string | null; teacher_name: string | null; student_count: number;
}
interface Teacher { id: string; name: string; email: string; }

export default function SectionsPage() {
  const { token } = useSessionStore();
  const [sections, setSections] = useState<Section[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing,  setEditing]  = useState<Section | null>(null);
  const [form,     setForm]     = useState({ name: '', grade: '', section_label: '', teacher_id: '' });
  const [saving,   setSaving]   = useState(false);

  async function load() {
    const [sRes, tRes] = await Promise.all([
      fetch(`${API}/api/school/sections`,  { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API}/api/school/teachers`,  { headers: { Authorization: `Bearer ${token}` } }),
    ]);
    if (sRes.ok) setSections(await sRes.json());
    if (tRes.ok) setTeachers(await tRes.json());
    setLoading(false);
  }

  useEffect(() => { if (token) load(); }, [token]);

  function openNew() {
    setEditing(null);
    setForm({ name: '', grade: '', section_label: '', teacher_id: '' });
    setShowForm(true);
  }

  function openEdit(s: Section) {
    setEditing(s);
    setForm({
      name: s.name, grade: s.grade ?? '', section_label: s.section_label ?? '',
      teacher_id: s.teacher_id ?? '',
    });
    setShowForm(true);
  }

  async function save() {
    setSaving(true);
    try {
      const body = {
        name: form.name, grade: form.grade || null,
        section_label: form.section_label || null,
        teacher_id: form.teacher_id || null,
      };
      const res = editing
        ? await fetch(`${API}/api/school/sections/${editing.id}`, {
            method: 'PATCH',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          })
        : await fetch(`${API}/api/school/sections`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          });
      if (res.ok) { setShowForm(false); await load(); }
    } finally { setSaving(false); }
  }

  async function del(id: string) {
    if (!confirm('Delete this section? Students will lose their section assignment.')) return;
    await fetch(`${API}/api/school/sections/${id}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    });
    await load();
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[var(--tx1)] text-xl font-bold">Sections</h1>
        <button
          onClick={openNew}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500
                     text-white text-sm rounded-xl transition-colors"
        >
          <Plus size={15} /> New Section
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-6">
          <h2 className="text-[var(--tx1)] font-semibold text-sm mb-4">
            {editing ? 'Edit Section' : 'Create Section'}
          </h2>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div className="col-span-2">
              <label className="block text-xs text-[var(--tx6)] mb-1">Section Name *</label>
              <input
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="e.g. Class IX - A"
                className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                           text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--tx6)] mb-1">Grade</label>
              <input
                value={form.grade}
                onChange={e => setForm(f => ({ ...f, grade: e.target.value }))}
                placeholder="e.g. 9"
                className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                           text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--tx6)] mb-1">Section Label</label>
              <input
                value={form.section_label}
                onChange={e => setForm(f => ({ ...f, section_label: e.target.value }))}
                placeholder="e.g. A"
                className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                           text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-[var(--tx6)] mb-1">Assign Teacher</label>
              <select
                value={form.teacher_id}
                onChange={e => setForm(f => ({ ...f, teacher_id: e.target.value }))}
                className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                           text-[var(--tx1)] outline-none focus:border-purple-500/60"
              >
                <option value="">— No teacher —</option>
                {teachers.map(t => (
                  <option key={t.id} value={t.id}>{t.name} ({t.email})</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={save}
              disabled={saving || !form.name.trim()}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl
                         transition-colors disabled:opacity-40"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : editing ? 'Save' : 'Create'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-4 py-2 bg-[var(--ov2)] text-[var(--tx4)] text-sm rounded-xl hover:bg-[var(--ov3)] transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Section list */}
      {sections.length === 0 ? (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-8 text-center">
          <Layers size={32} className="text-[var(--tx7)] mx-auto mb-3" />
          <p className="text-[var(--tx5)] text-sm">No sections yet.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {sections.map(s => (
            <div
              key={s.id}
              className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl px-5 py-4
                         flex items-center justify-between"
            >
              <div>
                <p className="text-[var(--tx1)] font-medium text-sm">{s.name}</p>
                <p className="text-[var(--tx7)] text-xs mt-0.5">
                  {s.teacher_name
                    ? <>Teacher: <span className="text-[var(--tx5)]">{s.teacher_name}</span></>
                    : <span className="text-amber-400">No teacher</span>
                  }
                  <span className="mx-2 text-[var(--bd)]">·</span>
                  <Users size={11} className="inline mr-0.5" />
                  {s.student_count} students
                </p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => openEdit(s)}
                  className="p-2 text-[var(--tx7)] hover:text-[var(--tx2)] rounded-lg hover:bg-[var(--ov2)] transition-colors"
                >
                  <Pencil size={14} />
                </button>
                <button
                  onClick={() => del(s.id)}
                  className="p-2 text-[var(--tx7)] hover:text-red-400 rounded-lg hover:bg-[var(--ov2)] transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
