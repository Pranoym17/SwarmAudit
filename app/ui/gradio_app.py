import os
import warnings

import gradio as gr

from app.agents.graph import AuditGraph
from app.config import get_settings
from app.schemas import AuditReport, Severity
from app.services.llm_client import LLMClient
from app.services.benchmark import BenchmarkService
from app.services.report_formatter import (
    format_empty_finding_detail_html,
    format_finding_detail_html,
    format_report_overview_html,
    write_report_exports,
)


EXAMPLE_REPOS = {
    "Requests": "https://github.com/psf/requests",
    "ItsDangerous": "https://github.com/pallets/itsdangerous",
    "Flask": "https://github.com/pallets/flask",
}

AGENT_SWARM = [
    ("Crawler", "Fetch repository tree", "Crawler Agent", "mapped"),
    ("Chunker", "Tokenize and segment files", "Chunker", "created"),
    ("Security", "CVE and secret scanning", "Security Agent", "found"),
    ("Performance", "Hot-path and complexity", "Performance Agent", "found"),
    ("Quality", "Lint, types, smells", "Quality Agent", "found"),
    ("Docs", "Coverage and accuracy", "Docs Agent", "found"),
    ("Config", "Production config risk", "Config Agent", "found"),
    ("Dependency", "Manifest and CVE checks", "Dependency Agent", "found"),
    ("Errors", "Resilience paths", "Error Handling Agent", "found"),
    ("Observability", "Logs and health checks", "Observability Agent", "found"),
    ("ROCm", "CUDA portability", "CUDA-to-ROCm Agent", "found"),
    ("Synthesizer", "Merge findings into report", "Synthesizer Agent", "final report"),
]


APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --sa-bg: #080d14;
    --sa-surface: #0d141d;
    --sa-panel: #101923;
    --sa-panel-high: #162233;
    --sa-panel-higher: #1b293a;
    --sa-border: #26364a;
    --sa-border-strong: #33465e;
    --sa-text: #e6f0ff;
    --sa-muted: #8aa0b8;
    --sa-primary: #60a5fa;
    --sa-primary-soft: rgba(96, 165, 250, 0.14);
    --sa-blue: #06b6d4;
    --sa-orange: #f97316;
    --sa-yellow: #eab308;
    --sa-red: #ef4444;
    --sa-green: #22c55e;
    --sa-info: #64748b;
    --sa-card-shadow: 0 18px 60px rgba(0, 0, 0, 0.24);
}

* {
    scrollbar-width: thin;
    scrollbar-color: #475569 #0f172a;
}

*::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

*::-webkit-scrollbar-track {
    background: #0f172a;
}

*::-webkit-scrollbar-thumb {
    background: #475569;
    border-radius: 999px;
    border: 2px solid #0f172a;
}

*::-webkit-scrollbar-thumb:hover {
    background: #64748b;
}

.gradio-container {
    background:
        radial-gradient(circle at 18% -10%, rgba(96, 165, 250, 0.08), transparent 30%),
        linear-gradient(180deg, #0a1018 0%, var(--sa-bg) 38%, #070b11 100%) !important;
    color: var(--sa-text) !important;
    font-family: Inter, system-ui, sans-serif !important;
}

#swarm-shell {
    max-width: 1440px;
    margin: 0 auto;
}

.swarm-topbar {
    border: 1px solid rgba(96, 165, 250, 0.18);
    background:
        linear-gradient(135deg, rgba(16, 25, 35, 0.94), rgba(13, 20, 29, 0.86)),
        rgba(16, 25, 35, 0.86);
    border-radius: 10px;
    padding: 14px 16px 13px;
    margin-bottom: 12px;
    box-shadow: 0 18px 70px rgba(0, 0, 0, 0.18), inset 0 1px 0 rgba(230, 240, 255, 0.04);
    backdrop-filter: blur(10px);
}

.swarm-brand-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 10px;
}

.swarm-brand {
    font-size: 19px;
    line-height: 24px;
    font-weight: 700;
    letter-spacing: 0;
}

.swarm-tagline {
    color: var(--sa-muted);
    font-size: 12px;
    line-height: 18px;
}

.swarm-status {
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    text-transform: uppercase;
}

.swarm-progressbar {
    height: 3px;
    border-radius: 999px;
    background: rgba(38, 54, 74, 0.7);
    overflow: hidden;
}

.swarm-progressbar span {
    display: block;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, var(--sa-primary), #22c55e);
    box-shadow: 0 0 18px rgba(96, 165, 250, 0.24);
}

.swarm-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 10px;
    margin: 12px 0;
}

.swarm-metric {
    border: 1px solid rgba(38, 54, 74, 0.95);
    background: linear-gradient(180deg, rgba(22, 34, 51, 0.86), rgba(16, 25, 35, 0.9));
    border-radius: 8px;
    padding: 12px;
    box-shadow: inset 0 1px 0 rgba(230, 240, 255, 0.035);
    transition: border-color 160ms ease, transform 160ms ease, background 160ms ease;
}

