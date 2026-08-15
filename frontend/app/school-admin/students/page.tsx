'use client';
import { useEffect, useState } from 'react';
import { Users, Loader2, Upload, Plus, Pencil, Trash2, ArchiveRestore, Archive, Eye, EyeOff, X, Check } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Student {
  id: string; name: string; email: string | null; roll_number: string | null;
  section_id: string | null; section_name: string | null; is_active: boolean;
}
interface Section { id: string; name: string; }

const EMPTY_EDIT = { name: '', roll_number: '', email: '', section_id: '', password: '' };

export default function StudentsPage() {
  const { token } = useSessionStore();
  const [students,      setStudents]      = useState<Student[]>([]);
  const [sections,      setSections]      = useState<Section[]>([]);
  const [loading,       setLoading]       = useState(true);
  const [filterSec,     setFilterSec]     = useState('');
  const [showArchived,  setShowArchived]  = useState(false);
  const [tab,           setTab]           = useState<'list'|'add'|'bulk'>('list');

  // Add form
  const [form,          setForm]          = useState({ name: '', roll_number: '', email: '', section_id: '', password: '' });

  // Edit modal
  const [editing,       setEditing]       = useState<Student | null>(null);
  const [editForm,      setEditForm]      = useState({ ...EMPTY_EDIT });
  const [showEditPwd,   setShowEditPwd]   = useState(false);
  const [editSaving,    setEditSaving]    = useState(false);

  // Bulk import
  const [csvText,       setCsvText]       = useState('name,roll_number\n');
  const [bulkSec,       setBulkSec]       = useState('');
  const [saving,        setSaving]        = useState(false);
  const [bulkResult,    setBulkResult]    = useState<any[] | null>(null);

  async function load(sec?: string, archived?: boolean) {
    const params = new URLSearchParams();
    if (sec) params.set('section_id', sec);
    if (archived ?? showArchived) params.set('include_archived', 'true');
    const [sRes, secRes] = await Promise.all([
      fetch(`${API}/api/school/students?${params}`, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API}/api/school/sections`,            { headers: { Authorization: `Bearer ${token}` } }),
    ]);
    if (sRes.ok)   setStudents(await sRes.json());
    if (secRes.ok) setSections(await secRes.json());
    setLoading(false);
  }

  useEffect(() => { if (token) load(); }, [token]);

  // ── Add single student ──────────────────────────────────────────────────────
  async function addStudent() {
    if (!form.name.trim() || !form.roll_number.trim()) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/school/students`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name, roll_number: form.roll_number,
          email: form.email.trim() || null,
          section_id: form.section_id || null,
          password: form.password || null,
        }),
      });
      if (res.ok) {
        setForm({ name: '', roll_number: '', email: '', section_id: '', password: '' });
        setTab('list'); await load();
      }
    } finally { setSaving(false); }
  }

  // ── Edit modal ──────────────────────────────────────────────────────────────
  function openEdit(s: Student) {
    setEditing(s);
    setEditForm({
      name: s.name,
      roll_number: s.roll_number ?? '',
      email: s.email ?? '',
      section_id: s.section_id ?? '',
      password: '',
    });
    setShowEditPwd(false);
  }

  async function saveEdit() {
    if (!editing) return;
    setEditSaving(true);
    try {
      const body: Record<string, any> = {};
      if (editForm.name !== editing.name)                    body.name        = editForm.name.trim();
      if (editForm.roll_number !== (editing.roll_number??'')) body.roll_number = editForm.roll_number.trim();
      if (editForm.email !== (editing.email??''))             body.email       = editForm.email.trim() || null;
      if (editForm.section_id !== (editing.section_id??''))   body.section_id  = editForm.section_id || null;
      if (editForm.password)                                  body.password    = editForm.password;

      const res = await fetch(`${API}/api/school/students/${editing.id}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) { setEditing(null); await load(filterSec || undefined, showArchived); }
    } finally { setEditSaving(false); }
  }

  async function toggleArchive(s: Student) {
    const action = s.is_active ? 'Archive' : 'Restore';
    if (!confirm(`${action} ${s.name}?`)) return;
    await fetch(`${API}/api/school/students/${s.id}`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: !s.is_active }),
    });
    await load(filterSec || undefined, showArchived);
  }

  async function hardDelete(s: Student) {
    if (!confirm(`Permanently delete ${s.name}? This cannot be undone.`)) return;
    await fetch(`${API}/api/school/students/${s.id}?hard=true`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    });
    await load(filterSec || undefined, showArchived);
  }

  // ── Bulk import ─────────────────────────────────────────────────────────────
  async function bulkImport() {
    if (!bulkSec) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/school/students/bulk-import`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ section_id: bulkSec, csv_text: csvText }),
      });
      if (res.ok) {
        const d = await res.json();
        setBulkResult(d.results);
        await load();
      }
    } finally { setSaving(false); }
  }

  function applyFilter(sec: string) {
    setFilterSec(sec);
    load(sec || undefined, showArchived);
  }

  function toggleShowArchived() {
    const next = !showArchived;
    setShowArchived(next);
    load(filterSec || undefined, next);
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  const active   = students.filter(s => s.is_active);
  const archived = students.filter(s => !s.is_active);

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-[var(--tx1)] text-xl font-bold">Students</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setTab('add')}
            className="flex items-center gap-1.5 px-3 py-2 bg-purple-600 hover:bg-purple-500
                       text-white text-sm rounded-xl transition-colors"
          >
            <Plus size={14} /> Add
          </button>
          <button
            onClick={() => { setTab('bulk'); setBulkResult(null); }}
            className="flex items-center gap-1.5 px-3 py-2 bg-[var(--ov3)] hover:bg-[var(--ov4)]
                       text-[var(--tx2)] text-sm rounded-xl transition-colors"
          >
            <Upload size={14} /> Bulk Import
          </button>
        </div>
      </div>

      {/* Add form */}
      {tab === 'add' && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-5">
          <h2 className="text-[var(--tx1)] font-semibold text-sm mb-4">Add Student</h2>
          <div className="grid grid-cols-2 gap-3 mb-3">
            {([
              { label: 'Full Name *', key: 'name', placeholder: 'Student name' },
              { label: 'Roll Number *', key: 'roll_number', placeholder: 'e.g. S001' },
              { label: 'Email', key: 'email', placeholder: 'optional — auto-generated if blank', type: 'email' },
              { label: 'Password (default = roll number)', key: 'password', placeholder: 'Leave blank to use roll number' },
            ] as const).map(f => (
              <div key={f.key} className={f.key === 'email' || f.key === 'password' ? 'col-span-2' : ''}>
                <label className="block text-xs text-[var(--tx6)] mb-1">{f.label}</label>
                <input
                  value={form[f.key]}
                  onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                  type={('type' in f ? f.type : 'text') as string}
                  className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                             text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
                />
              </div>
            ))}
            <div className="col-span-2">
              <label className="block text-xs text-[var(--tx6)] mb-1">Classroom</label>
              <select
                value={form.section_id}
                onChange={e => setForm(f => ({ ...f, section_id: e.target.value }))}
                className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                           text-[var(--tx1)] outline-none focus:border-purple-500/60"
              >
                <option value="">— No classroom —</option>
                {sections.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={addStudent} disabled={saving || !form.name || !form.roll_number}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl disabled:opacity-40">
              {saving ? <Loader2 size={14} className="animate-spin" /> : 'Add Student'}
            </button>
            <button onClick={() => setTab('list')}
              className="px-4 py-2 bg-[var(--ov2)] text-[var(--tx4)] text-sm rounded-xl hover:bg-[var(--ov3)]">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Bulk import */}
      {tab === 'bulk' && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-5">
          <h2 className="text-[var(--tx1)] font-semibold text-sm mb-1">Bulk Import via CSV</h2>
          <p className="text-[var(--tx7)] text-xs mb-4">
            Columns: <code className="bg-[var(--ov2)] px-1 rounded">name,roll_number</code> — default password = roll number.
          </p>
          <div className="mb-3">
            <label className="block text-xs text-[var(--tx6)] mb-1">Classroom *</label>
            <select value={bulkSec} onChange={e => setBulkSec(e.target.value)}
              className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                         text-[var(--tx1)] outline-none focus:border-purple-500/60">
              <option value="">— Select classroom —</option>
              {sections.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <textarea
            value={csvText} onChange={e => setCsvText(e.target.value)} rows={8}
            className="w-full font-mono text-xs bg-[var(--ov2)] border border-[var(--bd)] rounded-xl p-3
                       text-[var(--tx2)] outline-none focus:border-purple-500/60 resize-none mb-3"
          />
          <div className="flex gap-2 mb-4">
            <button onClick={bulkImport} disabled={saving || !bulkSec}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl disabled:opacity-40">
              {saving ? <Loader2 size={14} className="animate-spin" /> : 'Import'}
            </button>
            <button onClick={() => { setTab('list'); setBulkResult(null); }}
              className="px-4 py-2 bg-[var(--ov2)] text-[var(--tx4)] text-sm rounded-xl hover:bg-[var(--ov3)]">
              Cancel
            </button>
          </div>
          {bulkResult && (
            <div className="border border-[var(--bd)] rounded-xl overflow-hidden">
              {bulkResult.map((r, i) => (
                <div key={i} className={`flex items-center justify-between px-4 py-2.5 text-sm border-b border-[var(--bd)] last:border-b-0
                  ${r.status === 'created' ? 'bg-green-500/5' : r.status === 'error' ? 'bg-red-500/5' : ''}`}>
                  <span className="text-[var(--tx2)]">{r.name ?? r.roll_number}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    r.status === 'created' ? 'bg-green-500/20 text-green-400' :
                    r.status === 'skipped' ? 'bg-amber-500/20 text-amber-400' :
                    'bg-red-500/20 text-red-400'}`}>
                    {r.status}{r.reason ? ` — ${r.reason}` : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Filter bar */}
      <div className="flex items-center gap-3 mb-4">
        <select value={filterSec} onChange={e => applyFilter(e.target.value)}
          className="bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                     text-[var(--tx2)] outline-none focus:border-purple-500/60">
          <option value="">All Classrooms</option>
          {sections.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button
          onClick={toggleShowArchived}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs rounded-xl border transition-colors ${
            showArchived
              ? 'border-amber-500/40 bg-amber-500/10 text-amber-400'
              : 'border-[var(--bd)] bg-[var(--ov2)] text-[var(--tx6)] hover:text-[var(--tx3)]'
          }`}
        >
          <Archive size={13} /> {showArchived ? 'Hide Archived' : 'Show Archived'}
        </button>
        <span className="text-[var(--tx7)] text-sm ml-auto">{active.length} active{archived.length > 0 ? `, ${archived.length} archived` : ''}</span>
      </div>

      {/* Active students */}
      {active.length === 0 && !showArchived ? (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-8 text-center">
          <Users size={32} className="text-[var(--tx7)] mx-auto mb-3" />
          <p className="text-[var(--tx5)] text-sm">No students yet.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {active.map(s => <StudentRow key={s.id} s={s} sections={sections} onEdit={openEdit} onArchive={toggleArchive} onDelete={hardDelete} />)}
          {showArchived && archived.length > 0 && (
            <>
              <p className="text-xs text-[var(--tx7)] mt-3 mb-1 font-semibold uppercase tracking-wide">Archived</p>
              {archived.map(s => <StudentRow key={s.id} s={s} sections={sections} onEdit={openEdit} onArchive={toggleArchive} onDelete={hardDelete} />)}
            </>
          )}
        </div>
      )}

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[var(--tx1)] font-semibold">Edit Student</h2>
              <button onClick={() => setEditing(null)} className="text-[var(--tx7)] hover:text-[var(--tx3)]">
                <X size={18} />
              </button>
            </div>
            <div className="flex flex-col gap-3">
              {([
                { label: 'Name', key: 'name' },
                { label: 'Roll Number', key: 'roll_number' },
                { label: 'Email', key: 'email', type: 'email' },
              ] as const).map(f => (
                <div key={f.key}>
                  <label className="block text-xs text-[var(--tx6)] mb-1">{f.label}</label>
                  <input
                    value={editForm[f.key]}
                    onChange={e => setEditForm(p => ({ ...p, [f.key]: e.target.value }))}
                    type={('type' in f ? f.type : 'text') as string}
                    className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                               text-[var(--tx1)] outline-none focus:border-purple-500/60"
                  />
                </div>
              ))}
              <div>
                <label className="block text-xs text-[var(--tx6)] mb-1">Classroom</label>
                <select value={editForm.section_id} onChange={e => setEditForm(p => ({ ...p, section_id: e.target.value }))}
                  className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                             text-[var(--tx1)] outline-none focus:border-purple-500/60">
                  <option value="">— None —</option>
                  {sections.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-[var(--tx6)] mb-1">
                  New Password <span className="text-[var(--tx7)]">(leave blank to keep current)</span>
                </label>
                <div className="relative">
                  <input
                    value={editForm.password}
                    onChange={e => setEditForm(p => ({ ...p, password: e.target.value }))}
                    type={showEditPwd ? 'text' : 'password'}
                    placeholder="Enter new password"
                    className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 pr-10 text-sm
                               text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
                  />
                  <button type="button" onClick={() => setShowEditPwd(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--tx7)] hover:text-[var(--tx3)]">
                    {showEditPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>
            </div>
            <div className="flex gap-2 mt-5">
              <button onClick={saveEdit} disabled={editSaving}
                className="flex-1 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl disabled:opacity-40 flex items-center justify-center gap-2">
                {editSaving ? <Loader2 size={14} className="animate-spin" /> : <><Check size={14} /> Save</>}
              </button>
              <button onClick={() => setEditing(null)}
                className="px-4 py-2 bg-[var(--ov2)] text-[var(--tx4)] text-sm rounded-xl hover:bg-[var(--ov3)]">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StudentRow({
  s, sections, onEdit, onArchive, onDelete,
}: {
  s: Student; sections: Section[];
  onEdit: (s: Student) => void;
  onArchive: (s: Student) => void;
  onDelete: (s: Student) => void;
}) {
  return (
    <div className={`flex items-center justify-between border rounded-xl px-4 py-3 transition-colors
      ${s.is_active
        ? 'bg-[var(--surface)] border-[var(--bd)]'
        : 'bg-[var(--ov1)] border-[var(--bd)] opacity-60'
      }`}>
      <div>
        <p className="text-[var(--tx1)] text-sm font-medium">{s.name}
          {!s.is_active && <span className="ml-2 text-xs text-amber-400 font-normal">(archived)</span>}
        </p>
        <p className="text-[var(--tx7)] text-xs">
          Roll: {s.roll_number ?? '—'}
          {s.section_name && <span className="ml-2 text-purple-400">{s.section_name}</span>}
          {s.email && !s.email.includes('@students.learnxai.internal') && (
            <span className="ml-2 text-[var(--tx6)]">{s.email}</span>
          )}
        </p>
      </div>
      <div className="flex items-center gap-1">
        <button onClick={() => onEdit(s)} title="Edit"
          className="p-2 text-[var(--tx7)] hover:text-[var(--tx2)] rounded-lg hover:bg-[var(--ov2)] transition-colors">
          <Pencil size={14} />
        </button>
        <button onClick={() => onArchive(s)} title={s.is_active ? 'Archive' : 'Restore'}
          className="p-2 text-[var(--tx7)] hover:text-amber-400 rounded-lg hover:bg-[var(--ov2)] transition-colors">
          {s.is_active ? <Archive size={14} /> : <ArchiveRestore size={14} />}
        </button>
        <button onClick={() => onDelete(s)} title="Permanently delete"
          className="p-2 text-[var(--tx7)] hover:text-red-400 rounded-lg hover:bg-[var(--ov2)] transition-colors">
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
