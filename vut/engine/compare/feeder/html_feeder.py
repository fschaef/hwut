#!/usr/bin/env python
"""
VUT HTML Report Generator.
Features: 
- Potpourri "Tangle" Visualization with Bezier Curves.
- Semantic "Truth vs. Attempt" Styling.
- HOCON-style configuration loading.
"""
import sys
import os
import html
import importlib.util
from typing import Dict, Any

# --- IMPORTS (Adjust path as necessary) ---
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../../")

from vut.engine.compare.configuration      import Configuration
from vut.engine.compare.reading.line_element import E_ToleranceId
from vut.engine.compare.feeder.ui          import (feed,
                                                   SectionBeginInst,
                                                   LinePairInst,
                                                   EndOfStreamInst)

# ==============================================================================
#  1. DEFAULT CONFIGURATION (HOCON-like structure)
# ==============================================================================

DEFAULT_CONFIG = {
    "options": {
        "show_nominal_gap": True, # Show empty space on nominal side if subject inserts text
        "line_height_px": 24,     # Fixed height for SVG alignment
        "gutter_width_px": 40,
        "region_begin_marker": "##!",
        "region_end_marker": "####"
    },
    "labels": {
        "OK_GOOD":                    "Perfect Match",
        "OK_TOLERATED":               "Tolerated Difference",
        "OK_VISIBLE_NOTHING":         "Ignored Whitespace",
        "BAD_SUBJECT_DIFFERS":        "Content Mismatch",
        "BAD_SUBJECT_HAS_NOT":        "Missing in Subject",
        "BAD_SUBJECT_HAS":            "Unexpected Insertion",
        "BAD_TRANSPOSE":              "Out of Order",
        "BAD_SUBJECT_TYPE_DIFFERS":   "Type Mismatch (e.g. Number vs String)"
    },
    "styles": {
        "base": {
            "bg": "#0d1117", "fg": "#c9d1d9", "gutter": "#161b22", 
            "border": "#30363d", "font": "'SFMono-Regular', Consolas, monospace"
        },
        # Relations
        "OK_GOOD":              {"color": "inherit"},
        "OK_TOLERATED":         {"color": "#e3b341", "decoration": "underline dotted #d29922", "style": "italic"},
        "VISIBLE_NOTHING":      {"color": "#484f58"},
        
        # Errors (Subject Side = Blame / Red)
        "BAD_SUBJECT_DIFFERS":  {"bg": "rgba(248, 81, 73, 0.15)", "color": "#ff7b72", "border": "1px solid #8e1519"},
        "BAD_SUBJECT_HAS":      {"bg": "rgba(248, 81, 73, 0.15)", "color": "#ff7b72", "decoration": "line-through"},
        "BAD_SUBJECT_HAS_NOT":  {"border": "1px dashed #484f58", "color": "#484f58"}, # The gap style
        
        # Errors (Nominal Side = Truth / Blue-Cyan)
        "BAD_NOMINAL_DIFFERS":  {"bg": "rgba(56, 139, 253, 0.1)", "color": "#58a6ff", "border": "1px solid #1f6feb"},
        "BAD_NOMINAL_HAS":      {"bg": "rgba(56, 139, 253, 0.1)", "color": "#58a6ff", "weight": "bold"},
        
        # Structural
        "BAD_TRANSPOSE":        {"bg": "rgba(163, 113, 247, 0.1)", "color": "#d2a8ff", "border": "1px solid #8957e5"},
        
        # Bezier Curves
        "connector_ok":         "#3fb950", # Green
        "connector_bad":        "#f85149", # Red
        "connector_dim":        "#30363d"  # Dim gray
    }
}

# ==============================================================================
#  2. HTML GENERATOR
# ==============================================================================

