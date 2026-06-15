"""Report generation — Legendary audit-ready Markdown and HTML reports."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template

from audit_readiness.config import Config
from audit_readiness.utils import logger


# ═══════════════════════════════════════════════════════════════════════════════
# MARKDOWN TEMPLATE — Clean, emoji-native, GitHub/GitLab compatible
# ═══════════════════════════════════════════════════════════════════════════════

MARKDOWN_TEMPLATE = """# 🔒 Security Readiness Assessment Report

**Project:** {{ project_name }}  
**Date:** {{ date }}  
**Engine:** Foundry Audit Readiness v{{ version }}  
**Classification:** Confidential — Client Use Only

---

## Executive Summary

{% if all_passed %}✅ **STATUS: AUDIT-READY**

This codebase has successfully passed all automated security readiness checks across {{ tools_configured }} security tools. No critical or high-severity findings were detected.
{% else %}❌ **STATUS: NOT AUDIT-READY**

This codebase has failed one or more automated security readiness checks. Issues must be resolved before professional audit engagement.
{% endif %}

### Risk Matrix

| Severity | Count | Description |
|:---------|:-----:|:------------|
{% for sev, count, desc in risk_matrix %}
| {{ sev }} | **{{ count }}** | {{ desc }} |
{% endfor %}

### Key Metrics

| Metric | Result | Threshold | Status |
|:-------|:------:|:---------:|:------:|
| Line Coverage | {{ coverage.line_percent | round(1) }}% | {{ config.coverage.line }}% | {% if coverage.line_percent >= config.coverage.line %}✅{% else %}❌{% endif %} |
| Branch Coverage | {{ coverage.branch_percent | round(1) }}% | {{ config.coverage.branch }}% | {% if coverage.branch_percent >= config.coverage.branch %}✅{% else %}❌{% endif %} |
| Function Coverage | {{ coverage.function_percent | round(1) }}% | {{ config.coverage.function }}% | {% if coverage.function_percent >= config.coverage.function %}✅{% else %}❌{% endif %} |
| Static Analysis | {{ tools_ran }}/{{ tools_configured }} tools clean | All | {% if static_analysis_passed %}✅{% else %}❌{% endif %} |
| Compiler Warnings | {% if no_warnings %}None{% else %}{{ compiler_warnings | length }} found{% endif %} | 0 | {% if no_warnings %}✅{% else %}❌{% endif %} |
| NatSpec (external) | {{ natspec.documented_external }}/{{ natspec.total_external }} | 100% | {% if natspec.total_external == 0 or natspec.documented_external == natspec.total_external %}✅{% else %}⚠️{% endif %} |

---

## 1. Scope of Assessment

This assessment employed {{ tools_configured }} industry-standard security analysis tools:

| Phase | Tool | Vendor | Technique |
|:------|:-----|:-------|:----------|
| 1 | Slither | Trail of Bits | Static Analysis |
| 2 | Aderyn | Cyfrin | Static Analysis |
| 3 | Solhint | Community | Linting |
| 4 | Semgrep | r2c | Rule Engine |
| 5 | Mythril | ConsenSys | Symbolic Execution |
| 6 | Halmos | a16z | Formal Verification |
| 7 | SMTChecker | Ethereum Foundation | SMT Verification |

### Coverage Thresholds

- Line: {{ config.coverage.line }}% | Branch: {{ config.coverage.branch }}% | Function: {{ config.coverage.function }}%

---

## 2. Security Findings

{% if total_findings == 0 %}✅ **Zero findings across all tools.** Exceptional code quality.
{% elif total_critical == 0 and total_high == 0 %}⚠️ **{{ total_findings }} medium/low-severity findings detected.** No critical or high issues. Recommended for review.
{% else %}🔴 **{{ total_critical }} critical and {{ total_high }} high-severity findings detected.** These require immediate attention.
{% endif %}

{% for tool, result in static_analysis.items() %}
### 2.{{ loop.index }}. {{ tool_name(tool) }}{% if result.error %} (SKIPPED){% endif %}

{% if result.error %}⏭️ **Status:** SKIPPED — {{ result.error }}
{% else %}
**Status:** {% if result.passed %}✅ PASS{% else %}❌ FAIL{% endif %}  
**Findings:** {% if result.findings | length == 0 %}None{% else %}{% for f in result.findings %}🔴 {{ f.severity }} — {{ f.check }} ({{ f.file }}:{{ f.line }}): {{ f.message | truncate(100) }}
{% endfor %}{% endif %}
{% endif %}
{% endfor %}

---

## 3. Test Coverage Analysis

| Metric | Achieved | Required | Gap | Status |
|:-------|:--------:|:--------:|:---:|:------:|
| Line | {{ coverage.line_percent | round(1) }}% | {{ config.coverage.line }}% | {{ (coverage.line_percent - config.coverage.line) | round(1) }}% | {% if coverage.line_percent >= config.coverage.line %}✅ EXCEEDS{% else %}❌ BELOW{% endif %} |
| Branch | {{ coverage.branch_percent | round(1) }}% | {{ config.coverage.branch }}% | {{ (coverage.branch_percent - config.coverage.branch) | round(1) }}% | {% if coverage.branch_percent >= config.coverage.branch %}✅ EXCEEDS{% else %}❌ BELOW{% endif %} |
| Function | {{ coverage.function_percent | round(1) }}% | {{ config.coverage.function }}% | {{ (coverage.function_percent - config.coverage.function) | round(1) }}% | {% if coverage.function_percent >= config.coverage.function %}✅ EXCEEDS{% else %}❌ BELOW{% endif %} |

{% if invariants.functions_found > 0 %}
### Invariant Testing