.swarm-metric:hover {
    border-color: rgba(96, 165, 250, 0.34);
    transform: translateY(-1px);
}

.swarm-metric span {
    display: block;
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    text-transform: uppercase;
    letter-spacing: 0;
}

.swarm-metric strong {
    display: block;
    color: var(--sa-text);
    font-size: 22px;
    line-height: 28px;
    margin-top: 2px;
}

.metric-critical strong,
.metric-critical span {
    color: var(--sa-red);
}

.metric-high strong,
.metric-high span {
    color: var(--sa-orange);
}

.metric-medium strong,
.metric-medium span {
    color: var(--sa-yellow);
}

.metric-low strong,
.metric-low span {
    color: var(--sa-blue);
}

.swarm-card,
.swarm-panel,
.swarm-export {
    border: 1px solid var(--sa-border) !important;
    background: rgba(16, 25, 35, 0.92) !important;
    border-radius: 8px !important;
    box-shadow: inset 0 1px 0 rgba(230, 240, 255, 0.03);
}

.agent-card {
    border: 1px solid rgba(38, 54, 74, 0.95);
    background: linear-gradient(180deg, rgba(16, 25, 35, 0.95), rgba(13, 20, 29, 0.96));
    border-radius: 9px;
    overflow: hidden;
    margin-bottom: 12px;
    box-shadow: inset 0 1px 0 rgba(230, 240, 255, 0.035);
}

.agent-card-header,
.audit-console-header {
    min-height: 42px;
    border-bottom: 1px solid var(--sa-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 14px;
}

.agent-card-title,
.audit-console-title {
    color: var(--sa-text);
    font-size: 13px;
    line-height: 18px;
    font-weight: 700;
}

.agent-card-count,
.audit-filter-row {
    color: var(--sa-muted);
    font: 500 11px/16px JetBrains Mono, monospace;
}

.agent-list {
    padding: 12px 14px 14px;
}

.agent-item {
    display: grid;
    grid-template-columns: 28px 1fr auto;
    gap: 10px;
    align-items: center;
    padding: 8px 0;
    border-radius: 7px;
    transition: background 150ms ease, border-color 150ms ease;
}

.agent-icon {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: 1px solid var(--sa-border);
    background: rgba(27, 41, 58, 0.88);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--sa-muted);
    font: 700 11px/16px JetBrains Mono, monospace;
}

.agent-name {
    color: var(--sa-text);
    font-size: 13px;
    line-height: 18px;
    font-weight: 700;
}

.agent-desc {
    color: var(--sa-muted);
    font-size: 11px;
    line-height: 16px;
}

.agent-status {
    font: 600 11px/16px JetBrains Mono, monospace;
}

.agent-status.done {
    color: var(--sa-green);
}

.agent-status.running {
    color: var(--sa-primary);
}

.agent-status.idle {
    color: var(--sa-muted);
}

.agent-item.running {
    background: rgba(34, 197, 94, 0.08);
    border: 1px solid rgba(34, 197, 94, 0.22);
    border-radius: 7px;
    margin: 2px -6px;
    padding: 8px 6px;
}

.swarm-card textarea,
.swarm-card input,
.swarm-card select {
    font-family: JetBrains Mono, monospace !important;
}

.swarm-progress textarea {
    min-height: 285px !important;
    font-family: JetBrains Mono, monospace !important;
    font-size: 12px !important;
    line-height: 20px !important;
    color: #d8e3ef !important;
    background: #0b1118 !important;
}

.swarm-report {
    min-height: 560px;
}

.swarm-report h1,
.swarm-report h2,
.swarm-report h3 {
    color: var(--sa-text) !important;
}

.swarm-report code,
.swarm-report pre {
    font-family: JetBrains Mono, monospace !important;
}

.swarm-export {
    padding: 12px !important;
}

.audit-actionbar {
    border: 1px solid rgba(38, 54, 74, 0.95) !important;
    background: linear-gradient(180deg, rgba(16, 25, 35, 0.92), rgba(13, 20, 29, 0.94)) !important;
    border-radius: 10px !important;
    padding: 7px 8px !important;
    margin-bottom: 12px !important;
    box-shadow: inset 0 1px 0 rgba(230, 240, 255, 0.035);
}

.audit-actionbar .form,
.audit-actionbar .block {
    min-height: 0 !important;
}

.audit-actionbar .gradio-row,
.audit-actionbar .row {
    align-items: center !important;
    gap: 8px !important;
}

.repo-input {
    min-width: min(560px, 100%) !important;
}

.audit-actionbar label {
    color: var(--sa-muted) !important;
    font: 600 11px/16px JetBrains Mono, monospace !important;
    text-transform: lowercase !important;
}

.audit-actionbar input {
    background: #111a25 !important;
    border: 1px solid var(--sa-border) !important;
    border-radius: 7px !important;
    color: var(--sa-text) !important;
    font-family: JetBrains Mono, monospace !important;
    min-height: 34px !important;
    height: 34px !important;
    padding: 6px 10px !important;
    transition: border-color 150ms ease, box-shadow 150ms ease, background 150ms ease;
}