class HtmlReportGenerator:
    HEAD_TPL = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
    <title>VUT Report</title><style>
        :root {{
            --lh: {lh}px; 
            --gw: {gw}px;
            --bg: {s[base][bg]}; --fg: {s[base][fg]};
            --border: {s[base][border]}; --gutter: {s[base][gutter]};
        }}
        body {{ background: var(--bg); color: var(--fg); font-family: {s[base][font]}; margin: 0; padding: 20px; font-size: 13px; }}
        .container {{ border: 1px solid var(--border); border-radius: 6px; background: var(--bg); overflow: hidden; }}
        .scroll-wrap {{ overflow-x: auto; }}
        
        /* Layout Grid */
        .row {{ display: grid; grid-template-columns: var(--gw) 1fr 20px var(--gw) 1fr; border-bottom: 1px solid #21262d; height: var(--lh); }}
        .row:hover {{ background: rgba(255,255,255,0.03); }}
        
        /* Columns */
        .ln {{ background: var(--gutter); color: #6e7681; text-align: right; padding-right: 8px; line-height: var(--lh); font-size: 11px; user-select: none; border-right: 1px solid var(--border); }}
        .side {{ padding: 0 8px; white-space: pre; line-height: var(--lh); overflow: hidden; }}
        .mid {{ background: var(--gutter); border-left: 1px solid var(--border); border-right: 1px solid var(--border); }}
        
        /* Potpourri */
        .potpourri-frame {{ border: 1px solid #30363d; margin: 10px 0; background: #0d1117; position: relative; }}
        .potpourri-marker {{ background: #161b22; color: #8b949e; text-align: center; font-size: 10px; letter-spacing: 2px; padding: 2px; border-bottom: 1px solid var(--border); font-weight: bold; }}
        .tangle-grid {{ display: grid; grid-template-columns: var(--gw) minmax(200px, 1fr) 60px var(--gw) minmax(200px, 1fr); position: relative; }}
        .svg-col {{ position: relative; overflow: visible; }}
        svg.connectors {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }}
        path.curve {{ fill: none; stroke-width: 1.5; opacity: 0.6; transition: stroke-width 0.2s, opacity 0.2s; }}
        path.curve:hover {{ stroke-width: 3; opacity: 1.0; z-index: 99; }}

        /* Tokens */
        .tok {{ display: inline-block; padding: 0 2px; border-radius: 2px; border: 1px solid transparent; cursor: help; }}
        
        /* Generated Styles */
        {dynamic_css}
    </style></head><body><div class="container"><div class="scroll-wrap">
    """

    def __init__(self, stream, out_fh, config_dict=None):
        self.stream = stream
        self.out = out_fh
        self.cfg = config_dict or DEFAULT_CONFIG
        self.styles = self.cfg['styles']
        self.opts = self.cfg['options']
        self.labels = self.cfg['labels']
        
        # Buffering for Potpourri
        self.in_potpourri = False
        self.potpourri_buffer = []

    async def do(self):
        self._write_header()
        
        async for inst in self.stream:
            # 1. Detect Potpourri Transition based on Markers inside ConfigInst? 
            # Actually, VUT engine usually sends SectionBeginInst. 
            # But the prompt says "framed by lines containing marker". 
            # We will use the SectionBeginInst as the trigger.
            
            if isinstance(inst, SectionBeginInst):
                self._flush_potpourri() # Close previous if open
                if "Potpourri" in inst.chunk_type:
                    self.in_potpourri = True
                    self._print(f'<div class="potpourri-frame"><div class="potpourri-marker">{self.opts["region_begin_marker"]} REGION START</div>')
                else:
                    self.in_potpourri = False
                    # Standard header for Line Sequence
                    self._print(f'<div class="row" style="background:var(--gutter); color:#58a6ff; font-weight:bold; height:auto; padding:4px;"><div style="grid-column:1/-1">:: {inst.title}</div></div>')

            elif isinstance(inst, LinePairInst):
                if self.in_potpourri:
                    self.potpourri_buffer.append(inst)
                else:
                    self._render_standard_row(inst)
            
            elif isinstance(inst, EndOfStreamInst):
                self._flush_potpourri()
                break
                
        self._print("</div></div></body></html>")

    def _write_header(self):
        # Generate CSS classes from dict
        css = []
        for k, v in self.styles.items():
            if k in ['base', 'connector_ok', 'connector_bad', 'connector_dim']: continue
            props = []
            if 'color' in v: props.append(f"color: {v['color']}")
            if 'bg' in v: props.append(f"background-color: {v['bg']}")
            if 'border' in v: props.append(f"border: {v['border']}")
            if 'decoration' in v: props.append(f"text-decoration: {v['decoration']}")
            if 'style' in v: props.append(f"font-style: {v['style']}")
            if 'weight' in v: props.append(f"font-weight: {v['weight']}")
            css.append(f".{k} {{ {'; '.join(props)}; }}")
        
        html_head = self.HEAD_TPL.format(
            lh=self.opts['line_height_px'],
            gw=self.opts['gutter_width_px'],
            s=self.styles,
            dynamic_css="\n".join(css)
        )
        self._print(html_head)

    def _render_standard_row(self, inst: LinePairInst):
        """Renders standard sequential lines."""
        ls = str(inst.line_n_s) if inst.line_n_s != -1 else ""
        ln = str(inst.line_n_n) if inst.line_n_n != -1 else ""
        
        self._print('<div class="row">')
        self._print(f'<div class="ln">{ls}</div>')
        self._print('<div class="side">', end='')
        for c in inst.cells_s: self._render_cell(c)
        self._print('</div>')
        self._print('<div class="mid"></div>')
        self._print(f'<div class="ln">{ln}</div>')
        self._print('<div class="side">', end='')
        for c in inst.cells_n: self._render_cell(c)
        self._print('</div></div>')

    def _flush_potpourri(self):
        if not self.potpourri_buffer:
            if self.in_potpourri: 
                self._print(f'<div class="potpourri-marker">{self.opts["region_end_marker"]} END</div></div>')
            return

        # 1. Sort visuals independently
        # Subject lines: Sort by Line Number (skip missing)
        s_rows = sorted([x for x in self.potpourri_buffer if x.line_n_s != -1], key=lambda x: x.line_n_s)
        # Nominal lines: Sort by Line Number (skip missing)
        n_rows = sorted([x for x in self.potpourri_buffer if x.line_n_n != -1], key=lambda x: x.line_n_n)
        
        # 2. Map coordinates
        s_map = {inst.line_n_s: i for i, inst in enumerate(s_rows)}
        n_map = {inst.line_n_n: i for i, inst in enumerate(n_rows)}
        
        height_px = max(len(s_rows), len(n_rows)) * self.opts['line_height_px']
        
        self._print('<div class="tangle-grid">')
        
        # COL 1: Subject Lines
        self._print('<div class="col-grp">')
        for inst in s_rows:
            self._print('<div class="row" style="display:flex; border-bottom:none;">')
            self._print(f'<div class="ln" style="width:{self.opts["gutter_width_px"]}px; flex-shrink:0">{inst.line_n_s}</div>')
            self._print('<div class="side" style="flex-grow:1">', end='')
            for c in inst.cells_s: self._render_cell(c)
            self._print('</div></div>')
        self._print('</div>') # End Subj Col

        # COL 2: SVG Connectors
        self._print(f'<div class="svg-col"><svg class="connectors" style="height:{height_px}px" viewBox="0 0 100 {height_px}" preserveAspectRatio="none">')
        lh = self.opts['line_height_px']
        half_lh = lh / 2
        
        for inst in self.potpourri_buffer:
            if inst.line_n_s != -1 and inst.line_n_n != -1:
                y1 = s_map[inst.line_n_s] * lh + half_lh
                y2 = n_map[inst.line_n_n] * lh + half_lh
                
                # Semantic Coloring for lines
                stroke = self.styles['connector_ok']
                if inst.cost > 0: stroke = self.styles['connector_bad']
                elif abs(y1 - y2) > lh: stroke = self.styles['connector_dim'] # Dim simple structural lines if tangled
                
                path = f'<path d="M 0 {y1} C 50 {y1}, 50 {y2}, 100 {y2}" class="curve" style="stroke:{stroke}" />'
                self._print(path)
        self._print('</svg></div>')

        # COL 3 & 4: Nominal Ln + Content
        self._print('<div class="col-grp" style="display:flex; flex-direction:column">') # Wrapper for Nominal side lines
        # Nominal line number column is tricky in this grid layout, we merge ln+content in one col-grp visually
        pass 
        # Re-think grid: The main grid handles the columns.
        
        # NOMINAL LN
        self._print('<div class="col-n-ln">')
        for inst in n_rows:
             self._print(f'<div class="ln" style="border-bottom:none">{inst.line_n_n}</div>')
        self._print('</div>')

        # NOMINAL CONTENT
        self._print('<div class="col-n-content">')
        for inst in n_rows:
            self._print('<div class="side">', end='')
            for c in inst.cells_n: self._render_cell(c)
            self._print('</div>')
        self._print('</div>')

        self._print('</div>') # End Tangle Grid
        self._print(f'<div class="potpourri-marker">{self.opts["region_end_marker"]} END</div></div>')
        
        self.potpourri_buffer = []

    def _render_cell(self, cell):
        content = getattr(cell, "subject", None) or getattr(cell, "nominal", None) or ""
        txt = html.escape(content).replace(" ", "&nbsp;")
        rid = cell.relation_id.name
        
        # Tooltip generation
        tip = f"{self.labels.get(rid, rid)}"
        
        # Provenance Logic
        if cell.tolerance_id == E_ToleranceId.ANALOGY and cell.analogy_origin_line_number_pair:
            lnp = cell.analogy_origin_line_number_pair
            is_conflict = "BAD" in rid
            if is_conflict:
                tip += f"\nConflict! Originally established at S:{lnp.line_n_in_subject} / N:{lnp.line_n_in_nominal}"
            else:
                tip += f"\nAnalogy established at S:{lnp.line_n_in_subject} / N:{lnp.line_n_in_nominal}"
        
        self._print(f'<span class="tok {rid}" title="{tip}">{txt}</span>', end='')

    def _print(self, *args, **kwargs):
        print(*args, file=self.out, **kwargs)

# ==============================================================================
#  3. ENTRY POINT & CONFIG LOADING
# ==============================================================================

def load_config(path: str) -> Dict[str, Any]:
    """Loads a Python file as a dict configuration."""
    cfg = DEFAULT_CONFIG.copy()
    if not path or not os.path.exists(path):
        return cfg
    
    try:
        spec = importlib.util.spec_from_file_location("user_cfg", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        
        # Recursive update (simple version)
        if hasattr(mod, 'options'): cfg['options'].update(mod.options)
        if hasattr(mod, 'styles'): cfg['styles'].update(mod.styles)
        if hasattr(mod, 'labels'): cfg['labels'].update(mod.labels)
    except Exception as e:
        sys.stderr.write(f"Config Load Error: {e}\n")
    return cfg

async def run(s_stream, n_stream, out_fh, config_obj: Configuration, config_file=None):
    user_cfg = load_config(config_file)
    feeder = feed(config_obj, s_stream, n_stream)
    gen = HtmlReportGenerator(feeder, out_fh, user_cfg)
    await gen.do()

