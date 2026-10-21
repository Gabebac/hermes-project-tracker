/**
 * Project Tracker — desktop UI.
 * A full page at /projects: the projects routine (Ongoing/Building/Maintenance/
 * Ideas/Done) with staleness badges, per-project done/left checklists, inline
 * session logging and quick edits. All writes go through the plugin's backend
 * (ctx.rest), same store the agent tools use.
 * Accents use var(--accent); surfaces/borders ride Hermes theme vars so it
 * reskins.
 */
import { host, ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA, PANES_AREA } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useState } from 'react'
import { jsxs, jsx } from 'react/jsx-runtime'

const ID = 'project-tracker'
const SECTIONS = ['Ongoing (Business)', 'Building', 'Maintenance', 'Ideas', 'Done']
const SECTION_HINT = {
  'Ongoing (Business)': 'Business — never drops; it pauses, doesn\u2019t die',
  'Building': '2 weeks without a logged session flags it',
  'Maintenance': 'upkeep only — checkup every 6 weeks',
  'Ideas': 'promote within 3 Sundays or park',
  'Done': 'an App done here means moved to Maintenance, not deleted',
}

let CTX = null
async function api(path, opts) {
  if (CTX?.rest) return CTX.rest(path, { method: opts?.method || 'GET', body: opts?.body })
  const r = await fetch(`/api/plugins/${ID}${path}`, {
    method: opts?.method || 'GET',
    headers: { 'content-type': 'application/json' },
    body: opts?.body ? JSON.stringify(opts.body) : undefined,
  })
  return r.json()
}

const stale = (p) => p.staleness?.stale
const idle = (p) => (p.staleness?.days_idle == null ? null : p.staleness.days_idle)

function Badge({ text, tone }) {
  const colors = {
    stale: { color: '#ff6b5e', borderColor: 'rgba(255,107,94,0.45)', background: 'rgba(255,107,94,0.12)' },
    okstale: { color: '#e2b93b', borderColor: 'rgba(226,185,59,0.4)', background: 'rgba(226,185,59,0.1)' },
    label: { color: 'var(--ui-text-tertiary, #8f8da6)', borderColor: 'var(--ui-stroke-secondary, rgba(140,140,170,0.3))', background: 'transparent' },
  }
  return jsx('span', {
    style: {
      fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 999,
      border: `1px solid ${colors[tone].borderColor}`, background: colors[tone].background,
      color: colors[tone].color, whiteSpace: 'nowrap',
    },
    children: text,
  })
}

function briefSummary(b, err) {
  if (err) return `evidence unavailable: ${err} (interview falls back to the static brief)`
  if (!b) return 'evidence: not checked yet \u2014 hit Refresh evidence'
  const s = b.sessions_checked || { pinned: 0, recent: 0 }
  return `evidence: ${s.pinned} pinned \u00B7 ${s.recent} recent \u00B7 ${(b.unlogged || []).length} unlogged candidate${(b.unlogged || []).length === 1 ? '' : 's'} \u00B7 ${(b.stale_flags || []).length} stale \u00B7 built ${b.generated_at}`
}

function ItemRow({ p, side, item, onToggle, onRemove }) {
  const checked = side === 'done'
  return jsxs('div', {
    style: { display: 'flex', alignItems: 'flex-start', gap: 6, padding: '2px 0', fontSize: 12 },
    children: [
      jsx('button', {
        title: checked ? 'Move back to left' : 'Mark done',
        onClick: () => onToggle(p, side, item.text),
        onMouseDown: (e) => e.stopPropagation(),
        style: { border: 'none', background: 'transparent', cursor: 'pointer', padding: 0,
          fontSize: 12, color: checked ? '#4caf7d' : 'var(--ui-text-tertiary, #8f8da6)',
          lineHeight: 1.3 },
        children: checked ? '\u2611' : '\u2610',
      }),
      jsx('span', {
        style: { flex: 1, color: 'var(--ui-text-secondary, #c9c8d4)',
          textDecoration: checked ? 'line-through' : 'none', opacity: checked ? 0.7 : 1 },
        children: item.text,
      }),
      jsx('button', {
        title: 'Remove item',
        onMouseDown: (e) => e.stopPropagation(),
        onClick: () => onRemove(p, side, item.text),
        style: { border: 'none', background: 'transparent', cursor: 'pointer', fontSize: 10,
          color: 'var(--ui-text-tertiary, #8f8da6)', padding: '0 3px' },
        children: '\u2715',
      }),
    ],
  })
}