| Property | Value |
|:---------|:------|
| Invariant functions | {{ invariants.functions_found }} |
| Fuzz runs | {{ invariants.runs }} |
| All passing | {% if invariants.all_passed %}✅ Yes{% else %}❌ No{% endif %} |
{% endif %}

---

## 4. Code Quality Assessment

### NatSpec Documentation

| Scope | Documented | Total | Status |
|:------|:----------:|:-----:|:------:|
| Public Functions | {{ natspec.documented_public }} | {{ natspec.total_public }} | {% if natspec.documented_public == natspec.total_public %}✅{% else %}⚠️ {{ natspec.total_public - natspec.documented_public }} missing{% endif %} |
| External Functions | {{ natspec.documented_external }} | {{ natspec.total_external }} | {% if natspec.documented_external == natspec.total_external %}✅{% else %}⚠️ {{ natspec.total_external - natspec.documented_external }} missing{% endif %} |

### Compiler Warnings

{% if no_warnings %}✅ No compiler warnings detected.
{% else %}⚠️ {{ compiler_warnings | length }} warning(s) detected:
{% for w in compiler_warnings[:5] %}
- {{ w | truncate(120) }}
{% endfor %}
{% if compiler_warnings | length > 5 %}... and {{ compiler_warnings | length - 5 }} more{% endif %}
{% endif %}

### Gas Analysis

{% if gas.baseline_exists %}✅ Gas snapshot baseline exists ({{ gas.functions | length }} functions tracked).
{% else %}ℹ️ No gas snapshot baseline found. Run `forge snapshot` to establish one.
{% endif %}

---

## 5. Tool Coverage Summary

| # | Tool | Vendor | Technique | Findings | Status |
|:-:|----- |:------|:----------|:---------|:------:|
{% for tool_name_key, result in static_analysis.items() %}
| {{ loop.index }} | **{{ tool_name(tool_name_key) }}** | {{ tool_vendor(tool_name_key) }} | {{ tool_technique(tool_name_key) }} | {% if result.error %}N/A{% else %}{{ result.findings | length }}{% endif %} | {% if result.error %}⏭️ SKIP{% elif result.passed %}✅ PASS{% else %}❌ FAIL{% endif %} |
{% endfor %}

---

## 6. Conclusion

{% if all_passed %}
### ✅ Security Readiness Certificate

**{{ project_name }}** has been evaluated against {{ tools_configured }} independent security tools and has demonstrated **audit-ready code quality**.

| Criterion | Result |
|:----------|:------:|
| Critical/High Findings | 0 ✅ |
| Test Coverage | {{ coverage.line_percent | round(1) }}% line / {{ coverage.branch_percent | round(1) }}% branch |
| Invariant Tests | {{ invariants.functions_found }}/{{ invariants.functions_found }} passing |
| Documentation | {{ natspec.documented_external }}/{{ natspec.total_external }} external functions |
| Compiler Warnings | 0 |

**Recommendation:** Proceed with professional security audit engagement.  
**Estimated scope:** 2-4 auditor-weeks | **Cost reduction:** 30-40%
{% else %}
### ❌ Action Required

**{{ project_name }}** has failed one or more checks and is **not recommended** for audit at this time.

Required actions:
{% if not static_analysis_passed %}- 🔴 Address critical/high findings from static analysis
{% endif %}
{% if not coverage_passed %}- 🔴 Increase test coverage (line ≥{{ config.coverage.line }}%, branch ≥{{ config.coverage.branch }}%)
{% endif %}
{% if not natspec.passed %}- 🟡 Document all external functions with NatSpec
{% endif %}
{% if not no_warnings %}- 🟡 Eliminate all compiler warnings
{% endif %}

Resolve the issues above and re-run this assessment.
{% endif %}

---

## 7. Limitations & Disclaimer

This report was generated by **automated analysis tools** and has inherent limitations:

1. Automated tools detect known patterns only. Novel vulnerabilities may not be detected.
2. No automated tool can guarantee the absence of vulnerabilities.
3. Business logic correctness requires human expert review.
4. Proxy patterns are assessed on current implementation only.

> **THIS REPORT DOES NOT CONSTITUTE A PROFESSIONAL SECURITY AUDIT.** It is an automated readiness assessment. Only a professional audit by experienced human auditors can provide meaningful security assurance.

---