.audit-actionbar input:focus {
    border-color: rgba(96, 165, 250, 0.7) !important;
    box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.11) !important;
    background: #132033 !important;
}

.example-label {
    display: flex;
    align-items: center;
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    height: 34px;
    padding: 0 8px 0 12px;
}

.example-chip button {
    background: rgba(74, 91, 113, 0.82) !important;
    border: 1px solid rgba(100, 116, 139, 0.42) !important;
    border-radius: 12px !important;
    color: var(--sa-text) !important;
    font: 700 13px/18px Inter, system-ui, sans-serif !important;
    min-width: 0 !important;
    height: 40px !important;
    min-height: 40px !important;
    padding: 0 20px !important;
    margin: 0 4px !important;
    transition: border-color 150ms ease, background 150ms ease, color 150ms ease, transform 150ms ease;
}

.example-chip button:hover {
    background: rgba(87, 108, 135, 0.92) !important;
    border-color: rgba(96, 165, 250, 0.36) !important;
    color: var(--sa-text) !important;
    transform: translateY(-1px);
}

button.primary,
.gradio-button.primary {
    background: linear-gradient(180deg, #7bb8ff, var(--sa-primary)) !important;
    color: #08111d !important;
    border: 1px solid rgba(147, 197, 253, 0.48) !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.08), 0 10px 26px rgba(96, 165, 250, 0.14);
    min-height: 34px !important;
    height: 34px !important;
    padding: 0 14px !important;
    transition: filter 150ms ease, transform 150ms ease, box-shadow 150ms ease;
}

button.primary:hover,
.gradio-button.primary:hover {
    filter: brightness(1.04);
    transform: translateY(-1px);
    box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.1), 0 14px 30px rgba(96, 165, 250, 0.18);
}

.tabs {
    border: 1px solid var(--sa-border) !important;
    border-radius: 10px !important;
    background: rgba(8, 13, 20, 0.74) !important;
    padding: 8px !important;
    box-shadow: inset 0 1px 0 rgba(230, 240, 255, 0.03);
}

.tab-nav button {
    border-radius: 7px !important;
    font-weight: 600 !important;
}

.tab-nav button.selected,
.tab-nav button[aria-selected="true"] {
    color: var(--sa-primary) !important;
    box-shadow: inset 0 -1px 0 var(--sa-primary), 0 10px 24px rgba(96, 165, 250, 0.08);
}

.swarm-note {
    color: var(--sa-muted);
    font-size: 13px;
    line-height: 20px;
    margin: 0 0 10px;
}

.swarm-report a {
    color: var(--sa-primary) !important;
}

.swarm-report blockquote {
    border-left: 3px solid var(--sa-border-strong) !important;
    color: var(--sa-muted) !important;
}

.audit-console {
    border: 1px solid var(--sa-border);
    background: rgba(16, 25, 35, 0.92);
    border-radius: 9px;
    overflow: hidden;
    min-height: 700px;
}

.findings-list-radio,
.finding-detail-panel {
    border: 1px solid rgba(38, 54, 74, 0.95);
    background: rgba(16, 25, 35, 0.94);
    border-radius: 0;
    overflow: hidden;
}

.findings-list-radio {
    height: 690px;
    max-height: 690px;
    overflow-y: auto !important;
    border-right: 0;
    border-radius: 0 0 0 8px;
    scrollbar-gutter: auto;
}

.report-toolbar {
    min-height: 41px;
    border: 1px solid rgba(38, 54, 74, 0.95);
    border-bottom: 0;
    background: linear-gradient(180deg, rgba(16, 25, 35, 0.98), rgba(13, 20, 29, 0.96));
    border-radius: 9px 9px 0 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 0 13px;
}

.report-header-row {
    border: 1px solid rgba(38, 54, 74, 0.95) !important;
    border-bottom: 0 !important;
    background: linear-gradient(180deg, rgba(16, 25, 35, 0.98), rgba(13, 20, 29, 0.96)) !important;
    border-radius: 9px 9px 0 0 !important;
    align-items: center !important;
    gap: 8px !important;
    padding: 7px 10px !important;
}

.report-header-row .report-toolbar {
    border: 0 !important;
    background: transparent !important;
    min-height: 28px !important;
    padding: 0 !important;
}

.severity-filter-radio {
    min-width: 360px !important;
}

.severity-filter-radio .wrap,
.severity-filter-radio .block,
.severity-filter-radio fieldset {
    background: transparent !important;
    border: 0 !important;
    padding: 0 !important;
}

.severity-filter-radio label {
    border: 1px solid transparent !important;
    border-radius: 6px !important;
    background: transparent !important;
    padding: 5px 7px !important;
    margin: 0 1px !important;
    color: var(--sa-muted) !important;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease;
}

.severity-filter-radio label:hover,
.severity-filter-radio label:has(input:checked) {
    background: rgba(22, 34, 51, 0.92) !important;
    border-color: rgba(96, 165, 250, 0.18) !important;
    color: var(--sa-text) !important;
}