function ProjectCard({ p, open, onOpen, reload }) {
  const [logText, setLogText] = useState('')
  const [logDate, setLogDate] = useState('')
  const [nextAction, setNextAction] = useState(p.next_action || '')
  const [newLeft, setNewLeft] = useState('')
  const [saving, setSaving] = useState(false)

  const post = useCallback(async (path, body) => {
    setSaving(true)
    try { await api(path, { method: 'POST', body }) } finally { setSaving(false) }
    reload()
  }, [reload])

  const st = p.staleness || {}
  const isBusiness = p.section === 'Ongoing (Business)'

  return jsxs('div', {
    style: {
      borderRadius: 10, border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
      background: 'var(--ui-card, var(--card, rgba(255,255,255,0.03)))',
      padding: '10px 12px', marginBottom: 8,
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' },
        onClick: () => onOpen(open ? null : p.name),
        children: [
          jsx('span', { style: { fontSize: 13, fontWeight: 600, color: 'var(--ui-text-primary, #fafafa)' }, children: p.name }),
          jsx(Badge, { text: p.label, tone: 'label' }),
          stale(p) && jsx(Badge, { text: `STALE \u00B7 ${st.days_idle}d`, tone: 'stale' }),
          !stale(p) && !isBusiness && idle(p) != null && jsx(Badge, { text: `${idle(p)}d idle`, tone: 'okstale' }),
          isBusiness && !p.phase && !p.next_action && jsx(Badge, { text: 'paused', tone: 'okstale' }),
          jsx('span', { style: { marginLeft: 'auto', fontSize: 10.5, color: 'var(--ui-text-tertiary, #8f8da6)' },
            children: p.phase || st.rule || '' }),
        ],
      }),
      !open && p.next_action && jsx('div', {
        style: { fontSize: 11.5, color: 'var(--ui-text-tertiary, #8f8da6)', marginTop: 4 },
        children: `Next: ${p.next_action}`,
      }),
      open && jsxs('div', {
        style: { marginTop: 8, borderTop: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.25))', paddingTop: 6 },
        children: [
          jsxs('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 },
            children: [
              jsxs('div', {}, [
                jsx('div', { style: { fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.4,
                  color: 'var(--ui-text-tertiary, #8f8da6)', margin: '4px 0' }, children: 'Left to complete' }),
                p.left.map((i, k) => jsx(ItemRow, { p, side: 'left', item: i, key: k,
                  onToggle: (pp, side, text) => post('/item', { name: pp.name, action: 'check', side, text }),
                  onRemove: (pp, side, text) => post('/item', { name: pp.name, action: 'remove', side, text }) })),
                jsx('input', {
                  value: newLeft, placeholder: 'add item + Enter',
                  onChange: (e) => setNewLeft(e.target.value),
                  onKeyDown: (e) => { if (e.key === 'Enter' && newLeft.trim()) { post('/item', { name: p.name, action: 'add', side: 'left', text: newLeft.trim() }); setNewLeft('') } },
                  onMouseDown: (e) => e.stopPropagation(),
                  style: { width: '100%', fontSize: 11, marginTop: 4, borderRadius: 6, padding: '4px 8px',
                    background: 'rgba(127,127,127,0.08)', border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
                    color: 'var(--ui-text-primary, #fafafa)', outline: 'none' },
                }),
              ]),
              jsx('div', {}, [
                jsx('div', { style: { fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.4,
                  color: 'var(--ui-text-tertiary, #8f8da6)', margin: '4px 0' }, children: 'Done' }),
                p.done.map((i, k) => jsx(ItemRow, { p, side: 'done', item: i, key: k,
                  onToggle: (pp, side, text) => post('/item', { name: pp.name, action: 'uncheck', side, text }),
                  onRemove: (pp, side, text) => post('/item', { name: pp.name, action: 'remove', side, text }) })),
              ]),
            ],
          }),
          jsxs('div', { style: { marginTop: 10, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }, children: [
            jsx('input', {
              value: logText, placeholder: 'log a 1-hour session\u2026',
              onChange: (e) => setLogText(e.target.value),
              onMouseDown: (e) => e.stopPropagation(),
              onKeyDown: (e) => { if (e.key === 'Enter' && logText.trim()) { post('/session', { name: p.name, text: logText.trim(), date: logDate || undefined }); setLogText('') } },
              style: { flex: 1, minWidth: 160, fontSize: 11.5, borderRadius: 6, padding: '5px 8px',
                background: 'rgba(127,127,127,0.08)', border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
                color: 'var(--ui-text-primary, #fafafa)', outline: 'none' },
            }),
            jsx('input', {
              type: 'date', value: logDate, onChange: (e) => setLogDate(e.target.value),
              onMouseDown: (e) => e.stopPropagation(),
              style: { fontSize: 11, borderRadius: 6, padding: '4px 6px',
                background: 'rgba(127,127,127,0.08)', border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
                color: 'var(--ui-text-primary, #fafafa)', outline: 'none' },
            }),
            jsx('button', {
              disabled: !logText.trim() || saving,
              onClick: () => { post('/session', { name: p.name, text: logText.trim(), date: logDate || undefined }); setLogText('') },
              style: { fontSize: 11, padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
                border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
                background: 'var(--accent, #6c5ce7)', color: '#fff', fontWeight: 600,
                opacity: !logText.trim() || saving ? 0.5 : 1 },
              children: 'Log',
            }),
          ] }),
          jsxs('div', { style: { marginTop: 6, display: 'flex', gap: 6, alignItems: 'center' }, children: [
            jsx('input', {
              value: nextAction, placeholder: 'next action\u2026',
              onChange: (e) => setNextAction(e.target.value),
              onMouseDown: (e) => e.stopPropagation(),
              style: { flex: 1, fontSize: 11.5, borderRadius: 6, padding: '5px 8px',
                background: 'rgba(127,127,127,0.08)', border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
                color: 'var(--ui-text-primary, #fafafa)', outline: 'none' },
            }),
            (nextAction !== (p.next_action || '')) && jsx('button', {
              onClick: () => post('/set', { name: p.name, next_action: nextAction.trim() }),
              style: { fontSize: 11, padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
                border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
                background: 'transparent', color: 'var(--accent, #6c5ce7)', fontWeight: 600 },
              children: 'Save next action',
            }),
          ] }),
          jsxs('div', { style: { marginTop: 6, fontSize: 10.5, color: 'var(--ui-text-quaternary, #77768c)', display: 'flex', gap: 10, flexWrap: 'wrap' }, children: [
            jsx('span', { children: `label ${p.label} \u00B7 section ${p.section}` }),
            jsx('span', { children: `created ${p.created}` }),
            jsx('span', { children: `last update ${p.last_update}` }),
            p.promote_by && jsx('span', { children: `promote by ${p.promote_by}` }),
            p.repo && jsx('span', { children: p.repo }),
          ] }),
        ],
      }),
    ],
  })
}

