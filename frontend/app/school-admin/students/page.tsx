'use client';
import { useEffect, useState } from 'react';
import { Users, Loader2, Upload, Plus, Trash2 } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Student {
  id: string; name: string; roll_number: string | null;
  section_id: string | null; section_name: string | null; is_active: boolean;
}
interface Section { id: string; name: string; }

export default function StudentsPage() {
  const { token } = useSessionStore();
  const [students,   setStudents]   = useState<Student[]>([]);
  const [sections,   setSections]   = useState<Section[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [filterSec,  setFilterSec]  = useState('');
  const [tab,        setTab]        = useState<'list'|'add'|'bulk'>('list');
  const [form,       setForm]       = useState({ name: '', roll_number: '', email: '', section_id: '', password: '' });
  const [csvText,    setCsvText]    = useState('name,roll_number\n');
  const [bulkSec,    setBulkSec]    = useState('');
  const [saving,     setSaving]     = useState(false);
  const [bulkResult, setBulkResult] = useState<any[] | null>(null);

  async function load(sec?: string) {
    const url = sec ? `${API}/api/school/students?section_id=${sec}` : `${API}/api/school/students`;
    const [sRes, secRes] = await Promise.all([
      fetch(url, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API}/api/school/sections`, { headers: { Authorization: `Bearer ${token}` } }),
    ]);
    if (sRes.ok)   setStudents(await sRes.json());
    if (secRes.ok) setSections(await secRes.json());
    setLoading(false);
  }

  useEffect(() => { if (token) load(); }, [token]);

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
      if (res.ok) { setForm({ name: '', roll_number: '', email: '', section_id: '', password: '' }); setTab('list'); await load(); }
    } finally { setSaving(false); }
  }

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

  async function del(id: string) {
    if (!confirm('Remove this student?')) return;
    await fetch(`${API}/api/school/students/${id}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    });
    await load(filterSec);
  }

  function applyFilter(sec: string) {
    setFilterSec(sec);
    load(sec || undefined);
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

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

      {/* Add single student */}
      {tab === 'add' && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-5">
          <h2 className="text-[var(--tx1)] font-semibold text-sm mb-4">Add Student</h2>
          <div className="grid grid-cols-2 gap-3 mb-3">
            {[
              { label: 'Full Name *', key: 'name', placeholder: 'Student name' },
              { label: 'Roll Number *', key: 'roll_number', placeholder: 'e.g. S001' },
              { label: 'Email', key: 'email', placeholder: 'optional — auto-generated if blank', type: 'email' },
              { label: 'Password (default = roll number)', key: 'password', placeholder: 'Leave blank to use roll number' },
            ].map(f => (
              <div key={f.key} className={f.key === 'email' || f.key === 'password' ? 'col-span-2' : ''}>
                <label className="block text-xs text-[var(--tx6)] mb-1">{f.label}</label>
                <input
                  value={(form as any)[f.key]}
                  onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                  type={(f as any).type ?? 'text'}
                  className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                             text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
                />
              </div>
            ))}
            <div className="col-span-2">
              <label className="block text-xs text-[var(--tx6)] mb-1">Section</label>
              <select
                value={form.section_id}
                onChange={e => setForm(f => ({ ...f, section_id: e.target.value }))}
                className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                           text-[var(--tx1)] outline-none focus:border-purple-500/60"
              >
                <option value="">— No section —</option>
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
            Paste CSV with <code className="bg-[var(--ov2)] px-1 rounded">name,roll_number</code> columns.
            Default password = roll number.
          </p>
          <div className="mb-3">
            <label className="block text-xs text-[var(--tx6)] mb-1">Section *</label>
            <select value={bulkSec} onChange={e => setBulkSec(e.target.value)}
              className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                         text-[var(--tx1)] outline-none focus:border-purple-500/60">
              <option value="">— Select section —</option>
              {sections.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <textarea
            value={csvText}
            onChange={e => setCsvText(e.target.value)}
            rows={8}
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

      {/* Filter + list */}
      <div className="flex items-center gap-3 mb-4">
        <select
          value={filterSec}
          onChange={e => applyFilter(e.target.value)}
          className="bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                     text-[var(--tx2)] outline-none focus:border-purple-500/60"
        >
          <option value="">All Classrooms</option>
          {sections.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <span className="text-[var(--tx7)] text-sm">{students.length} students</span>
      </div>

      {students.length === 0 ? (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-8 text-center">
          <Users size={32} className="text-[var(--tx7)] mx-auto mb-3" />
          <p className="text-[var(--tx5)] text-sm">No students yet.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {students.map(s => (
            <div key={s.id}
              className="flex items-center justify-between bg-[var(--surface)] border border-[var(--bd)]
                         rounded-xl px-4 py-3">
              <div>
                <p className="text-[var(--tx1)] text-sm font-medium">{s.name}</p>
                <p className="text-[var(--tx7)] text-xs">
                  Roll: {s.roll_number ?? '—'}
                  {s.section_name && <span className="ml-2 text-purple-400">{s.section_name}</span>}
                </p>
              </div>
              <button onClick={() => del(s.id)}
                className="p-2 text-[var(--tx7)] hover:text-red-400 rounded-lg hover:bg-[var(--ov2)] transition-colors">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
