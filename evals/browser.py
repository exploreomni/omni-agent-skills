#!/usr/bin/env python3
"""Generate a self-contained HTML eval browser from eval-history.jsonl and workspace dirs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVALS_DIR = ROOT / "evals"
DEFAULT_HISTORY = EVALS_DIR / "eval-history.jsonl"
DEFAULT_JOBS_DIR = EVALS_DIR / "workspaces" / "benchflow"
DEFAULT_OUTPUT = EVALS_DIR / "report.html"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def find_case_dir(job_dir: Path, mode: str, case_id: str) -> Path | None:
    mode_dir = "with-skill" if mode == "with_skill" else mode
    results_dir = job_dir / "jobs" / mode_dir
    if not results_dir.exists():
        return None
    for result_path in results_dir.rglob("result.json"):
        result = load_json(result_path) or {}
        task_name = str(result.get("task_name") or result_path.parent.name.split("__")[0])
        if task_name == str(case_id):
            return result_path.parent
    return None


def load_case_detail(job_dir: Path, mode: str, case_id: str) -> dict[str, Any]:
    case_dir = find_case_dir(job_dir, mode, case_id)
    if not case_dir:
        return {}
    detail: dict[str, Any] = {}
    judge = load_json(case_dir / "verifier" / "judge_result.json")
    if judge:
        detail["judge"] = judge
    prompts = load_json(case_dir / "prompts.json")
    if prompts:
        detail["prompt"] = prompts[0] if isinstance(prompts, list) else prompts
    return detail


def build_data(history_path: Path, jobs_dir: Path) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in history_path.read_text().splitlines()
        if line.strip()
    ]

    # Group: run_id → skill_name → case_id → mode → row
    run_meta: dict[str, dict] = {}
    skill_meta: dict[str, dict[str, dict]] = defaultdict(dict)  # run_id → skill → meta
    case_data: dict[str, dict[str, dict[str, dict]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )  # run_id → skill → case_id → mode → row
    job_dirs: dict[str, dict[str, str]] = defaultdict(dict)  # run_id → skill → job_dir

    for row in rows:
        run_id = row.get("run_id", "")
        skill = row.get("skill_name", "")
        case_id = str(row.get("case_id", ""))
        mode = row.get("mode", "")

        if run_id not in run_meta:
            run_meta[run_id] = {
                "run_id": run_id,
                "run_started_at": row.get("run_started_at"),
                "branch": row.get("branch"),
                "git_sha": row.get("git_sha"),
                "agent": row.get("agent"),
                "model": row.get("model"),
                "sandbox": row.get("sandbox"),
            }

        if skill not in skill_meta[run_id]:
            skill_meta[run_id][skill] = {
                "version": row.get("version"),
                "environment": row.get("environment"),
            }

        case_data[run_id][skill][case_id][mode] = {
            "passed": row.get("passed"),
            "score": row.get("score"),
            "errored": row.get("errored"),
            "timeout": row.get("timeout"),
            "tool_calls": row.get("tool_calls"),
            "duration_sec": row.get("duration_sec"),
            "total_tokens": row.get("total_tokens"),
            "input_tokens": row.get("input_tokens"),
            "output_tokens": row.get("output_tokens"),
            "cache_read_tokens": row.get("cache_read_tokens"),
            "cache_creation_tokens": row.get("cache_creation_tokens"),
        }

        if row.get("job_dir"):
            job_dirs[run_id][skill] = row["job_dir"]

    # Sort runs newest-first
    sorted_runs = sorted(
        run_meta.values(),
        key=lambda r: r.get("run_started_at") or "",
        reverse=True,
    )

    # Collect case names from rows
    case_names: dict[str, dict[str, str]] = defaultdict(dict)  # skill → case_id → name
    for row in rows:
        skill = row.get("skill_name", "")
        case_id = str(row.get("case_id", ""))
        name = row.get("case_name", "")
        if name and case_id not in case_names[skill]:
            case_names[skill][case_id] = name

    # Build final structure + load workspace details
    runs_out = []
    print(f"Loading workspace details for {len(sorted_runs)} run(s)...")
    for run in sorted_runs:
        run_id = run["run_id"]
        skills_out = []
        for skill, cases in sorted(case_data[run_id].items()):
            job_dir_str = job_dirs[run_id].get(skill, "")
            job_dir = None
            if job_dir_str:
                p = Path(job_dir_str)
                job_dir = p if p.is_absolute() else ROOT / p
            cases_out = []
            for case_id, modes in sorted(cases.items(), key=lambda x: (x[0].isdigit() is False, int(x[0]) if x[0].isdigit() else x[0])):
                details: dict[str, Any] = {}
                if job_dir and job_dir.exists():
                    for mode in ("with_skill", "baseline"):
                        d = load_case_detail(job_dir, mode, case_id)
                        if d:
                            details[mode] = d
                cases_out.append({
                    "case_id": case_id,
                    "case_name": case_names[skill].get(case_id, case_id),
                    "modes": modes,
                    "details": details,
                })
            skills_out.append({
                **skill_meta[run_id].get(skill, {}),
                "skill_name": skill,
                "job_dir": job_dir_str,
                "cases": cases_out,
            })
        runs_out.append({**run, "skills": skills_out})

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "runs": runs_out,
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Eval Browser</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --surface2: #22263a;
    --border: #2e3249; --text: #e2e5f0; --muted: #7a82a0;
    --green: #22c55e; --red: #ef4444; --yellow: #eab308;
    --blue: #3b82f6; --purple: #a855f7; --accent: #6366f1;
    --green-dim: #14532d; --red-dim: #450a0a; --yellow-dim: #422006;
    --gray-dim: #1e2130;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: var(--bg); color: var(--text); font-size: 13px; line-height: 1.5; }
  a { color: var(--accent); text-decoration: none; }

  /* Layout */
  #app { display: flex; flex-direction: column; height: 100vh; }
  header { display: flex; align-items: center; gap: 24px; padding: 0 20px;
           border-bottom: 1px solid var(--border); background: var(--surface); height: 48px; flex-shrink: 0; }
  header h1 { font-size: 15px; font-weight: 600; color: var(--text); white-space: nowrap; }
  header .meta { font-size: 11px; color: var(--muted); }
  nav { display: flex; gap: 2px; margin-left: auto; }
  nav button { background: none; border: none; color: var(--muted); cursor: pointer;
               padding: 6px 14px; border-radius: 6px; font-size: 13px; transition: all .15s; }
  nav button:hover { background: var(--surface2); color: var(--text); }
  nav button.active { background: var(--accent); color: white; }

  main { flex: 1; overflow: hidden; display: flex; }
  .panel { flex: 1; overflow-y: auto; padding: 20px; display: none; }
  .panel.active { display: block; }

  /* Detail drawer */
  #detail-drawer { width: 480px; background: var(--surface); border-left: 1px solid var(--border);
                   overflow-y: auto; display: none; flex-shrink: 0; }
  #detail-drawer.open { display: block; }
  #detail-drawer header { position: sticky; top: 0; background: var(--surface);
                           padding: 12px 16px; border-bottom: 1px solid var(--border);
                           display: flex; align-items: center; justify-content: space-between; }
  #detail-drawer header h2 { font-size: 13px; font-weight: 600; }
  #close-drawer { background: none; border: none; color: var(--muted); cursor: pointer;
                  font-size: 18px; line-height: 1; padding: 2px 6px; border-radius: 4px; }
  #close-drawer:hover { background: var(--surface2); color: var(--text); }
  .drawer-body { padding: 16px; }

  /* Tables */
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border);
       color: var(--muted); font-weight: 500; font-size: 11px; text-transform: uppercase;
       letter-spacing: .05em; white-space: nowrap; }
  td { padding: 7px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:hover td { background: var(--surface2); }
  tr.expanded td { background: var(--surface2); }

  /* Badges / pills */
  .badge { display: inline-block; padding: 2px 7px; border-radius: 10px; font-size: 11px; font-weight: 500; }
  .badge-pass { background: var(--green-dim); color: var(--green); }
  .badge-fail { background: var(--red-dim); color: var(--red); }
  .badge-partial { background: var(--yellow-dim); color: var(--yellow); }
  .badge-err { background: var(--gray-dim); color: var(--muted); }
  .badge-mode-ws { background: #1e3a5f; color: #60a5fa; }
  .badge-mode-bl { background: #2d1b4e; color: #c084fc; }
  .badge-mode-lift { background: #1a2e1a; color: #86efac; }

  /* Score bar */
  .score-bar { display: flex; align-items: center; gap: 8px; }
  .score-bar-track { flex: 1; height: 6px; background: var(--surface2); border-radius: 3px; max-width: 80px; }
  .score-bar-fill { height: 100%; border-radius: 3px; }

  /* Expandable rows */
  .expand-btn { background: none; border: none; color: var(--muted); cursor: pointer;
                padding: 0 4px; font-size: 11px; transition: transform .15s; }
  .expand-btn.open { transform: rotate(90deg); }
  .sub-table { background: var(--bg); }
  .sub-table td { font-size: 12px; padding: 5px 12px 5px 32px; }
  .sub-table tr:last-child td { border-bottom: none; }
  .case-link { cursor: pointer; color: var(--text); }
  .case-link:hover { color: var(--accent); }

  /* Filters */
  .filters { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
  .filters input, .filters select {
    background: var(--surface); border: 1px solid var(--border); color: var(--text);
    padding: 5px 10px; border-radius: 6px; font-size: 12px; outline: none; }
  .filters input:focus, .filters select:focus { border-color: var(--accent); }

  /* Heatmap */
  .heatmap-wrap { overflow-x: auto; }
  .heatmap-table th, .heatmap-table td { padding: 3px 6px; font-size: 11px; white-space: nowrap; }
  .heatmap-table td { text-align: center; }
  .hm-cell { width: 28px; height: 22px; border-radius: 3px; cursor: pointer;
             display: inline-flex; align-items: center; justify-content: center;
             font-size: 10px; font-weight: 600; transition: transform .1s; }
  .hm-cell:hover { transform: scale(1.2); z-index: 1; position: relative; }
  .hm-pass { background: var(--green); color: #000; }
  .hm-fail { background: var(--red); color: #fff; }
  .hm-partial { background: var(--yellow); color: #000; }
  .hm-err { background: var(--surface2); color: var(--muted); }
  .hm-none { background: var(--surface2); color: transparent; }
  .hm-label { color: var(--muted); text-align: left !important; max-width: 200px;
              overflow: hidden; text-overflow: ellipsis; }
  .hm-run-label { writing-mode: vertical-lr; transform: rotate(180deg); max-height: 80px;
                  overflow: hidden; text-overflow: ellipsis; font-size: 10px; color: var(--muted); }

  /* Trends */
  .trends-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
  .trend-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .trend-card h3 { font-size: 13px; font-weight: 600; margin-bottom: 12px; }
  .trend-svg { width: 100%; }

  /* Detail */
  .detail-section { margin-bottom: 20px; }
  .detail-section h3 { font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
                       color: var(--muted); margin-bottom: 8px; font-weight: 600; }
  .detail-tabs { display: flex; gap: 4px; margin-bottom: 12px; }
  .detail-tab { background: var(--surface2); border: none; color: var(--muted); cursor: pointer;
                padding: 4px 12px; border-radius: 5px; font-size: 12px; }
  .detail-tab.active { background: var(--accent); color: white; }
  .rubric-item { display: flex; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--border); font-size: 12px; }
  .rubric-item:last-child { border-bottom: none; }
  .rubric-icon { flex-shrink: 0; font-size: 13px; }
  .reasoning-box, .prompt-box { background: var(--bg); border-radius: 6px; padding: 12px;
                                 font-size: 12px; line-height: 1.6; white-space: pre-wrap;
                                 word-break: break-word; color: var(--text); max-height: 300px;
                                 overflow-y: auto; }
  .kv-grid { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; font-size: 12px; }
  .kv-key { color: var(--muted); white-space: nowrap; }
  .kv-val { color: var(--text); }
  .mono { font-family: 'SF Mono', 'Fira Code', monospace; }

  /* Misc */
  .empty { color: var(--muted); padding: 40px; text-align: center; }
  .run-header td { font-weight: 600; cursor: pointer; }
  .chip { display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 10px;
          background: var(--surface2); color: var(--muted); font-family: monospace; }
</style>
</head>
<body>
<div id="app">
  <header>
    <h1>⚗ Eval Browser</h1>
    <span class="meta" id="gen-meta"></span>
    <nav>
      <button class="active" onclick="switchTab('overview')">Overview</button>
      <button onclick="switchTab('heatmap')">Heatmap</button>
      <button onclick="switchTab('trends')">Trends</button>
    </nav>
  </header>
  <main>
    <div id="panel-overview" class="panel active"></div>
    <div id="panel-heatmap" class="panel"></div>
    <div id="panel-trends" class="panel"></div>
    <div id="detail-drawer">
      <header>
        <h2 id="drawer-title">Case Detail</h2>
        <button id="close-drawer" onclick="closeDrawer()">✕</button>
      </header>
      <div class="drawer-body" id="drawer-body"></div>
    </div>
  </main>
</div>

<script>
const DATA = __DATA__;

// ── helpers ──────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function scoreBadge(mode_data) {
  if (!mode_data) return '<span class="badge badge-err">—</span>';
  if (mode_data.errored) return '<span class="badge badge-err">err</span>';
  const s = mode_data.score;
  if (s === null || s === undefined) return '<span class="badge badge-err">—</span>';
  const pct = Math.round(s * 100);
  if (s >= 1.0) return `<span class="badge badge-pass">${pct}%</span>`;
  if (s > 0)    return `<span class="badge badge-partial">${pct}%</span>`;
  return `<span class="badge badge-fail">${pct}%</span>`;
}

function liftBadge(lift_data) {
  if (!lift_data || lift_data.score === null || lift_data.score === undefined)
    return '<span class="badge badge-err">—</span>';
  const pts = Math.round(lift_data.score * 100);
  if (pts > 0)  return `<span class="badge badge-pass">+${pts}</span>`;
  if (pts < 0)  return `<span class="badge badge-fail">${pts}</span>`;
  return `<span class="badge badge-err">0</span>`;
}

function scoreBar(score) {
  if (score === null || score === undefined) return '';
  const pct = Math.round(score * 100);
  const color = score >= 1 ? 'var(--green)' : score > 0 ? 'var(--yellow)' : 'var(--red)';
  return `<div class="score-bar"><div class="score-bar-track"><div class="score-bar-fill" style="width:${pct}%;background:${color}"></div></div><span>${pct}%</span></div>`;
}

function fmtNum(n, digits=0) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString(undefined, {maximumFractionDigits: digits});
}

function fmtDur(s) {
  if (s === null || s === undefined) return '—';
  if (s < 60) return `${Math.round(s)}s`;
  return `${Math.floor(s/60)}m${Math.round(s%60)}s`;
}

function skillAvgScore(skill, mode) {
  let sum = 0, n = 0;
  for (const c of skill.cases) {
    const m = c.modes[mode];
    if (m && m.score !== null && m.score !== undefined) { sum += m.score; n++; }
  }
  return n > 0 ? sum / n : null;
}

// ── tab switching ─────────────────────────────────────────────────────────────

function switchTab(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  event.currentTarget.classList.add('active');
  if (name === 'heatmap') renderHeatmap();
  if (name === 'trends') renderTrends();
}

// ── detail drawer ─────────────────────────────────────────────────────────────

function openDrawer(runId, skillName, caseId) {
  const run = DATA.runs.find(r => r.run_id === runId);
  if (!run) return;
  const skill = run.skills.find(s => s.skill_name === skillName);
  if (!skill) return;
  const cas = skill.cases.find(c => c.case_id === caseId);
  if (!cas) return;

  document.getElementById('drawer-title').textContent = `${skillName} · case ${caseId}`;
  document.getElementById('drawer-body').innerHTML = renderCaseDetail(cas);
  document.getElementById('detail-drawer').classList.add('open');

  // activate first detail tab
  const firstTab = document.querySelector('.detail-tab');
  if (firstTab) activateDetailTab(firstTab, 'with_skill');
}

function closeDrawer() {
  document.getElementById('detail-drawer').classList.remove('open');
}

function activateDetailTab(btn, mode) {
  document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.detail-mode-panel').forEach(p => p.style.display = 'none');
  const panel = document.getElementById('detail-mode-' + mode);
  if (panel) panel.style.display = 'block';
}

function renderCaseDetail(cas) {
  let html = `<div class="detail-section">
    <div class="kv-grid">
      <span class="kv-key">Case</span><span class="kv-val">${esc(cas.case_id)}</span>
      <span class="kv-key">Question</span><span class="kv-val">${esc(cas.case_name)}</span>
    </div>
  </div>`;

  const modes = [['with_skill','With Skill'],['baseline','Baseline']];
  const hasModes = modes.filter(([m]) => cas.modes[m]);

  // Summary row
  html += `<div class="detail-section"><h3>Scores</h3><div class="kv-grid">`;
  for (const [m, label] of hasModes) {
    const md = cas.modes[m];
    const score = md?.score !== null && md?.score !== undefined ? Math.round(md.score * 100) + '%' : '—';
    html += `<span class="kv-key">${label}</span><span class="kv-val">${scoreBar(md?.score)} ${fmtNum(md?.tool_calls)} tools · ${fmtDur(md?.duration_sec)} · ${fmtNum(md?.total_tokens)} tokens</span>`;
  }
  if (cas.modes['lift']) {
    const lift = cas.modes['lift'];
    const pts = lift.score !== null ? Math.round(lift.score * 100) : null;
    html += `<span class="kv-key">Lift</span><span class="kv-val">${pts !== null ? (pts > 0 ? '+' : '') + pts + ' pts' : '—'}</span>`;
  }
  html += `</div></div>`;

  // Mode tabs
  if (hasModes.length) {
    html += `<div class="detail-tabs">`;
    for (const [m, label] of hasModes) {
      html += `<button class="detail-tab" onclick="activateDetailTab(this, '${m}')">${label}</button>`;
    }
    html += `</div>`;

    for (const [m, label] of hasModes) {
      html += `<div class="detail-mode-panel" id="detail-mode-${m}" style="display:none">`;
      const det = (cas.details || {})[m] || {};

      if (det.judge) {
        html += `<div class="detail-section"><h3>Judge Reasoning</h3>
          <div class="reasoning-box">${esc(det.judge.reasoning || '')}</div></div>`;
        if (det.judge.items?.length) {
          html += `<div class="detail-section"><h3>Rubric</h3>`;
          for (const item of det.judge.items) {
            html += `<div class="rubric-item">
              <span class="rubric-icon">${item.pass ? '✅' : '❌'}</span>
              <span>${esc(item.criterion)}</span>
            </div>`;
          }
          html += `</div>`;
        }
      }

      if (det.prompt) {
        html += `<div class="detail-section"><h3>Agent Prompt</h3>
          <div class="prompt-box mono">${esc(typeof det.prompt === 'string' ? det.prompt : JSON.stringify(det.prompt, null, 2))}</div>
        </div>`;
      }

      if (!det.judge && !det.prompt) {
        html += `<p style="color:var(--muted);font-size:12px;padding:8px 0">No workspace detail available for this run.</p>`;
      }

      html += `</div>`;
    }
  }

  return html;
}

// ── overview panel ────────────────────────────────────────────────────────────

let overviewFilter = { text: '', skill: '', branch: '' };

function renderOverview() {
  const skills = [...new Set(DATA.runs.flatMap(r => r.skills.map(s => s.skill_name)))].sort();
  const branches = [...new Set(DATA.runs.map(r => r.branch).filter(Boolean))].sort();

  let skillOpts = `<option value="">All skills</option>` + skills.map(s => `<option>${esc(s)}</option>`).join('');
  let branchOpts = `<option value="">All branches</option>` + branches.map(b => `<option>${esc(b)}</option>`).join('');

  let html = `<div class="filters">
    <input type="text" placeholder="Search…" oninput="overviewFilter.text=this.value;renderOverviewTable()" style="width:180px">
    <select onchange="overviewFilter.skill=this.value;renderOverviewTable()">${skillOpts}</select>
    <select onchange="overviewFilter.branch=this.value;renderOverviewTable()">${branchOpts}</select>
  </div>
  <div id="overview-table-wrap"></div>`;

  document.getElementById('panel-overview').innerHTML = html;
  renderOverviewTable();
}

function renderOverviewTable() {
  const { text, skill, branch } = overviewFilter;
  const q = text.toLowerCase();

  let html = `<table>
    <thead><tr>
      <th></th><th>Run</th><th>Date</th><th>Branch</th><th>Commit</th>
      <th>Skill</th><th>Version</th><th>With Skill</th><th>Baseline</th><th>Lift</th>
    </tr></thead><tbody id="overview-body">`;

  for (const run of DATA.runs) {
    for (const sk of run.skills) {
      if (skill && sk.skill_name !== skill) continue;
      if (branch && run.branch !== branch) continue;
      if (q && !run.run_id.toLowerCase().includes(q) &&
               !sk.skill_name.toLowerCase().includes(q) &&
               !(run.branch||'').toLowerCase().includes(q)) continue;

      const wsScore = skillAvgScore(sk, 'with_skill');
      const blScore = skillAvgScore(sk, 'baseline');
      const lift = wsScore !== null && blScore !== null ? wsScore - blScore : null;
      const rowId = `${run.run_id}__${sk.skill_name}`;

      html += `<tr class="run-header" onclick="toggleSkillRows('${rowId}')">
        <td><button class="expand-btn" id="btn-${rowId}">▶</button></td>
        <td><span class="chip mono">${esc(run.run_id.slice(0,16))}</span></td>
        <td style="color:var(--muted)">${esc(run.run_started_at||'')}</td>
        <td>${run.branch ? `<span class="chip">${esc(run.branch)}</span>` : '<span style="color:var(--muted)">—</span>'}</td>
        <td><span class="chip mono">${run.git_sha ? esc(run.git_sha.slice(0,7)) : '—'}</span></td>
        <td><strong>${esc(sk.skill_name)}</strong></td>
        <td style="color:var(--muted)">${esc(sk.version||'—')}</td>
        <td>${scoreBar(wsScore)}</td>
        <td>${scoreBar(blScore)}</td>
        <td>${liftBadge({score: lift})}</td>
      </tr>`;

      html += `<tr id="rows-${rowId}" style="display:none"><td colspan="10" style="padding:0">
        <table class="sub-table"><tbody>`;
      for (const cas of sk.cases) {
        const ws = cas.modes['with_skill'];
        const bl = cas.modes['baseline'];
        const lt = cas.modes['lift'];
        html += `<tr>
          <td style="width:32px"></td>
          <td style="width:40px;color:var(--muted)">${esc(cas.case_id)}</td>
          <td class="case-link" onclick="openDrawer('${run.run_id}','${sk.skill_name}','${cas.case_id}')"
              title="Click to view detail">${esc(cas.case_name)}</td>
          <td>${scoreBadge(ws)}</td>
          <td>${scoreBadge(bl)}</td>
          <td>${liftBadge(lt)}</td>
          <td style="color:var(--muted)">${ws ? fmtNum(ws.tool_calls) + ' tools' : ''}</td>
          <td style="color:var(--muted)">${ws ? fmtDur(ws.duration_sec) : ''}</td>
          <td style="color:var(--muted)">${ws ? fmtNum(ws.total_tokens) + ' tok' : ''}</td>
        </tr>`;
      }
      html += `</tbody></table></td></tr>`;
    }
  }

  html += `</tbody></table>`;
  document.getElementById('overview-table-wrap').innerHTML = html;
}

function toggleSkillRows(id) {
  const rows = document.getElementById('rows-' + id);
  const btn = document.getElementById('btn-' + id);
  if (!rows) return;
  const open = rows.style.display !== 'none';
  rows.style.display = open ? 'none' : '';
  btn.classList.toggle('open', !open);
}

// ── heatmap panel ─────────────────────────────────────────────────────────────

function renderHeatmap() {
  // Collect all skill+case pairs and runs (newest→oldest, truncated)
  const skillCases = [];
  const seenSC = new Set();
  const skills = [...new Set(DATA.runs.flatMap(r => r.skills.map(s => s.skill_name)))].sort();
  for (const skillName of skills) {
    for (const run of [...DATA.runs].reverse()) {
      const sk = run.skills.find(s => s.skill_name === skillName);
      if (!sk) continue;
      for (const cas of sk.cases) {
        const key = `${skillName}__${cas.case_id}`;
        if (!seenSC.has(key)) {
          seenSC.add(key);
          skillCases.push({ skill: skillName, case_id: cas.case_id, case_name: cas.case_name });
        }
      }
    }
  }

  const runs = [...DATA.runs].reverse().slice(0, 20); // up to 20 most recent

  let html = `<div class="heatmap-wrap"><table class="heatmap-table"><thead><tr>
    <th class="hm-label">Skill · Case</th>`;
  for (const run of runs) {
    const short = (run.run_started_at || run.run_id).slice(0, 16);
    html += `<th><div class="hm-run-label" title="${esc(run.run_id)}">${esc(short)}</div></th>`;
  }
  html += `</tr></thead><tbody>`;

  let lastSkill = '';
  for (const { skill, case_id, case_name } of skillCases) {
    if (skill !== lastSkill) {
      html += `<tr><td colspan="${runs.length + 1}" style="padding:8px 0 2px;color:var(--accent);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em">${esc(skill)}</td></tr>`;
      lastSkill = skill;
    }
    html += `<tr><td class="hm-label" title="${esc(case_name)}">${esc(case_id)}. ${esc(case_name.slice(0, 40))}</td>`;
    for (const run of runs) {
      const sk = run.skills.find(s => s.skill_name === skill);
      const cas = sk?.cases.find(c => c.case_id === case_id);
      const ws = cas?.modes['with_skill'];
      let cls = 'hm-none', label = '';
      if (ws) {
        if (ws.errored) { cls = 'hm-err'; label = 'E'; }
        else if (ws.score === null || ws.score === undefined) { cls = 'hm-none'; }
        else if (ws.score >= 1.0) { cls = 'hm-pass'; label = '✓'; }
        else if (ws.score > 0)    { cls = 'hm-partial'; label = Math.round(ws.score*100); }
        else                      { cls = 'hm-fail'; label = '✗'; }
      }
      const onclick = ws ? `onclick="openDrawer('${run.run_id}','${skill}','${case_id}')"` : '';
      html += `<td><div class="hm-cell ${cls}" ${onclick} title="${esc(run.run_started_at||run.run_id)}">${label}</div></td>`;
    }
    html += `</tr>`;
  }

  html += `</tbody></table></div>`;
  document.getElementById('panel-heatmap').innerHTML = html;
}

// ── trends panel ──────────────────────────────────────────────────────────────

function renderTrends() {
  const skills = [...new Set(DATA.runs.flatMap(r => r.skills.map(s => s.skill_name)))].sort();
  const runs = [...DATA.runs].reverse(); // oldest first for charts

  let html = `<div class="trends-grid">`;
  for (const skillName of skills) {
    const wsPoints = [], blPoints = [];
    const labels = [];
    for (const run of runs) {
      const sk = run.skills.find(s => s.skill_name === skillName);
      if (!sk) continue;
      labels.push((run.run_started_at || '').slice(5, 16));
      wsPoints.push(skillAvgScore(sk, 'with_skill'));
      blPoints.push(skillAvgScore(sk, 'baseline'));
    }
    html += `<div class="trend-card"><h3>${esc(skillName)}</h3>${renderSparkline(wsPoints, blPoints, labels)}</div>`;
  }
  html += `</div>`;
  document.getElementById('panel-trends').innerHTML = html;
}

function renderSparkline(ws, bl, labels) {
  const W = 300, H = 100, pad = { t: 8, r: 8, b: 24, l: 30 };
  const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
  const n = Math.max(ws.length, 1);
  const xPos = (i) => pad.l + (n === 1 ? iw / 2 : i / (n - 1) * iw);
  const yPos = (v) => v === null ? null : pad.t + ih - v * ih;

  function polyline(pts, color) {
    const segs = [];
    let seg = [];
    for (const p of pts) {
      if (p === null) { if (seg.length > 1) segs.push(seg); seg = []; }
      else seg.push(p);
    }
    if (seg.length > 1) segs.push(seg);
    return segs.map(s =>
      `<polyline points="${s.map(([x,y]) => `${x},${y}`).join(' ')}"
        fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`
    ).join('') +
    pts.map((p, i) => p ? `<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="${color}"/>` : '').join('');
  }

  const wsPts = ws.map((v, i) => v !== null ? [xPos(i), yPos(v)] : null);
  const blPts = bl.map((v, i) => v !== null ? [xPos(i), yPos(v)] : null);

  // y-axis grid
  let grid = '';
  for (const v of [0, 0.5, 1]) {
    const y = yPos(v);
    grid += `<line x1="${pad.l}" y1="${y}" x2="${W - pad.r}" y2="${y}"
      stroke="var(--border)" stroke-width="1"/>
      <text x="${pad.l - 4}" y="${y + 4}" font-size="9" fill="var(--muted)" text-anchor="end">${v * 100}%</text>`;
  }

  // x labels (sparse)
  let xlabels = '';
  const step = Math.max(1, Math.floor(n / 5));
  for (let i = 0; i < n; i += step) {
    xlabels += `<text x="${xPos(i)}" y="${H - 4}" font-size="8" fill="var(--muted)" text-anchor="middle">${esc(labels[i]||'')}</text>`;
  }

  return `<svg class="trend-svg" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
    ${grid}
    ${polyline(wsPts, 'var(--accent)')}
    ${polyline(blPts, 'var(--purple)')}
    ${xlabels}
    <text x="${W - pad.r}" y="12" font-size="9" fill="var(--accent)" text-anchor="end">● with-skill</text>
    <text x="${W - pad.r}" y="23" font-size="9" fill="var(--purple)" text-anchor="end">● baseline</text>
  </svg>`;
}

// ── init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('gen-meta').textContent = `Generated ${DATA.generated_at} · ${DATA.runs.length} run(s)`;
  renderOverview();
});
</script>
</body>
</html>
"""


def generate(history_path: Path, jobs_dir: Path, output: Path) -> None:
    data = build_data(history_path, jobs_dir)
    data_json = json.dumps(data, separators=(",", ":"), default=str)
    html = HTML_TEMPLATE.replace("__DATA__", data_json)
    output.write_text(html)
    print(f"Written: {output}  ({output.stat().st_size // 1024} KB, {len(data['runs'])} runs)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--jobs-dir", type=Path, default=DEFAULT_JOBS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.history.exists():
        raise SystemExit(f"history file not found: {args.history}\nRun ./evals/history.sh first.")

    generate(args.history, args.jobs_dir, args.output)


if __name__ == "__main__":
    main()