function NewProjectForm({ reload }) {
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ name: '', label: 'App', phase: '', next_action: '' })
  const [saving, setSaving] = useState(false)
  if (!open) {
    return jsx('button', {
      onClick: () => setOpen(true),
      style: { fontSize: 11.5, padding: '4px 12px', borderRadius: 6, cursor: 'pointer',
        border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
        background: 'transparent', color: 'var(--ui-text-secondary, #c9c8d4)' },
      children: '+ Track a project',
    })
  }
  const submit = async () => {
    if (!f.name.trim() || saving) return
    setSaving(true)
    try {
      await api('/project', { method: 'POST', body: { name: f.name.trim(), label: f.label, phase: f.phase.trim(), next_action: f.next_action.trim() } })
      setOpen(false); setF({ name: '', label: 'App', phase: '', next_action: '' })
      reload()
    } finally { setSaving(false) }
  }
  const inp = (key, ph, style2) => jsx('input', {
    value: f[key], placeholder: ph,
    onChange: (e) => setF((o) => ({ ...o, [key]: e.target.value })),
    onKeyDown: (e) => { if (e.key === 'Enter') submit() },
    onMouseDown: (e) => e.stopPropagation(),
    style: { fontSize: 11.5, borderRadius: 6, padding: '5px 8px',
      background: 'rgba(127,127,127,0.08)', border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
      color: 'var(--ui-text-primary, #fafafa)', outline: 'none', ...style2 },
  })
  return jsxs('div', {
    style: { display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 },
    onMouseDown: (e) => e.stopPropagation(),
    children: [
      inp('name', 'project name', { width: 170 }),
      jsx('select', {
        value: f.label, onChange: (e) => setF((o) => ({ ...o, label: e.target.value })),
        style: { fontSize: 11.5, borderRadius: 6, padding: '4px 6px',
          background: 'rgba(127,127,127,0.08)', border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
          color: 'var(--ui-text-primary, #fafafa)', outline: 'none' },
        children: ['Business', 'App', 'Personal', 'Idea'].map((l) => jsx('option', { value: l, children: l })),
      }),
      inp('phase', 'phase (optional)', { width: 150 }),
      inp('next_action', 'next action (optional)', { width: 190 }),
      jsx('button', {
        onClick: submit, disabled: saving,
        style: { fontSize: 11.5, padding: '4px 12px', borderRadius: 6, cursor: 'pointer',
          border: 'none', background: 'var(--accent, #6c5ce7)', color: '#fff', fontWeight: 600 },
        children: 'Add',
      }),
      jsx('button', {
        onClick: () => setOpen(false),
        style: { fontSize: 11.5, padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
          border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
          background: 'transparent', color: 'var(--ui-text-secondary, #c9c8d4)' },
        children: 'Cancel',
      }),
    ],
  })
}

