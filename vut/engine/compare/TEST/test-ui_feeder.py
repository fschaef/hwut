
#! /usr/bin/env python
import io
import sys
import os

# Adjust path to find vut
sys.path.insert(0, "../../../../")

from vut.engine.compare.ui_feeder import (
    ui_feeder, 
    ConfigInst, 
    ProtocolHeader,
    SectionBeginInst, 
    LinePairInst, 
    EndOfStreamInst
)
from vut.engine.compare.configuration import Configuration

if "--hwut-info" in sys.argv:
    print("Testing the ui-feeder producing HTML code using Polymorphic Instructions.")
    sys.exit()

# --- 1. Wisdom vs. Distortion (Data remains same) ---
nominal = """
There once was a ((Object)) made of ((Material)),
Who pondered the things that it said.
"Even the largest fahrt," it began with a roar,
"Starts with 1.0 gas atom leaving the door."
Then it dissolved into raindrops of bread.

A ((Persona)) in a ((Location)) maze,
Observed the electric 0.5 blue haze.
"I think, therefore I am... not quite sure,"
He whispered while scrubbing the floor of the pure,
"For a bug in the code ends 100.0 days."

||||
The ((Animal)) in the desert was dry,
With a telescope aimed at the sky.
"That which does not kill us makes us 42.0 percent strange,"
((Object)) noted while rearranging the range,
Then ate a gold watch and started to fly.
||||

||||
A ((Object)) sat down on a chair,
To contemplate why it was there.
"To be, or not to be... a small grape,"
It sighed as it shifted its 3.14159 geological shape,
"Is a question that leaves me quite bare."
||||

A ((hole in the wall)) looked out at its arse,
And watched the transparent 10.0 years pass.
"The unexamined life is a pane in the neck,"
It muttered while counting a solitary speck,
Then turned into liquid and sat on the grass.
"""

subject = """
There once was a ((mouse)) made of ((Glass)),
Who pondered the things that it said.
"Even the largest fahrt," it began with a roar,
"Starts with 1.05 gas atom leaving the door."
Then it dissolved into raindrops of bread.

A ((Monk)) in a ((Monastery)) maze,
Observed the electric 0.51 blue haze.
"I think, therefore I am... not quite sure,"
"For a bug in the code ends 102.0 days."

||||
"That which does not kill us makes us 42.1 percent strange,"
The ((Animal)) in the desert was dry,
With a telescope aimed at the sky.
A ((mouse)) noted while rearranging the range,
Then ate a gold watch and started to fly.
||||

||||
A ((Object)) sat down on a chair,
To contemplate why it was there.
"To be, or not to be... a small grape,"
"Is a question that leaves me quite bare."
It sighed as it shifted its 3.14 geological shape,
||||

A ((Window)) looked out at its glas,
"The unexamined life is a pane in the heck,"
It muttered pendant que counting a solitary speck,
Then turned into butter and sat on the grass.
"""

async def generate_html():
    config = Configuration()
    s_stream = io.StringIO(subject)
    n_stream = io.StringIO(nominal)

    EXPECTED_SIGNATURE = '6AE8E2F3'

    HTML_HEAD = """
    <html><head><style>
        :root {
            --bg: #0d1117;        --text: #c9d1d9;
            --ln-bg: #010409;     --ln-color: #484f58;
            --border: #30363d;
            --err-bg: rgba(248, 81, 73, 0.15);  --err-border: #f85149;
            --tol-bg: rgba(210, 153, 34, 0.15); --tol-border: #d29922;
            --dimmed: #484f58;
        }
        body { 
            background: var(--bg); color: var(--text); 
            font-family: 'SFMono-Regular', Consolas, monospace; font-size: 12px; margin: 0; padding: 20px; 
        }
        .console { border: 1px solid var(--border); border-radius: 6px; overflow: hidden; background: var(--bg); }
        .config-bar { background: var(--ln-bg); padding: 4px 10px; border-bottom: 1px solid var(--border); color: #8b949e; font-size: 11px; }
        .header { background: #1f242c; padding: 4px 10px; border-bottom: 1px solid var(--border); color: #58a6ff; font-weight: bold; }
        .row { display: grid; grid-template-columns: 40px minmax(0, 1fr) 40px minmax(0, 1fr); border-bottom: 1px solid #21262d; position: relative; }
        .ln { background: var(--ln-bg); color: var(--ln-color); text-align: right; padding: 2px 8px; border-right: 1px solid var(--border); }
        .side { padding: 2px 6px; white-space: pre; display: flex; flex-wrap: wrap; }
        .token { padding: 0 2px; border-radius: 2px; margin: 0 1px; border: 1px solid transparent; }
        .BAD_SUBJECT_DIFFERS { background: var(--err-bg); border-color: var(--err-border); color: #ff7b72; }
        .BAD_SUBJECT_HAS     { background: var(--err-bg); border-color: var(--err-border); color: #ff7b72; }
        .OK_TOLERATED        { background: var(--tol-bg); border-color: var(--tol-border); color: #e3b341; }
        .BAD_SUBJECT_HAS_NOT { color: #3fb950; font-weight: bold; }
        .dimmed { color: var(--dimmed) !important; }
        .OK_GOOD { color: var(--text); }
        .heatmap-marker { position: absolute; left: 0; top: 0; bottom: 0; width: 3px; }
    </style></head><body><div class="console">
    """

    output = [HTML_HEAD]

    async for inst in ui_feeder(config, s_stream, n_stream):
        match inst:
            case ProtocolHeader(signature=sig, engine_id=eid):
                if sig != EXPECTED_SIGNATURE:
                    print(f"CRITICAL ERROR: Protocol Mismatch!", file=sys.stderr)
                    print(f"Receiver expects: {EXPECTED_SIGNATURE}", file=sys.stderr)
                    print(f"Engine provided:  {sig} ({eid})", file=sys.stderr)
                    sys.exit(1)
                # Success: Protocol is verified.
                
            case ConfigInst() as c:
                output.append(f"<div class='config-bar'>TOLERANCE: {c.numeric_tolerance_ratio}</div>")
                
            case SectionBeginInst(title=t):
                output.append(f"<div class='header'>:: {t}</div>")
            
            case LinePairInst() as lp:
                has_error = any(not c.relation_id.name.startswith("OK_") for c in lp.cells_s)
                alpha = min(0.3, lp.cost * 0.4)
                row_style = f"style='background: rgba(248, 81, 73, {alpha});'" if lp.cost > 0 else ""
                
                output.append(f"<div class='row' {row_style}>")
                
                # --- Subject ---
                output.append(f"<div class='ln'>{lp.line_n_s if lp.line_n_s != -1 else '-'}</div><div class='side'>")
                if lp.cost > 0:
                    output.append(f"<div class='heatmap-marker' style='background: var(--err-border); opacity: {lp.cost};'></div>")
                
                for cell in lp.cells_s:
                    content = (cell.subject or "").replace(" ", "&middot;")
                    output.append(f"<span class='token {cell.relation_id.name}'>{content}</span>")
                output.append("</div>")

                # --- Nominal ---
                output.append(f"<div class='ln'>{lp.line_n_n if lp.line_n_n != -1 else '-'}</div><div class='side'>")
                dim_class = "dimmed" if has_error else ""
                for cell in lp.cells_n:
                    content = (cell.nominal or "").replace(" ", "&middot;")
                    output.append(f"<span class='token {cell.relation_id.name} {dim_class}'>{content}</span>")
                output.append("</div></div>")

            case EndOfStreamInst():
                break

    output.append("</div></body></html>")
    print("\n".join(output))

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_html())