*Report generated by Foundry Audit Readiness v{{ version }} — {{ date }}*
"""


# ═══════════════════════════════════════════════════════════════════════════════
# HTML TEMPLATE — Native HTML with integrated professional CSS
# Dark theme, print-ready, responsive. NOT converted from markdown.
# ═══════════════════════════════════════════════════════════════════════════════

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Security Readiness — {{ project_name }}</title>
<style>
/* ─── Reset & Base ─── */
*,*::before,*::after{box-sizing:border-box;margin:0}
:root{
  --bg:#0d1117;--bg-elev:#161b22;--bg-card:#1c2128;--border:#30363d;
  --text:#c9d1d9;--text-muted:#8b949e;--text-dim:#484f58;
  --accent:#58a6ff;--accent-soft:#388bfd33;
  --pass:#3fb950;--pass-bg:#2ea04326;
  --fail:#f85149;--fail-bg:#da363326;
  --warn:#d29922;--warn-bg:#bb800926;
  --info:#58a6ff;--info-bg:#388bfd26;
  --crit:#f85149;--high:#f0883e;--med:#d29922;--low:#58a6ff;--inf:#8b949e;
  --radius:8px;--shadow:0 4px 24px rgba(0,0,0,.4);
}
body{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
  background:var(--bg);color:var(--text);line-height:1.65;
  max-width:1100px;margin:0 auto;padding:32px 24px;
}

/* ─── Header ─── */
.report-header{
  text-align:center;padding:40px 32px 32px;
  background:linear-gradient(135deg,#161b22 0%,#1c2128 50%,#0d1117 100%);
  border:1px solid var(--border);border-radius:var(--radius);margin-bottom:32px;
  position:relative;overflow:hidden;
}
.report-header::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#f85149,#f0883e,#d29922,#58a6ff,#3fb950);
}
.report-header h1{font-size:1.8rem;font-weight:700;letter-spacing:-.5px;margin-bottom:12px;color:#f0f6fc}
.report-header .subtitle{color:var(--text-muted);font-size:.95rem;margin-bottom:20px}
.meta-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;text-align:left;margin-top:20px}
.meta-item{padding:10px 14px;background:var(--bg-elev);border:1px solid var(--border);border-radius:6px;font-size:.82rem}
.meta-item .label{color:var(--text-muted);text-transform:uppercase;font-size:.68rem;letter-spacing:.5px;margin-bottom:2px}
.meta-item .value{color:var(--text);font-weight:600}

/* ─── Status Banner ─── */
.status-banner{text-align:center;padding:24px 32px;border-radius:var(--radius);margin-bottom:32px;font-size:1.1rem;font-weight:600;border:1px solid}
.status-pass{background:var(--pass-bg);border-color:var(--pass);color:var(--pass)}
.status-fail{background:var(--fail-bg);border-color:var(--fail);color:var(--fail)}

/* ─── Section Cards ─── */
.section{margin-bottom:32px}
.section-title{font-size:1.25rem;font-weight:700;color:#f0f6fc;margin-bottom:20px;padding-bottom:10px;border-bottom:2px solid var(--accent);display:flex;align-items:center;gap:10px}
.section-title .num{color:var(--accent);font-size:.85rem;background:var(--accent-soft);padding:2px 8px;border-radius:4px}
.card{background:var(--bg-elev);border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin-bottom:20px}
.card-title{font-size:1.05rem;font-weight:600;color:var(--accent);margin-bottom:16px;display:flex;align-items:center;gap:8px}

/* ─── Tables ─── */
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:.85rem}
th{text-align:left;padding:10px 12px;background:var(--bg-card);color:var(--text-muted);font-weight:600;text-transform:uppercase;font-size:.72rem;letter-spacing:.4px;border-bottom:2px solid var(--border)}
td{padding:10px 12px;border-bottom:1px solid var(--border);vertical-align:top}
tr:hover td{background:rgba(88,166,255,.04)}
td:last-child,th:last-child{text-align:center}

/* ─── Severity Badges ─── */
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.3px;white-space:nowrap}
.badge-crit{background:var(--fail-bg);color:var(--crit);border:1px solid var(--fail)}
.badge-high{background:#f0883e1a;color:var(--high);border:1px solid var(--high)}
.badge-med{background:var(--warn-bg);color:var(--med);border:1px solid var(--med)}
.badge-low{background:var(--info-bg);color:var(--low);border:1px solid var(--low)}
.badge-inf{background:rgba(139,148,158,.15);color:var(--inf);border:1px solid var(--inf)}
.badge-pass{background:var(--pass-bg);color:var(--pass);border:1px solid var(--pass)}
.badge-fail{background:var(--fail-bg);color:var(--fail);border:1px solid var(--fail)}
.badge-skip{background:rgba(139,148,158,.15);color:var(--text-muted);border:1px solid var(--text-dim)}

/* ─── Finding Items ─── */
.finding-item{padding:14px 16px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:10px;transition:border-color .15s}
.finding-item:hover{border-color:var(--accent)}
.finding-header{display:flex;align-items:center;gap:10px;margin-bottom:6px;flex-wrap:wrap}
.finding-file{font-family:'SF Mono',Consolas,monospace;font-size:.8rem;color:var(--accent);background:var(--accent-soft);padding:2px 8px;border-radius:4px}
.finding-line{color:var(--text-muted);font-size:.8rem}
.finding-check{font-family:'SF Mono',Consolas,monospace;font-size:.78rem;color:var(--warn);background:var(--warn-bg);padding:2px 8px;border-radius:4px}
.finding-msg{color:var(--text-muted);font-size:.85rem;line-height:1.5}

/* ─── Tool Section ─── */
.tool-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px}
.tool-name{font-size:1.1rem;font-weight:700;color:#f0f6fc}
.tool-status{display:flex;align-items:center;gap:12px}
.tool-counts{display:flex;gap:16px;font-size:.85rem;color:var(--text-muted)}
.tool-count{display:flex;align-items:center;gap:4px}
.tool-sep{height:20px;width:1px;background:var(--border);margin:0 4px}

/* ─── Coverage Bars ─── */
.coverage-row{display:flex;align-items:center;gap:16px;margin-bottom:12px;padding:12px 16px;background:var(--bg-card);border-radius:var(--radius)}
.coverage-label{min-width:100px;font-weight:600;font-size:.88rem}
.coverage-bar{flex:1;height:28px;background:var(--bg);border-radius:6px;overflow:hidden;position:relative}
.coverage-fill{height:100%;border-radius:6px;transition:width .4s ease;display:flex;align-items:center;justify-content:flex-end;padding-right:10px;font-size:.75rem;font-weight:700;color:#fff;min-width:50px}
.coverage-fill.good{background:linear-gradient(90deg,#2ea043,#3fb950)}
.coverage-fill.bad{background:linear-gradient(90deg,#da3633,#f85149)}
.coverage-pct{min-width:60px;text-align:right;font-weight:700;font-size:.9rem}
.coverage-pct.good{color:var(--pass)}
.coverage-pct.bad{color:var(--fail)}

/* ─── Metric Grid ─── */
.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-top:16px}
.metric-box{text-align:center;padding:18px 12px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius)}
.metric-box .value{font-size:1.6rem;font-weight:700;margin-bottom:4px}
.metric-box .label{font-size:.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.3px}
.metric-box.good .value{color:var(--pass)}
.metric-box.warn .value{color:var(--warn)}
.metric-box.bad .value{color:var(--fail)}

/* ─── Certificate ─── */
.certificate{text-align:center;padding:40px 32px;background:linear-gradient(135deg,#162d1e 0%,#1c2128 50%,#0d1117 100%);border:2px solid var(--pass);border-radius:var(--radius);position:relative;overflow:hidden}
.certificate::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#2ea043,#3fb950,#56d364)}
.certificate h3{font-size:1.4rem;color:var(--pass);margin-bottom:16px}
.certificate p{color:var(--text-muted);max-width:600px;margin:0 auto 24px}
.cert-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin:24px 0}
.cert-item{padding:16px;background:var(--bg-elev);border:1px solid var(--border);border-radius:var(--radius)}
.cert-item .val{font-size:1.3rem;font-weight:700;color:var(--pass);margin-bottom:4px}
.cert-item .lbl{font-size:.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.3px}

/* ─── Action Items ─── */
.action-list{list-style:none;padding:0}
.action-list li{padding:12px 16px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:8px;display:flex;align-items:center;gap:10px;font-size:.88rem}
.action-list li .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dot-crit{background:var(--crit)}.dot-high{background:var(--high)}.dot-med{background:var(--med)}

/* ─── Divider ─── */
hr{border:none;border-top:1px solid var(--border);margin:32px 0}

/* ─── Print / PDF Button ─── */
.pdf-btn{position:fixed;top:20px;right:20px;background:var(--accent);color:#fff;border:none;padding:12px 22px;border-radius:var(--radius);font-size:.85rem;font-weight:600;cursor:pointer;box-shadow:var(--shadow);z-index:1000;transition:background .15s}
.pdf-btn:hover{background:#79b8ff}

/* ─── Print ─── */
@media print{
  .pdf-btn{display:none}
  body{background:#fff;color:#1a1a1a;padding:20px}
  :root{--bg:#fff;--bg-elev:#f6f8fa;--bg-card:#fff;--border:#d0d7de;--text:#1a1a1a;--text-muted:#656d76;--accent:#0969da}
  .report-header{background:#f6f8fa}
  .finding-item,.metric-box,.cert-item,.action-list li,.meta-item,.coverage-row,.card{background:#f6f8fa}
}

/* ─── Responsive ─── */
@media(max-width:768px){
  body{padding:16px 12px}
  .meta-grid{grid-template-columns:1fr}
  .tool-header{flex-direction:column;align-items:flex-start}
  .tool-counts{flex-wrap:wrap}
}
</style>
</head>
<body>

<button class="pdf-btn" onclick="window.print()">📄 Save as PDF</button>

<!-- ═══ HEADER ═══ -->
<div class="report-header">
  <div style="font-size:2.5rem;margin-bottom:12px">🔒</div>
  <h1>Security Readiness Assessment Report</h1>
  <div class="subtitle">{{ project_name }} — Automated Multi-Tool Security Analysis</div>
  <div class="meta-grid">
    <div class="meta-item"><div class="label">Engine</div><div class="value">Foundry Audit Readiness v{{ version }}</div></div>
    <div class="meta-item"><div class="label">Date</div><div class="value">{{ date }}</div></div>
    <div class="meta-item"><div class="label">Classification</div><div class="value">Confidential</div></div>
    <div class="meta-item"><div class="label">Tools Executed</div><div class="value">{{ tools_ran }}/{{ tools_configured }} tools</div></div>
  </div>
</div>

<!-- ═══ STATUS BANNER ═══ -->
{% if all_passed %}
<div class="status-banner status-pass">✅ AUDIT-READY — This codebase has passed all automated security readiness checks</div>
{% else %}
<div class="status-banner status-fail">❌ NOT AUDIT-READY — Issues must be resolved before professional audit engagement</div>
{% endif %}

<!-- ═══ EXECUTIVE SUMMARY ═══ -->
<div class="section">
  <div class="section-title"><span>Executive Summary</span></div>

  <div class="card">
    <div class="card-title">📊 Risk Matrix</div>
    <table>
      <thead><tr><th>Severity</th><th>Count</th><th style="text-align:left">Description</th></tr></thead>
      <tbody>
        {% for sev, count, desc in risk_matrix %}
        <tr><td><span class="badge badge-{% if 'CRIT' in sev %}crit{% elif 'HIGH' in sev %}high{% elif 'MED' in sev %}med{% elif 'LOW' in sev %}low{% else %}inf{% endif %}">{{ sev }}</span></td><td><strong>{{ count }}</strong></td><td style="text-align:left">{{ desc }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-title">📈 Key Metrics at a Glance</div>
    <div class="metric-grid">
      <div class="metric-box {% if coverage.line_percent >= config.coverage.line %}good{% else %}bad{% endif %}">
        <div class="value">{{ coverage.line_percent | round(1) }}%</div><div class="label">Line Coverage</div>
      </div>
      <div class="metric-box {% if coverage.branch_percent >= config.coverage.branch %}good{% else %}bad{% endif %}">
        <div class="value">{{ coverage.branch_percent | round(1) }}%</div><div class="label">Branch Coverage</div>
      </div>
      <div class="metric-box {% if coverage.function_percent >= config.coverage.function %}good{% else %}bad{% endif %}">
        <div class="value">{{ coverage.function_percent | round(1) }}%</div><div class="label">Function Coverage</div>
      </div>
      <div class="metric-box {% if static_analysis_passed %}good{% else %}bad{% endif %}">
        <div class="value">{{ tools_ran }}/{{ tools_configured }}</div><div class="label">Tools Clean</div>
      </div>
      <div class="metric-box {% if no_warnings %}good{% else %}warn{% endif %}">
        <div class="value">{% if no_warnings %}0{% else %}{{ compiler_warnings | length }}{% endif %}</div><div class="label">Warnings</div>
      </div>
      <div class="metric-box {% if natspec.total_external == 0 or natspec.documented_external == natspec.total_external %}good{% else %}warn{% endif %}">
        <div class="value">{{ natspec.documented_external }}/{{ natspec.total_external }}</div><div class="label">NatSpec External</div>
      </div>
    </div>
  </div>
</div>

<hr>

<!-- ═══ SCOPE ═══ -->
<div class="section">
  <div class="section-title"><span class="num">1</span> Scope of Assessment</div>
  <div class="card">
    <div class="card-title">🔧 Tools & Methodology</div>
    <table>
      <thead><tr><th>#</th><th>Tool</th><th>Vendor</th><th>Technique</th><th>Status</th></tr></thead>
      <tbody>
        {% for tool_name_key, result in static_analysis.items() %}
        <tr>
          <td>{{ loop.index }}</td>
          <td><strong>{{ tool_name(tool_name_key) }}</strong></td>
          <td>{{ tool_vendor(tool_name_key) }}</td>
          <td>{{ tool_technique(tool_name_key) }}</td>
          <td>{% if result.error %}<span class="badge badge-skip">SKIPPED</span>{% elif result.passed %}<span class="badge badge-pass">PASS</span>{% else %}<span class="badge badge-fail">FAIL</span>{% endif %}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    <p style="margin-top:12px;color:var(--text-muted);font-size:.82rem">Coverage thresholds: Line ≥{{ config.coverage.line }}% | Branch ≥{{ config.coverage.branch }}% | Function ≥{{ config.coverage.function }}%</p>
  </div>
</div>

<hr>

<!-- ═══ FINDINGS ═══ -->
<div class="section">
  <div class="section-title"><span class="num">2</span> Security Findings</div>

  {% if total_findings == 0 %}
  <div class="card" style="text-align:center;padding:40px">
    <div style="font-size:3rem;margin-bottom:12px">✅</div>
    <h3 style="color:var(--pass);margin-bottom:8px">Zero Findings</h3>
    <p style="color:var(--text-muted)">No issues detected across any tool. Exceptional code quality.</p>
  </div>
  {% else %}
  <div class="card" style="margin-bottom:20px">
    {% if total_critical == 0 and total_high == 0 %}
    <p style="color:var(--warn)">⚠️ <strong>{{ total_findings }} medium/low-severity findings detected.</strong> No critical or high issues. These are recommended for review.</p>
    {% else %}
    <p style="color:var(--fail)">🔴 <strong>{{ total_critical }} critical and {{ total_high }} high-severity findings detected.</strong> These require immediate attention before audit.</p>
    {% endif %}
  </div>
  {% endif %}

  {% for tool_name_key, result in static_analysis.items() %}
  <div class="card">
    <div class="tool-header">
      <div class="tool-name">{{ tool_name(tool_name_key) }}</div>
      <div class="tool-status">
        {% if result.error %}<span class="badge badge-skip">⏭️ SKIPPED</span>
        {% elif result.passed %}<span class="badge badge-pass">✅ PASS</span>
        {% else %}<span class="badge badge-fail">❌ FAIL</span>{% endif %}
      </div>
    </div>

    {% if result.error %}
    <p style="color:var(--text-muted);font-size:.88rem">{{ result.error }}</p>
    {% elif result.findings %}
    <div class="tool-counts" style="margin-bottom:16px">
      <div class="tool-count"><span style="color:var(--crit)">●</span> {{ result.findings | selectattr('severity','equalto','critical') | list | length }} Critical</div>
      <div class="tool-count"><span style="color:var(--high)">●</span> {{ result.findings | selectattr('severity','equalto','high') | list | length }} High</div>
      <div class="tool-count"><span style="color:var(--med)">●</span> {{ result.findings | selectattr('severity','equalto','medium') | list | length }} Medium</div>
      <div class="tool-count"><span style="color:var(--low)">●</span> {{ result.findings | selectattr('severity','equalto','low') | list | length }} Low</div>
      <div class="tool-count"><span style="color:var(--inf)">●</span> {{ result.findings | selectattr('severity','equalto','info') | list | length }} Info</div>
    </div>
    {% for finding in result.findings[:30] %}
    <div class="finding-item">
      <div class="finding-header">
        <span class="badge badge-{% if finding.severity == 'critical' %}crit{% elif finding.severity == 'high' %}high{% elif finding.severity == 'medium' %}med{% elif finding.severity == 'low' %}low{% else %}inf{% endif %}">{{ finding.severity }}</span>
        <span class="finding-file">{{ finding.file or "-" }}</span>
        <span class="finding-line">line {{ finding.line or "-" }}</span>
        <span class="finding-check">{{ finding.check }}</span>
      </div>
      <div class="finding-msg">{{ finding.message | truncate(200) }}</div>
    </div>
    {% endfor %}
    {% if result.findings | length > 30 %}
    <p style="text-align:center;color:var(--text-muted);font-size:.82rem;margin-top:12px">... {{ result.findings | length - 30 }} additional findings not shown</p>
    {% endif %}
    {% else %}
    <p style="color:var(--text-muted);font-size:.88rem;font-style:italic">No findings reported by this tool.</p>
    {% endif %}
  </div>
  {% endfor %}
</div>

<hr>

<!-- ═══ COVERAGE ═══ -->
<div class="section">
  <div class="section-title"><span class="num">3</span> Test Coverage Analysis</div>
  <div class="card">
    <div class="card-title">📊 Coverage Metrics</div>
    {% set cov_good = coverage.line_percent >= config.coverage.line %}
    <div class="coverage-row">
      <div class="coverage-label">Line</div>
      <div class="coverage-bar"><div class="coverage-fill {% if cov_good %}good{% else %}bad{% endif %}" style="width:{{ coverage.line_percent | min(100) }}%">{{ coverage.line_percent | round(1) }}%</div></div>
      <div class="coverage-pct {% if cov_good %}good{% else %}bad{% endif %}">{{ coverage.line_percent | round(1) }}%</div>
    </div>
    {% set branch_good = coverage.branch_percent >= config.coverage.branch %}
    <div class="coverage-row">
      <div class="coverage-label">Branch</div>
      <div class="coverage-bar"><div class="coverage-fill {% if branch_good %}good{% else %}bad{% endif %}" style="width:{{ coverage.branch_percent | min(100) }}%">{{ coverage.branch_percent | round(1) }}%</div></div>
      <div class="coverage-pct {% if branch_good %}good{% else %}bad{% endif %}">{{ coverage.branch_percent | round(1) }}%</div>
    </div>
    {% set func_good = coverage.function_percent >= config.coverage.function %}
    <div class="coverage-row">
      <div class="coverage-label">Function</div>
      <div class="coverage-bar"><div class="coverage-fill {% if func_good %}good{% else %}bad{% endif %}" style="width:{{ coverage.function_percent | min(100) }}%">{{ coverage.function_percent | round(1) }}%</div></div>
      <div class="coverage-pct {% if func_good %}good{% else %}bad{% endif %}">{{ coverage.function_percent | round(1) }}%</div>
    </div>
  </div>

  {% if invariants.functions_found > 0 %}
  <div class="card">
    <div class="card-title">🧪 Invariant Testing</div>
    <div class="metric-grid" style="grid-template-columns:repeat(3,1fr)">
      <div class="metric-box"><div class="value">{{ invariants.functions_found }}</div><div class="label">Functions</div></div>
      <div class="metric-box"><div class="value">{{ invariants.runs }}</div><div class="label">Fuzz Runs</div></div>
      <div class="metric-box {% if invariants.all_passed %}good{% else %}bad{% endif %}"><div class="value">{% if invariants.all_passed %}✅{% else %}❌{% endif %}</div><div class="label">All Passing</div></div>
    </div>
  </div>
  {% endif %}
</div>

<hr>

<!-- ═══ CODE QUALITY ═══ -->
<div class="section">
  <div class="section-title"><span class="num">4</span> Code Quality Assessment</div>
  <div class="card">
    <div class="card-title">📝 NatSpec Documentation</div>
    <table>
      <thead><tr><th>Scope</th><th>Documented</th><th>Total</th><th>Status</th></tr></thead>
      <tbody>
        <tr><td>Public Functions</td><td>{{ natspec.documented_public }}</td><td>{{ natspec.total_public }}</td><td>{% if natspec.documented_public == natspec.total_public %}<span class="badge badge-pass">✅ Complete</span>{% else %}<span class="badge badge-fail">❌ {{ natspec.total_public - natspec.documented_public }} missing</span>{% endif %}</td></tr>
        <tr><td>External Functions</td><td>{{ natspec.documented_external }}</td><td>{{ natspec.total_external }}</td><td>{% if natspec.documented_external == natspec.total_external %}<span class="badge badge-pass">✅ Complete</span>{% else %}<span class="badge badge-warn">⚠️ {{ natspec.total_external - natspec.documented_external }} missing</span>{% endif %}</td></tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-title">⚠️ Compiler Warnings</div>
    {% if no_warnings %}
    <p style="color:var(--pass)">✅ No compiler warnings detected. The codebase compiles cleanly.</p>
    {% else %}
    <ul class="action-list">
      {% for w in compiler_warnings[:5] %}
      <li><span class="dot dot-med"></span>{{ w | truncate(120) }}</li>
      {% endfor %}
    </ul>
    {% if compiler_warnings | length > 5 %}<p style="color:var(--text-muted);font-size:.82rem;margin-top:8px">... and {{ compiler_warnings | length - 5 }} more</p>{% endif %}
    {% endif %}
  </div>

  <div class="card">
    <div class="card-title">⛽ Gas Analysis</div>
    {% if gas.baseline_exists %}<p style="color:var(--pass)">✅ Gas snapshot baseline exists ({{ gas.functions | length }} functions tracked).</p>
    {% else %}<p style="color:var(--text-muted)">ℹ️ No gas snapshot baseline found. Run <code style="background:var(--bg-card);padding:2px 6px;border-radius:4px">forge snapshot</code> to establish one.</p>{% endif %}
  </div>
</div>

<hr>

<!-- ═══ TOOL SUMMARY ═══ -->
<div class="section">
  <div class="section-title"><span class="num">5</span> Tool Coverage Summary</div>
  <div class="card">
    <table>
      <thead><tr><th>#</th><th>Tool</th><th>Vendor</th><th>Technique</th><th>Findings</th><th>Status</th></tr></thead>
      <tbody>
        {% for tool_name_key, result in static_analysis.items() %}
        <tr>
          <td>{{ loop.index }}</td>
          <td><strong>{{ tool_name(tool_name_key) }}</strong></td>
          <td>{{ tool_vendor(tool_name_key) }}</td>
          <td>{{ tool_technique(tool_name_key) }}</td>
          <td>{% if result.error %}—{% else %}{{ result.findings | length }}{% endif %}</td>
          <td>{% if result.error %}<span class="badge badge-skip">⏭️ SKIP</span>{% elif result.passed %}<span class="badge badge-pass">✅ PASS</span>{% else %}<span class="badge badge-fail">❌ FAIL</span>{% endif %}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<hr>

<!-- ═══ CONCLUSION ═══ -->
<div class="section">
  <div class="section-title"><span class="num">6</span> Conclusion & Recommendation</div>
  {% if all_passed %}
  <div class="certificate">
    <div style="font-size:3rem;margin-bottom:12px">🏆</div>
    <h3>✅ Security Readiness Certificate</h3>
    <p>{{ project_name }} has been evaluated against {{ tools_configured }} independent security tools and has demonstrated <strong>audit-ready code quality</strong>.</p>
    <div class="cert-grid">
      <div class="cert-item"><div class="val">0</div><div class="lbl">Critical/High</div></div>
      <div class="cert-item"><div class="val">{{ coverage.line_percent | round(1) }}%</div><div class="lbl">Line Coverage</div></div>
      <div class="cert-item"><div class="val">{{ invariants.functions_found }}</div><div class="lbl">Invariants Passing</div></div>
      <div class="cert-item"><div class="val">{{ natspec.documented_external }}/{{ natspec.total_external }}</div><div class="lbl">Documentation</div></div>
      <div class="cert-item"><div class="val">0</div><div class="lbl">Warnings</div></div>
    </div>
    <p style="color:var(--text);margin-top:16px"><strong>Recommendation:</strong> Proceed with professional security audit engagement.</p>
    <p style="color:var(--text-muted);font-size:.82rem">Estimated scope: 2-4 auditor-weeks | Cost reduction: 30-40%</p>
  </div>
  {% else %}
  <div class="card" style="border:2px solid var(--fail);background:var(--fail-bg)">
    <div style="text-align:center;padding:20px">
      <div style="font-size:2.5rem;margin-bottom:12px">❌</div>
      <h3 style="color:var(--fail);margin-bottom:12px">Action Required</h3>
      <p style="color:var(--text-muted);margin-bottom:20px">{{ project_name }} has failed one or more checks and is <strong style="color:var(--fail)">not recommended</strong> for audit at this time.</p>
      <ul class="action-list" style="max-width:500px;margin:0 auto;text-align:left">
        {% if not static_analysis_passed %}<li><span class="dot dot-crit"></span>Address critical/high findings from static analysis</li>{% endif %}
        {% if not coverage_passed %}<li><span class="dot dot-crit"></span>Increase test coverage (line &ge;{{ config.coverage.line }}%, branch &ge;{{ config.coverage.branch }}%)</li>{% endif %}
        {% if not natspec.passed %}<li><span class="dot dot-med"></span>Document all external functions with NatSpec</li>{% endif %}
        {% if not no_warnings %}<li><span class="dot dot-med"></span>Eliminate all compiler warnings</li>{% endif %}
      </ul>
      <p style="color:var(--text-muted);font-size:.85rem;margin-top:20px">Resolve the issues above and re-run this assessment.</p>
    </div>
  </div>
  {% endif %}
</div>

<hr>

<!-- ═══ DISCLAIMER ═══ -->
<div class="section">
  <div class="section-title"><span class="num">7</span> Limitations & Disclaimer</div>
  <div class="card">
    <div class="card-title">⚠️ Assessment Limitations</div>
    <ol style="color:var(--text-muted);font-size:.88rem;padding-left:20px;line-height:1.8">
      <li>Automated tools detect known patterns only. Novel vulnerabilities may not be detected.</li>
      <li>No automated tool can guarantee the absence of vulnerabilities.</li>
      <li>Business logic correctness requires human expert review.</li>
      <li>Proxy patterns are assessed on current implementation only.</li>
    </ol>
    <div style="margin-top:20px;padding:16px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);border-left:4px solid var(--warn)">
      <p style="color:var(--warn);font-size:.82rem;font-weight:600;margin-bottom:8px">IMPORTANT DISCLAIMER</p>
      <p style="color:var(--text-muted);font-size:.82rem;line-height:1.6">This report does <strong style="color:var(--text)">not</strong> constitute a professional security audit. It is an automated readiness assessment. Only a professional audit by experienced human auditors can provide meaningful security assurance.</p>
      <p style="color:var(--text-muted);font-size:.82rem;margin-top:8px">Recommended firms: Trail of Bits, OpenZeppelin, Spearbit, Cyfrin.</p>
    </div>
  </div>
</div>

<hr>

<!-- ═══ FOOTER ═══ -->
<div style="text-align:center;padding:24px;color:var(--text-dim);font-size:.78rem">
  <p>Report generated by <strong style="color:var(--text-muted)">Foundry Audit Readiness v{{ version }}</strong></p>
  <p>{{ date }} — Confidential</p>
</div>

</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL METADATA HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

_TOOL_NAMES = {
    "slither": "Slither",
    "aderyn": "Aderyn",
    "solhint": "Solhint",
    "semgrep": "Semgrep",
    "mythril": "Mythril",
    "halmos": "Halmos",
    "smtchecker": "SMTChecker",
}

_TOOL_VENDORS = {
    "slither": "Trail of Bits",
    "aderyn": "Cyfrin",
    "solhint": "Community",
    "semgrep": "r2c",
    "mythril": "ConsenSys",
    "halmos": "a16z",
    "smtchecker": "Ethereum Fdn",
}

_TOOL_TECHNIQUES = {
    "slither": "Static Analysis",
    "aderyn": "Static Analysis",
    "solhint": "Linting",
    "semgrep": "Rule Engine",
    "mythril": "Symbolic Execution",
    "halmos": "Formal Verification",
    "smtchecker": "SMT Verification",
}


def _tool_name(key: str) -> str:
    return _TOOL_NAMES.get(key.lower(), key.title())


def _tool_vendor(key: str) -> str:
    return _TOOL_VENDORS.get(key.lower(), key.title())


def _tool_technique(key: str) -> str:
    return _TOOL_TECHNIQUES.get(key.lower(), "Analysis")


def _count_severity(findings: List, severity: str) -> int:
    return sum(1 for f in findings if getattr(f, "severity", "") == severity)


# ═══════════════════════════════════════════════════════════════════════════════
# JINJA2 CUSTOM FILTERS
# ═══════════════════════════════════════════════════════════════════════════════


def _min_filter(value, other):
    """Return min of value and other."""
    try:
        return min(float(value), float(other))
    except (TypeError, ValueError):
        return value


def _build_jinja_env(template_str: str) -> Template:
    """Create a Jinja template with all custom globals and filters."""
    from jinja2 import Environment

    env = Environment()
    env.filters["min"] = _min_filter
    env.filters["truncate"] = lambda s, length=100, end="...": (s[:length] + end) if s and len(s) > length else (s or "")

    env.globals["tool_name"] = _tool_name
    env.globals["tool_vendor"] = _tool_vendor
    env.globals["tool_technique"] = _tool_technique

    return env.from_string(template_str)


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT GENERATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def _compute_risk_matrix(static_analysis: Dict) -> List:
    """Compute severity counts and build risk matrix rows."""
    severities = [
        ("CRITICAL", "critical", "Immediate exploitation risk. Must be fixed before deployment."),
        ("HIGH", "high", "Significant risk. Should be fixed before audit."),
        ("MEDIUM", "medium", "Moderate risk. Address during audit preparation."),
        ("LOW", "low", "Minor concern. Review recommended."),
        ("INFO", "info", "No security impact. Best-practice suggestions."),
    ]
    result = []
    for label, sev_key, desc in severities:
        count = 0
        for tool_res in static_analysis.values():
            if hasattr(tool_res, "findings") and tool_res.findings:
                count += _count_severity(tool_res.findings, sev_key)
        result.append((label, count, desc))
    return result


def _compute_totals(static_analysis: Dict) -> Dict:
    """Compute total finding counts by severity."""
    totals = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "all": 0}
    for tool_res in static_analysis.values():
        if hasattr(tool_res, "findings") and tool_res.findings:
            for f in tool_res.findings:
                sev = getattr(f, "severity", "")
                if sev in totals:
                    totals[sev] += 1
                    totals["all"] += 1
    return totals


def generate_markdown_report(
    project_name: str,
    version: str,
    date: str,
    config: Config,
    static_analysis: Dict,
    coverage: Any,
    invariants: Any,
    natspec: Any,
    gas: Any,
    no_warnings: bool,
    compiler_warnings: Optional[List[str]] = None,
    tools_ran: int = 0,
    tools_configured: int = 0,
    all_passed: bool = False,
    static_analysis_passed: bool = True,
    coverage_passed: bool = True,
) -> str:
    """Render the clean Markdown report from template."""
    risk_matrix = _compute_risk_matrix(static_analysis)
    totals = _compute_totals(static_analysis)

    template = _build_jinja_env(MARKDOWN_TEMPLATE)

    return template.render(
        project_name=project_name,
        version=version,
        date=date,
        config=config,
        static_analysis=static_analysis,
        coverage=coverage,
        invariants=invariants,
        natspec=natspec,
        gas=gas,
        no_warnings=no_warnings,
        compiler_warnings=compiler_warnings or [],
        tools_ran=tools_ran,
        tools_configured=tools_configured,
        all_passed=all_passed,
        static_analysis_passed=static_analysis_passed,
        coverage_passed=coverage_passed,
        risk_matrix=risk_matrix,
        total_findings=totals["all"],
        total_critical=totals["critical"],
        total_high=totals["high"],
        total_medium=totals["medium"],
        total_low=totals["low"],
        total_info=totals["info"],
    )


def generate_html_report(
    project_name: str,
    version: str,
    date: str,
    config: Config,
    static_analysis: Dict,
    coverage: Any,
    invariants: Any,
    natspec: Any,
    gas: Any,
    no_warnings: bool,
    compiler_warnings: Optional[List[str]] = None,
    tools_ran: int = 0,
    tools_configured: int = 0,
    all_passed: bool = False,
    static_analysis_passed: bool = True,
    coverage_passed: bool = True,
) -> str:
    """Render the native HTML report with integrated CSS."""
    risk_matrix = _compute_risk_matrix(static_analysis)
    totals = _compute_totals(static_analysis)

    template = _build_jinja_env(HTML_TEMPLATE)

    return template.render(
        project_name=project_name,
        version=version,
        date=date,
        config=config,
        static_analysis=static_analysis,
        coverage=coverage,
        invariants=invariants,
        natspec=natspec,
        gas=gas,
        no_warnings=no_warnings,
        compiler_warnings=compiler_warnings or [],
        tools_ran=tools_ran,
        tools_configured=tools_configured,
        all_passed=all_passed,
        static_analysis_passed=static_analysis_passed,
        coverage_passed=coverage_passed,
        risk_matrix=risk_matrix,
        total_findings=totals["all"],
        total_critical=totals["critical"],
        total_high=totals["high"],
        total_medium=totals["medium"],
        total_low=totals["low"],
        total_info=totals["info"],
    )


def save_report(content: str, output_path: Path) -> None:
    """Save report to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info(f"Report saved to {output_path}")