function ProjectsPage() {
  const [data, setData] = useState(null)
  const [openName, setOpenName] = useState(null)
  const [err, setErr] = useState('')
  const [brief, setBrief] = useState(null)
  const [briefErr, setBriefErr] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const reload = useCallback(async () => {
    try {
      const d = await api('/state')
      if (d && d.projects) setData(d)
      else if (d && d.error) setErr(d.error)
    } catch (e) { setErr(String(e)) }
  }, [])

  const refreshAll = useCallback(async () => {
    setRefreshing(true)
    try {
      const b = await api('/brief')
      if (b && b.brief) setBrief(b)
      else setBriefErr(b && b.error ? b.error : 'no evidence returned')
    } catch (e) { setBriefErr(String(e)) }
    setRefreshing(false)
    reload()
  }, [reload])

  useEffect(() => { refreshAll() }, [refreshAll])   // refresh evidences the tracker too

  if (err) return jsx('div', { style: { padding: 20, color: 'var(--ui-text-secondary, #ccc)' }, children: `Backend unreachable: ${err}` })
  if (!data) return jsx('div', { style: { padding: 20, color: 'var(--ui-text-tertiary, #888)' }, children: 'Loading projects\u2026' })

  const staleList = data.projects.filter(stale)

  return jsxs('div', {
    style: { height: '100%', overflowY: 'auto', padding: '16px 20px', boxSizing: 'border-box' },
    children: [
      jsx('div', { style: { fontSize: 11, color: 'var(--ui-text-tertiary, #8f8da6)', marginBottom: 10 },
        children: briefSummary(brief, briefErr) }),
      jsxs('div', { style: { display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 10 }, children: [
        jsx('h1', { style: { fontSize: 18, margin: 0, color: 'var(--ui-text-primary, #fafafa)' }, children: 'Projects' }),
        jsx('span', { style: { fontSize: 11, color: 'var(--ui-text-tertiary, #8f8da6)' },
          children: `${data.projects.length} tracked \u00B7 ${staleList.length} stale \u00B7 reviewed Sundays with Hermes \u00B7 1h/day on any project` }),
        jsx('button', {
          title: 'Re-run the evidence pass: checks the pinned and recent desktop sessions against the tracker log, raises unlogged work, and refreshes the interview questions',
          onClick: () => refreshAll(),
          disabled: refreshing,
          style: { fontSize: 11.5, padding: '4px 12px', borderRadius: 6, cursor: 'pointer',
            border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
            background: 'transparent', color: 'var(--accent, #6c5ce7)', fontWeight: 600,
            opacity: refreshing ? 0.6 : 1 },
          children: refreshing ? '\u21BB checking\u2026' : '\u21BB Refresh evidence',
        }),
        jsx('button', {
          title: 'Open a new session and start the projects interview there',
          onClick: () => startInterview(),
          style: { marginLeft: 'auto', fontSize: 11.5, padding: '4px 12px', borderRadius: 6, cursor: 'pointer',
            border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))',
            background: 'var(--accent, #6c5ce7)', color: '#fff', fontWeight: 600 },
          children: '\u2694 Interview',
        }),
        jsx('div', { children: jsx(NewProjectForm, { reload }) }),
      ] }),
      staleList.length > 0 && jsxs('div', {
        style: { borderRadius: 10, border: '1px solid rgba(255,107,94,0.35)', background: 'rgba(255,107,94,0.07)',
          padding: '8px 12px', marginBottom: 12, fontSize: 12, color: 'var(--ui-text-secondary, #c9c8d4)' },
        children: [
          jsx('span', { style: { fontWeight: 700, color: '#ff6b5e' }, children: 'Stale \u2014 decide at Sunday review: re-commit / park / drop. ' }),
          jsx('span', { children: staleList.map((p) => `${p.name} (${p.staleness.days_idle != null ? `idle ${p.staleness.days_idle}d` : p.staleness.rule})`).join(' \u00B7 ') }),
        ],
      }),
      SECTIONS.map((sec) => {
        const list = data.projects.filter((p) => p.section === sec)
        if (!list.length) return null
        return jsxs('div', { key: sec, style: { marginBottom: 14 }, children: [
          jsxs('div', { style: { display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }, children: [
            jsx('div', { style: { fontSize: 11.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5,
              color: 'var(--ui-text-tertiary, #8f8da6)' }, children: sec }),
            jsx('span', { style: { fontSize: 10.5, color: 'var(--ui-text-quaternary, #77768c)' },
              children: SECTION_HINT[sec] || '' }),
          ] }),
          list.map((p) => jsx(ProjectCard, { p, key: p.name, open: openName === p.name,
            onOpen: setOpenName, reload })),
        ] })
      }),
      data.projects.length === 0 && jsx('div', { style: { fontSize: 12, color: 'var(--ui-text-tertiary, #8f8da6)' }, children: 'No projects tracked yet \u2014 add one above, or ask Hermes.' }),
    ],
  })
}

