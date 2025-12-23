
#! /usr/bin/env python
import io
import sys
import os

# Adjust path to find vut
sys.path.insert(0, "../../../../")

from vut.engine.compare.ui_feeder import (
    ui_feeder, 
    ConfigInst, 
    SectionBeginInst, 
    LinePairInst, 
    EndOfStreamInst
)
from vut.engine.compare.configuration import Configuration

if "--hwut-info" in sys.argv:
    print("Testing the ui-feeder producing HTML code using Polymorphic Instructions.")
    sys.exit()

# --- 1. Wisdom vs. Distortion (Data remains same) ---
nominal = """((Author)) says time is like Gold
((It)) shines as the stories unfold
Walk slowly and see
The fruit on the tree
Lest wisdom should never take hold

((Author)) says silence is Best
((It)) gives the tired spirit some Rest
A word left unsaid
Is peace in the head
Put truth to the ultimate test

||||
((Author)) says focus is Key
To unlock the things you can be
Don't scatter your light
In the middle of night
Stay steady as 10 ships on the sea
||||
"""

subject = """((Socrates)) says time is like Lead
((Elfriede)) shines as the stories unfold
And see slowly
The fruit on the tree
Lest wisdom should never take hold

((Socrates)) says is silence Best
((Elfriede)) gives the tired spirit some Sleep
A word left unsaid
Put truth to the ultimate test

||||
To unlock the things you can pee
Don't scatter your light
Stay steady as 12 ships on the sea
((Heinz)) disagreed
((Socrates)) says focus is Lock
||||
"""

# --- 2. HTML Boilerplate with Heatmap Support ---
HTML_TEMPLATE = """
<html><head><style>
    body { font-family: 'Segoe UI', sans-serif; background: #121212; color: #e0e0e0; padding: 20px; }
    .container { max-width: 1200px; margin: auto; }
    .config-box { font-size: 0.8em; color: #888; border: 1px solid #333; padding: 10px; margin-bottom: 20px; border-radius: 4px; }
    .header { background: #1f1f1f; padding: 12px; border-radius: 8px 8px 0 0; margin-top: 20px; border-left: 5px solid #007acc; color: #007acc; font-weight: bold; }
    .row { display: flex; margin-bottom: 1px; background: #1e1e1e; overflow: hidden; transition: background 0.2s; }
    .row:hover { filter: brightness(1.2); }
    .line-no { width: 50px; background: rgba(0,0,0,0.2); color: #858585; text-align: center; padding: 6px 0; font-size: 0.8em; flex-shrink: 0; border-right: 1px solid #333; }
    .side { flex: 1; padding: 6px; display: flex; flex-wrap: wrap; align-content: flex-start; position: relative; }
    .token { margin: 0 2px; padding: 0 3px; border-radius: 2px; white-space: pre; }
    
    /* Semantic Highlighting */
    .OK_GOOD { color: #9cdcfe; }
    .OK_TOLERATED { color: #4ec9b0; border-bottom: 1px solid #4ec9b0; }
    .BAD_TRANSPOSE { color: #dcdcaa; background: #3e3e10; border: 1px dashed #dcdcaa; }
    .BAD_SUBJECT_DIFFERS { color: #f48771; background: #4b1818; text-decoration: underline wavy red; }
    .BAD_SUBJECT_HAS_NOT { background: #2d3e2d; color: #75beff; opacity: 0.8; } /* Inserted */
    .BAD_SUBJECT_HAS { background: #4b1818; color: #f48771; opacity: 0.8; }     /* Deleted */
</style></head><body><div class="container">
"""

async def generate_html():
    config = Configuration()
    s_stream = io.StringIO(subject)
    n_stream = io.StringIO(nominal)

    output = [HTML_TEMPLATE]

    # Pipe the streams through the ui_feeder (Instruction Streamer)
    async for inst in ui_feeder(config, s_stream, n_stream):
        
        match inst:
            case ConfigInst() as c:
                output.append(f"<div class='config-box'>Config: Markers={c.ignored_line_begin_marker} | Tolerance={c.numeric_tolerance_ratio}</div>")

            case SectionBeginInst(title=t, chunk_type=ct):
                output.append(f"<div class='header'>{t} <small style='color:#555'>({ct})</small></div>")
            
            case LinePairInst() as lp:
                # Use the 'cost' to generate a heatmap color (Red component grows with cost)
                # 0.0 cost = gray-ish background; 1.0 cost = reddish background
                bg_intensity = int(lp.cost * 60) # 0 to 60
                row_style = f"style='background: rgb({30 + bg_intensity}, 30, 30);'"
                
                output.append(f"<div class='row' {row_style}>")
                
                # --- Subject Side ---
                output.append(f"<div class='line-no'>{lp.line_n_s}</div><div class='side'>")
                for cell in lp.cells_s:
                    output.append(f"<span class='token {cell.relation_id.name}' title='Cost: {lp.cost}'>{cell.subject or ''}</span>")
                output.append("</div>")

                # --- Nominal Side ---
                output.append(f"<div class='line-no'>{lp.line_n_n}</div><div class='side'>")
                for cell in lp.cells_n:
                    output.append(f"<span class='token {cell.relation_id.name}'>{cell.nominal or ''}</span>")
                output.append("</div></div>")

            case EndOfStreamInst():
                output.append("<div style='text-align:center; padding: 20px; color: #444;'>--- End of Comparison ---</div>")

    output.append("</div></body></html>")
    print("\n".join(output))

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_html())