.severity-filter-radio label:has(input[value^="Critical"]) span { color: var(--sa-red) !important; }
.severity-filter-radio label:has(input[value^="High"]) span { color: var(--sa-orange) !important; }
.severity-filter-radio label:has(input[value^="Medium"]) span { color: var(--sa-yellow) !important; }
.severity-filter-radio label:has(input[value^="Low"]) span { color: var(--sa-blue) !important; }

.severity-filter-radio span {
    font: 700 10px/14px JetBrains Mono, monospace !important;
    white-space: nowrap !important;
}

.severity-filter-radio input {
    display: none !important;
}

.report-download button {
    height: 30px !important;
    min-height: 30px !important;
    border-radius: 7px !important;
    border: 1px solid var(--sa-border) !important;
    background: rgba(22, 34, 51, 0.82) !important;
    color: var(--sa-text) !important;
    font: 700 11px/16px Inter, system-ui, sans-serif !important;
    padding: 0 10px !important;
}

.report-download button:hover {
    border-color: rgba(96, 165, 250, 0.34) !important;
    background: rgba(27, 41, 58, 0.96) !important;
}

.report-overview {
    border: 1px solid rgba(38, 54, 74, 0.95);
    border-top: 0;
    background: rgba(16, 25, 35, 0.88);
    display: grid;
    grid-template-columns: repeat(2, minmax(120px, 0.7fr)) repeat(2, minmax(170px, 1fr));
    gap: 0;
}

.overview-column {
    border-right: 1px solid var(--sa-border);
    padding: 10px 12px;
}

.overview-column:last-child {
    border-right: 0;
}

.overview-column span {
    color: var(--sa-muted);
    font: 600 10px/15px JetBrains Mono, monospace;
    text-transform: uppercase;
}

.overview-column strong {
    display: block;
    color: var(--sa-text);
    font-size: 18px;
    line-height: 24px;
    margin-top: 2px;
}

.overview-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 4px;
}

.overview-tags span {
    border: 1px solid var(--sa-border);
    border-radius: 6px;
    background: rgba(22, 34, 51, 0.82);
    color: #cbd5e1;
    padding: 3px 6px;
    text-transform: none;
}

.report-body {
    border: 1px solid var(--sa-border) !important;
    border-top: 0 !important;
    background: rgba(16, 25, 35, 0.94) !important;
    border-radius: 0 0 9px 9px !important;
    overflow: hidden !important;
}

.report-body > .form {
    gap: 0 !important;
}

.report-title {
    color: var(--sa-text);
    font-size: 13px;
    line-height: 18px;
    font-weight: 700;
}

.report-title span {
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    margin-right: 6px;
}

.report-subnote {
    color: var(--sa-muted);
    font: 500 10px/14px JetBrains Mono, monospace;
    margin-top: 1px;
    opacity: 0.74;
}

.findings-list-radio .wrap,
.findings-list-radio .block,
.findings-list-radio fieldset {
    background: transparent !important;
    border: 0 !important;
    padding: 0 !important;
}

.findings-list-radio label {
    border-bottom: 1px solid rgba(38, 54, 74, 0.72) !important;
    background: rgba(16, 25, 35, 0.5) !important;
    padding: 12px 13px !important;
    margin: 0 !important;
    align-items: flex-start !important;
    cursor: pointer !important;
    transition: background 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
}

.findings-list-radio label:hover {
    background: rgba(22, 34, 51, 0.86) !important;
}

.findings-list-radio input:checked + span,
.findings-list-radio label:has(input:checked) {
    background: linear-gradient(90deg, rgba(96, 165, 250, 0.14), rgba(22, 34, 51, 0.86)) !important;
    box-shadow: inset 2px 0 0 var(--sa-primary);
}

.findings-list-radio span {
    color: #dce4ee !important;
    font: 600 12px/18px Inter, system-ui, sans-serif !important;
    white-space: pre-wrap !important;
}

.findings-list-radio label:has(input[value^="CRIT"]) span { color: var(--sa-red) !important; }
.findings-list-radio label:has(input[value^="HIGH"]) span { color: var(--sa-orange) !important; }
.findings-list-radio label:has(input[value^="MED"]) span { color: var(--sa-yellow) !important; }
.findings-list-radio label:has(input[value^="LOW"]) span { color: var(--sa-blue) !important; }

.findings-list-radio label:has(input[value^="LOW"]) {
    background: rgba(6, 182, 212, 0.055) !important;
}

.findings-list-radio input {
    margin-top: 4px !important;
    accent-color: var(--sa-primary) !important;
}

.finding-detail-panel {
    height: 690px;
    max-height: 690px;
    overflow-y: auto;
    border-radius: 0 0 8px 0;
    scrollbar-gutter: auto;
}

.swarm-report .finding-detail-panel {
    border: 0;
    background: transparent;
    border-radius: 0;
}

.audit-filter-row {
    display: flex;
    align-items: center;
    gap: 10px;
    white-space: nowrap;
}

.filter-pill {
    background: rgba(32, 42, 54, 0.9);
    border-radius: 6px;
    padding: 5px 10px;
    color: var(--sa-muted);
}