/* Right-rail companion: compact, sits where the Quota/Review panes dock. */
function ProjectsRail() {
  const [data, setData] = useState(null)
  const [briefAt, setBriefAt] = useState('')
  const reload = useCallback(async () => {
    try {
      const d = await api('/state')
      if (d && d.projects) setData(d)
    } catch { /* pane retries on next interaction */ }
  }, [])
  const refreshRail = useCallback(async () => {
    try {
      const b = await api('/brief')
      if (b && b.generated_at) setBriefAt(b.generated_at)
    } catch { /* keep the last stamp */ }
    reload()
  }, [reload])
  useEffect(() => { refreshRail() }, [refreshRail])
  if (!data) return jsx('div', { style: { padding: 8, fontSize: 11, color: 'var(--ui-text-tertiary, #8f8da6)' }, children: 'Projects\u2026' })
  const staleList = data.projects.filter(stale)
  const open = (name) => {
    host.navigate('/projects')
  }
  const row = (p) => jsxs('div', {
    onClick: () => open(p.name),
    style: { display: 'flex', alignItems: 'center', gap: 6, padding: '3px 4px', borderRadius: 6,
      cursor: 'pointer', fontSize: 11.5 },
    children: [
      jsx('span', { style: { flex: 1, color: 'var(--ui-text-secondary, #c9c8d4)',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }, children: p.name }),
      stale(p) && jsx(Badge, { text: `${p.staleness.days_idle ?? '!'}d`, tone: 'stale' }),
      !stale(p) && idle(p) != null && jsx(Badge, { text: `${idle(p)}d`, tone: 'okstale' }),
    ],
  })
  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', padding: '4px 2px' },
    children: [
      jsx('div', {
        onClick: () => host.navigate('/projects'),
        style: { display: 'flex', alignItems: 'baseline', gap: 6, padding: '2px 4px 6px', cursor: 'pointer' },
        children: [
          jsx('span', { style: { fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5,
            color: 'var(--ui-text-tertiary, #8f8da6)' }, children: `Projects \u00B7 ${data.projects.length}` }),
          jsx('button', {
            title: `Refresh evidence (pinned + recent sessions vs the tracker log)${briefAt ? ' \u00B7 last built ' + briefAt : ''}`,
            onMouseDown: (e) => { e.preventDefault(); e.stopPropagation() },
            onClick: (e) => { e.stopPropagation(); refreshRail() },
            style: { fontSize: 10, padding: '1px 7px', borderRadius: 999, cursor: 'pointer',
              border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.35))',
              background: 'transparent', color: 'var(--ui-text-tertiary, #8f8da6)', fontWeight: 600 },
            children: '\u21BB',
          }),
          jsx('button', {
            title: 'Start a projects interview in a new session',
            onMouseDown: (e) => { e.preventDefault(); e.stopPropagation() },
            onClick: (e) => { e.stopPropagation(); startInterview() },
            style: { marginLeft: 'auto', fontSize: 9.5, padding: '1px 8px', borderRadius: 999, cursor: 'pointer',
              border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.35))',
              background: 'transparent', color: 'var(--ui-text-tertiary, #8f8da6)', fontWeight: 600 },
            children: '\u2694 interview',
          }),
        ],
      }),
      staleList.length > 0 && jsxs('div', {
        style: { borderRadius: 8, border: '1px solid rgba(255,107,94,0.35)', background: 'rgba(255,107,94,0.08)',
          padding: '5px 8px', marginBottom: 6, fontSize: 10.5, color: 'var(--ui-text-secondary, #c9c8d4)' },
        children: [
          jsx('div', { style: { fontWeight: 700, color: '#ff6b5e', marginBottom: 2 },
            children: `\u23F2 Stale \u00B7 ${staleList.length} \u2014 review Sunday` }),
          staleList.map((p) => row(p)),
        ],
      }),
      SECTIONS.map((sec) => {
        const list = data.projects.filter((p) => p.section === sec)
        if (!list.length) return null
        return jsx('div', { key: sec, style: { marginBottom: 8 }, children: [
          jsx('div', { style: { fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.4,
            color: 'var(--ui-text-quaternary, #77768c)', padding: '2px 4px' }, children: sec }),
          list.map((p) => jsx('div', { key: p.name, children: row(p) })),
        ] })
      }),
      jsx('div', { style: { marginTop: 'auto', paddingTop: 6, fontSize: 10, color: 'var(--ui-text-quaternary, #77768c)' },
        children: `\u21BB evidence built ${briefAt || 'never'} \u00B7 review Sundays with Hermes \u00B7 click a project to open` }),
    ],
  })
}