.filter-pill.active {
    color: var(--sa-text);
}

.filter-dot {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    display: inline-block;
}

.dot-critical { background: var(--sa-red); }
.dot-high { background: var(--sa-orange); }
.dot-medium { background: var(--sa-yellow); }
.dot-low { background: var(--sa-blue); }

.audit-console-body {
    display: grid;
    grid-template-columns: minmax(280px, 42%) 1fr;
    min-height: 657px;
}

.finding-list {
    border-right: 1px solid var(--sa-border);
    background: #121922;
}

.finding-row {
    padding: 14px 16px;
    border-bottom: 1px solid var(--sa-border);
    background: #121922;
}

.finding-row:first-child {
    background: #1b232d;
}

.finding-row-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--sa-muted);
    font: 500 11px/16px JetBrains Mono, monospace;
    margin-bottom: 7px;
}

.severity-badge {
    border: 1px solid currentColor;
    border-radius: 5px;
    padding: 2px 7px;
    font: 700 10px/14px JetBrains Mono, monospace;
    color: var(--sa-muted);
    letter-spacing: 0.01em;
}

.severity-critical .severity-badge,
.severity-badge.severity-critical {
    color: #fecaca;
    background: rgba(239, 68, 68, 0.13);
    border-color: rgba(239, 68, 68, 0.55);
}
.severity-high .severity-badge,
.severity-badge.severity-high {
    color: #fed7aa;
    background: rgba(249, 115, 22, 0.13);
    border-color: rgba(249, 115, 22, 0.55);
}
.severity-medium .severity-badge,
.severity-badge.severity-medium {
    color: #fde68a;
    background: rgba(234, 179, 8, 0.13);
    border-color: rgba(234, 179, 8, 0.55);
}
.severity-low .severity-badge,
.severity-badge.severity-low {
    color: #a5f3fc;
    background: rgba(6, 182, 212, 0.13);
    border-color: rgba(6, 182, 212, 0.55);
}
.severity-info .severity-badge,
.severity-badge.severity-info {
    color: #cbd5e1;
    background: rgba(100, 116, 139, 0.16);
    border-color: rgba(100, 116, 139, 0.55);
}

.finding-row-title {
    color: var(--sa-text);
    font-size: 13px;
    line-height: 19px;
    font-weight: 700;
}

.finding-row-path {
    color: var(--sa-muted);
    font: 500 11px/16px JetBrains Mono, monospace;
    margin-top: 3px;
}

.finding-detail {
    padding: 22px 22px 26px;
    background: transparent;
}

.finding-detail-meta {
    display: flex;
    gap: 8px;
    color: var(--sa-muted);
    font: 500 11px/16px JetBrains Mono, monospace;
    margin-bottom: 12px;
}

.finding-detail-title {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 22px;
}

.finding-detail-title h3 {
    margin: 0;
    color: var(--sa-text);
    font-size: 18px;
    line-height: 26px;
}

.detail-section {
    margin-bottom: 20px;
}

.detail-section span {
    display: block;
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.detail-section p {
    color: #dbeafe;
    font-size: 13px;
    line-height: 21px;
    margin: 0;
}

.detail-section pre,
.reference-card {
    border: 0;
    background: rgba(22, 34, 51, 0.48);
    border-radius: 7px;
}

.detail-section pre {
    color: #f1f5f9;
    white-space: pre-wrap;
    font: 500 12px/20px JetBrains Mono, monospace;
    padding: 14px;
    box-shadow: inset 0 1px 0 rgba(230, 240, 255, 0.03);
}

.reference-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px;
    color: var(--sa-muted);
    transition: border-color 150ms ease, background 150ms ease;
}

.reference-card:hover {
    background: rgba(27, 41, 58, 0.9);
    border-color: rgba(96, 165, 250, 0.34);
}

.reference-card code {
    color: #dce4ee;
    font: 600 12px/18px JetBrains Mono, monospace;
}

.reference-card a {
    color: var(--sa-text) !important;
    text-decoration: none !important;
    font: 700 12px/18px Inter, system-ui, sans-serif;
}

.audit-empty {
    padding: 72px 24px;
    text-align: center;
    color: var(--sa-muted);
}

.audit-empty h3 {
    color: var(--sa-text);
    margin: 0 0 8px;
}