/* Interview door: open a fresh desktop session pre-loaded with the interview
 * brief. The live evidence brief from GET /brief is used when the backend
 * answers; the static brief below is the fallback (backend asleep / old build).
 * Same gateway RPCs the app's own new-chat flow uses. */
const DEFAULT_BRIEF = [
    "Run Pooh's projects interview now.", '',
    'Load the skill `projects-routine` and follow its "Sunday interview" procedure (evidence pass -> 5 question stages -> apply in one pass).',
    'You are in an interactive desktop session: use clarify() for the interview questions (batch independent ones, max 4-5 per call).',
    'Evidence pass first, before any question: (1) call the projects_review tool; (2) use session_search over the past 7 days to find project work that was never logged - raise it for confirmation instead of assuming; (3) check this week\'s daily 1-hour log in the vault week note if one exists.',
    'Interview Pooh project by project: \u2460 done-this-week confirmations, \u2461 stale decisions (re-commit / park / drop, evidence pack first), \u2462 new ideas/projects (promote with a named phase + label, or park), \u2463 each Business project\'s current focus + next action, \u2464 pick 1-3 projects for next week.',
    'Then apply all confirmed answers in one pass: project_log / project_set / project_item, explicit section moves, update the tracker, write the vault week note (Hermes/Projects/Weekly per the vault-delivery docker path), sync [[Projects]], and report every change back.',
    'Nothing moves without his answer - never drop, park, promote, or complete silently.',
  ].join('\n')

async function startInterview() {
  let text = DEFAULT_BRIEF
  try {
    const b = await api('/brief')
    if (b && b.brief) text = b.brief        // live evidence + current questions
  } catch { /* keep the static brief */ }
  const created = await host.request('session.create', {
    title: `Projects interview \u2014 ${new Date().toISOString().slice(0, 10)}`,
  })
  const sid = created?.session_id || created?.info?.session_id
  if (!sid) return { error: created }
  await host.request('prompt.submit', { session_id: sid, text })
  await host.request('session.activate', { session_id: sid })
  return { ok: true, session_id: sid }
}

/* registration */
export default {
  id: ID,
  name: 'Project Tracker',
  register(ctx) {
    CTX = ctx
    ctx.register({
      id: 'page',
      area: ROUTES_AREA,
      title: 'Projects',
      data: { path: '/projects' },
      render: () => jsx(ProjectsPage, {}),
    })
    ctx.register({
      id: 'nav',
      area: SIDEBAR_NAV_AREA,
      data: { path: '/projects', label: 'Projects', codicon: 'checklist' },
    })
    ctx.register({
      id: 'open',
      area: PALETTE_AREA,
      data: {
        id: 'project-tracker.open', label: 'Open Projects',
        keywords: ['projects', 'routine', 'review', 'stale'],
        run: () => host.navigate('/projects'),
      },
    })
    ctx.register({
      id: 'interview',
      area: PALETTE_AREA,
      data: {
        id: 'project-tracker.interview', label: 'Start projects interview',
        keywords: ['interview', 'sunday', 'review', 'projects', 'stale'],
        run: () => startInterview(),
      },
    })
    // Right-rail pane: placement 'right' stacks it as a tab in the default
    // right sidebar (beside Quota/Review); natively draggable anywhere after.
    ctx.register({
      id: 'rail',
      area: PANES_AREA,
      title: 'Projects',
      order: 2,
      data: {
        placement: 'right',
        width: '300px',
      },
      render: () => jsx(ProjectsRail, {}),
    })
  },
}