@media (max-width: 900px) {
    .swarm-summary-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .audit-console-body {
        grid-template-columns: 1fr;
    }
    .finding-list {
        border-right: 0;
    }
    .report-overview {
        grid-template-columns: 1fr 1fr;
    }
}
"""


def render_workspace_header() -> str:
    return """
    <section class="swarm-topbar">
        <div class="swarm-brand-row">
            <div>
                <div class="swarm-brand">SwarmAudit</div>
                <div class="swarm-tagline">AI-generated code production-readiness scanner</div>
            </div>
            <div class="swarm-status">mock-first / vLLM-ready</div>
        </div>
        <div class="swarm-progressbar"><span></span></div>
    </section>
    """


def render_agent_swarm(progress: list[str] | None = None) -> str:
    progress = progress or []
    done_count = sum(1 for _, _, token, done_token in AGENT_SWARM if _agent_status(progress, token, done_token) == "done")
    items = "\n".join(
        f"""
        <div class="agent-item {status}">
            <div class="agent-icon">{name[:2].upper()}</div>
            <div>
                <div class="agent-name">{name}</div>
                <div class="agent-desc">{desc}</div>
            </div>
            <div class="agent-status {status}">{status}</div>
        </div>
        """
        for name, desc, token, done_token in AGENT_SWARM
        for status in [_agent_status(progress, token, done_token)]
    )
    return f"""
    <section class="agent-card">
        <div class="agent-card-header">
            <div class="agent-card-title">Agent swarm</div>
            <div class="agent-card-count">{done_count}/{len(AGENT_SWARM)} done</div>
        </div>
        <div class="agent-list">{items}</div>
    </section>
    """


def _agent_status(progress: list[str], token: str, done_token: str) -> str:
    matching_events = [event for event in progress if token in event]
    if any(done_token in event for event in matching_events):
        return "done"
    if matching_events:
        return "running"
    return "idle"


def render_empty_summary() -> str:
    return render_summary_cards(
        files_scanned="-",
        total_findings="-",
        severity_counts={},
    )


def render_report_summary(report: AuditReport) -> str:
    return render_summary_cards(
        files_scanned=str(report.scanned_file_count),
        total_findings=str(report.total_findings_count),
        severity_counts={
            Severity.critical: report.severity_summary.get(Severity.critical, 0),
            Severity.high: report.severity_summary.get(Severity.high, 0),
            Severity.medium: report.severity_summary.get(Severity.medium, 0),
            Severity.low: report.severity_summary.get(Severity.low, 0),
        },
    )


def render_report_toolbar(report: AuditReport | None) -> str:
    return f"""
    <section class="report-toolbar">
        <div>
            <div class="report-title"><span>DOC</span>Audit report</div>
            <div class="report-subnote">Visible rows prioritize important findings; downloads keep full report data.</div>
        </div>
    </section>
    """


def build_severity_filter_choices(report: AuditReport | None) -> list[str]:
    if report is None:
        return ["All 0"]

    displayed_counts = {severity: 0 for severity in Severity}
    for finding in report.findings:
        displayed_counts[finding.severity] += 1

    choices = [f"All {len(report.findings)}"]
    for severity, label in [
        (Severity.critical, "Critical"),
        (Severity.high, "High"),
        (Severity.medium, "Medium"),
        (Severity.low, "Low"),
    ]:
        count = displayed_counts.get(severity, 0)
        if count > 0:
            choices.append(f"{label} {count}")
    return choices


def render_summary_cards(
    files_scanned: str,
    total_findings: str,
    severity_counts: dict[Severity, int],
) -> str:
    severity_cards = []
    for severity, css_class in [
        (Severity.critical, "metric-critical"),
        (Severity.high, "metric-high"),
        (Severity.medium, "metric-medium"),
        (Severity.low, "metric-low"),
    ]:
        count = severity_counts.get(severity, 0)
        if count <= 0:
            continue
        severity_cards.append(
            f'<div class="swarm-metric {css_class}"><span>{severity.value.title()}</span><strong>{count}</strong></div>'
        )

    severity_html = "\n".join(severity_cards)
    return f"""
    <section class="swarm-summary-grid">
        <div class="swarm-metric"><span>Files scanned</span><strong>{files_scanned}</strong></div>
        <div class="swarm-metric"><span>Findings</span><strong>{total_findings}</strong></div>
        {severity_html}
    </section>
    """


async def analyze_repo(repo_url: str):
    if not repo_url.strip():
        yield (
            "Paste a public GitHub repository URL to start.",
            render_agent_swarm(),
            render_empty_summary(),
            render_report_toolbar(None),
            gr.update(choices=["All 0"], value="All 0"),
            format_report_overview_html(None),
            gr.update(choices=[], value=None),
            format_empty_finding_detail_html(),
            None,
            None,
            None,
        )
        return

    progress: list[str] = []
    agent_html = render_agent_swarm(progress)
    summary_html = render_empty_summary()
    report_toolbar_html = render_report_toolbar(None)
    severity_filter_update = gr.update(choices=["All 0"], value="All 0")
    report_overview_html = format_report_overview_html(None)
    finding_choice_update = gr.update(choices=[], value=None)
    finding_detail_html = format_empty_finding_detail_html()
    markdown_export = None
    json_export = None
    report_state = None
    try:
        async for event in AuditGraph().run_with_progress(repo_url.strip()):
            if isinstance(event, AuditReport):
                report_state = event
                filter_choices = build_severity_filter_choices(event)
                selected_filter = filter_choices[0]
                severity_filter_update = gr.update(choices=filter_choices, value=selected_filter)
                finding_choices = build_finding_choices(event, selected_filter)
                finding_choice_update = gr.update(
                    choices=finding_choices,
                    value=finding_choices[0] if finding_choices else None,
                )
                finding_detail_html = format_finding_detail_html(event, 0)
                summary_html = render_report_summary(event)
                report_toolbar_html = render_report_toolbar(event)
                report_overview_html = format_report_overview_html(event)
                markdown_export, json_export = write_report_exports(event)
            else:
                progress.append(event)
                agent_html = render_agent_swarm(progress)
            yield (
                "\n".join(progress),
                agent_html,
                summary_html,
                report_toolbar_html,
                severity_filter_update,
                report_overview_html,
                finding_choice_update,
                finding_detail_html,
                markdown_export,
                json_export,
                report_state,
            )
    except Exception as exc:
        progress.append(f"Audit failed: {exc}")
        yield (
            "\n".join(progress),
            render_agent_swarm(progress),
            render_empty_summary(),
            render_report_toolbar(None),
            gr.update(choices=["All 0"], value="All 0"),
            format_report_overview_html(None),
            gr.update(choices=[], value=None),
            format_empty_finding_detail_html(),
            None,
            None,
            None,
        )


def build_finding_rows(report: AuditReport | None) -> list[list[str]]:
    if report is None:
        return []

    rows: list[list[str]] = []
    for index, finding in enumerate(report.findings, start=1):
        rows.append(
            [
                f"F-{index:03d}",
                finding.severity.value,
                finding.title,
                f"{finding.file_path}:{finding.line_start}",
                finding.agent_source,
            ]
        )
    return rows


def _severity_from_filter(filter_label: str | None) -> Severity | None:
    if not filter_label:
        return None
    normalized = filter_label.lower()
    for severity in Severity:
        if normalized.startswith(severity.value.lower()):
            return severity
    return None


def _severity_marker(severity: Severity) -> str:
    return {
        Severity.critical: "CRIT",
        Severity.high: "HIGH",
        Severity.medium: "MED",
        Severity.low: "LOW",
    }.get(severity, "INFO")


def build_finding_choices(report: AuditReport | None, severity_filter: str | None = None) -> list[str]:
    if report is None:
        return []

    selected_severity = _severity_from_filter(severity_filter)
    choices: list[str] = []
    for index, finding in enumerate(report.findings, start=1):
        if selected_severity is not None and finding.severity != selected_severity:
            continue
        marker = _severity_marker(finding.severity)
        choices.append(
            f"{marker:<4}  {finding.title}\n"
            f"{finding.file_path}:{finding.line_start}  |  {finding.agent_source}"
        )
    return choices


def filter_findings(severity_filter: str | None, report: AuditReport | None):
    choices = build_finding_choices(report, severity_filter)
    selected = choices[0] if choices else None
    detail_html = select_finding(selected, report) if selected else format_empty_finding_detail_html()
    return gr.update(choices=choices, value=selected), detail_html


def select_finding(choice: str | None, report: AuditReport | None) -> str:
    if report is None or not report.findings:
        return format_empty_finding_detail_html()

    row_index = 0
    if choice:
        choices = build_finding_choices(report)
        if choice in choices:
            row_index = choices.index(choice)

    return format_finding_detail_html(report, row_index)


def choose_example(example_name: str) -> str:
    return EXAMPLE_REPOS.get(example_name, "")


async def run_llm_diagnostics() -> str:
    health = await LLMClient(get_settings()).health_check()
    lines = [
        "# LLM Diagnostics",
        "",
        f"- Provider: `{health.provider}`",
        f"- Model: `{health.model}`",
        f"- Base URL: `{health.base_url}`",
        f"- Status: `{'OK' if health.ok else 'FAILED'}`",
    ]

    if health.latency_ms is not None:
        lines.append(f"- Latency: `{health.latency_ms} ms`")
    if health.models:
        lines.extend(["", "## Models", ""])
        lines.extend(f"- `{model}`" for model in health.models)
    if health.completion_preview:
        lines.extend(["", "## Completion Preview", "", health.completion_preview])
    if health.error:
        lines.extend(["", "## Error", "", f"```text\n{health.error}\n```"])

    return "\n".join(lines)


async def run_benchmark() -> str:
    result = await BenchmarkService(get_settings()).run_llm_benchmark()
    lines = [
        "# LLM Benchmark",
        "",
        f"- Provider: `{result.provider}`",
        f"- Backend: `{result.backend}`",
        f"- Model: `{result.model}`",
        f"- Hardware: `{result.hardware}`",
        f"- Status: `{'OK' if result.ok else 'FAILED'}`",
        f"- Prompt chars: `{result.prompt_chars}`",
        f"- Completion chars: `{result.completion_chars}`",
    ]

    if result.latency_ms is not None:
        lines.append(f"- Latency: `{result.latency_ms} ms`")
    if result.chars_per_second is not None:
        lines.append(f"- Approx chars/sec: `{result.chars_per_second}`")
    if result.completion_preview:
        lines.extend(["", "## Completion Preview", "", result.completion_preview])
    if result.error:
        lines.extend(["", "## Error", "", f"```text\n{result.error}\n```"])

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "This scaffold uses character counts until a real vLLM endpoint exposes token usage. "
            "When running on AMD MI300X, record latency/tokens-per-second here for the final demo.",
        ]
    )
    return "\n".join(lines)


def build_app() -> gr.Blocks:
    theme = gr.themes.Base(
        primary_hue="blue",
        secondary_hue="cyan",
        neutral_hue="slate",
        font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
        font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "monospace"],
    )

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The parameters have been moved from the Blocks constructor to the launch.*",
            category=UserWarning,
        )
        with gr.Blocks(title="SwarmAudit", theme=theme, css=APP_CSS, elem_id="swarm-shell") as demo:
            gr.HTML(render_workspace_header())

            with gr.Tab("Audit"):
                with gr.Group(elem_classes=["audit-actionbar"]):
                    with gr.Row(equal_height=False):
                        repo_url = gr.Textbox(
                            label="",
                            placeholder="repo  https://github.com/owner/repo",
                            scale=8,
                            min_width=420,
                            show_label=False,
                            elem_classes=["repo-input"],
                        )
                        analyze = gr.Button("Analyze", variant="primary", scale=0, min_width=112)
                        gr.HTML('<div class="example-label">Examples</div>', scale=0)
                        for example_name, example_url in EXAMPLE_REPOS.items():
                            example_button = gr.Button(
                                example_name,
                                scale=0,
                                min_width=124,
                                elem_classes=["example-chip"],
                            )
                            example_button.click(lambda url=example_url: url, outputs=repo_url)

                summary_output = gr.HTML(render_empty_summary())
                report_state = gr.State(None)

                with gr.Row():
                    with gr.Column(scale=1):
                        agent_output = gr.HTML(render_agent_swarm())
                        progress_output = gr.Textbox(
                            label="Activity log",
                            lines=12,
                            interactive=False,
                            elem_classes=["swarm-panel", "swarm-progress"],
                        )
                    with gr.Column(scale=3):
                        with gr.Row(elem_classes=["report-header-row"]):
                            report_toolbar = gr.HTML(render_report_toolbar(None), scale=1)
                            severity_filter = gr.Radio(
                                choices=["All 0"],
                                value="All 0",
                                interactive=True,
                                show_label=False,
                                scale=0,
                                min_width=360,
                                elem_classes=["severity-filter-radio"],
                            )
                            markdown_export = gr.DownloadButton(
                                "Markdown",
                                value=None,
                                size="sm",
                                scale=0,
                                min_width=96,
                                elem_classes=["report-download"],
                            )
                            json_export = gr.DownloadButton(
                                "JSON",
                                value=None,
                                size="sm",
                                scale=0,
                                min_width=76,
                                elem_classes=["report-download"],
                            )
                        report_overview = gr.HTML(format_report_overview_html(None))
                        with gr.Row(equal_height=True, elem_classes=["report-body"]):
                            with gr.Column(scale=1):
                                finding_selector = gr.Radio(
                                    choices=[],
                                    value=None,
                                    interactive=True,
                                    show_label=False,
                                    elem_classes=["findings-list-radio"],
                                )
                            with gr.Column(scale=1):
                                finding_detail = gr.HTML(
                                    format_empty_finding_detail_html(),
                                    elem_classes=["swarm-panel", "swarm-report"],
                                )

                analyze.click(
                    analyze_repo,
                    inputs=repo_url,
                    outputs=[
                        progress_output,
                        agent_output,
                        summary_output,
                        report_toolbar,
                        severity_filter,
                        report_overview,
                        finding_selector,
                        finding_detail,
                        markdown_export,
                        json_export,
                        report_state,
                    ],
                )
                severity_filter.change(
                    filter_findings,
                    inputs=[severity_filter, report_state],
                    outputs=[finding_selector, finding_detail],
                )
                finding_selector.change(select_finding, inputs=[finding_selector, report_state], outputs=finding_detail)

            with gr.Tab("Diagnostics"):
                gr.Markdown(
                    "Verify the configured LLM backend before switching from mock mode to AMD/vLLM enrichment.",
                    elem_classes=["swarm-note"],
                )
                diagnostics_button = gr.Button("Test LLM Connection", variant="primary")
                diagnostics_output = gr.Markdown(elem_classes=["swarm-panel"])
                diagnostics_button.click(run_llm_diagnostics, outputs=diagnostics_output)

            with gr.Tab("Benchmark"):
                gr.Markdown(
                    "Run a small timing probe. Mock mode validates the UI path; vLLM mode records MI300X demo numbers.",
                    elem_classes=["swarm-note"],
                )
                benchmark_button = gr.Button("Run Benchmark", variant="primary")
                benchmark_output = gr.Markdown(elem_classes=["swarm-panel"])
                benchmark_button.click(run_benchmark, outputs=benchmark_output)
    return demo


def launch_app() -> None:
    server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
    configured_port = os.getenv("PORT") or os.getenv("GRADIO_SERVER_PORT")
    server_port = int(configured_port or "7860")
    try:
        build_app().queue().launch(server_name=server_name, server_port=server_port)
    except OSError:
        if configured_port:
            raise
        build_app().queue().launch(server_name=server_name, server_port=None)


if __name__ == "__main__":
    launch_app()
