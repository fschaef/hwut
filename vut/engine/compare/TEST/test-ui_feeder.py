#! /usr/bin/env python
import io
import sys

sys.path.insert(0, "../../../../")

import os
from vut.engine.compare.ui_feeder import ui_feeder, E_DisplayCmd
from vut.engine.compare.configuration import Configuration

if "--hwut-info" in sys.argv:
    print("Testing the ui-feeder producing HTML code.")
    sys.exit()

# --- 1. Wisdom vs. Distortion ---
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

# Distortions: 
# 1. Gold -> Lead (Substitution), "slowly" moved (Transposition)
# 2. Rest -> Sleep (Substitution), "silence" moved
# 3. "Key" -> "Lock" (Substitution), analogy ((Author)) renamed
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

# --- 2. HTML Boilerplate ---
HTML_TEMPLATE = """
<html><head><style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #121212; color: #e0e0e0; padding: 20px; }
    .container { max-width: 1000px; margin: auto; }
    .header { background: #1f1f1f; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid #007acc; color: #007acc; }
    .row { display: flex; margin-bottom: 2px; background: #1e1e1e; border-radius: 4px; overflow: hidden; }
    .line-no { width: 40px; background: #252526; color: #858585; text-align: center; padding: 8px 0; font-size: 0.8em; flex-shrink: 0; }
    .side { flex: 1; padding: 8px; display: flex; flex-wrap: wrap; align-content: flex-start; border-right: 1px solid #333; }
    .token { margin: 0 2px; padding: 0 3px; border-radius: 2px; }
    
    /* Semantic Highlighting */
    .OK_GOOD { color: #9cdcfe; }
    .OK_TOLERATED { color: #4ec9b0; border-bottom: 1px solid #4ec9b0; }
    .BAD_TRANSPOSE { color: #dcdcaa; background: #3e3e10; border: 1px dashed #dcdcaa; }
    .BAD_SUBJECT_DIFFERS { color: #f48771; background: #4b1818; text-decoration: underline wavy red; }
    .BAD_SUBJECT_HAS_NOT { background: #2d3e2d; color: #75beff; opacity: 0.6; } /* Inserted */
    .BAD_SUBJECT_HAS { background: #4b1818; color: #f48771; opacity: 0.6; }     /* Deleted */
    .GAP { height: 30px; }
</style></head><body><div class="container">
"""

async def generate_html():
    config = Configuration()
    # Ensure analogies are tracked: Socrates in Subject maps to Author in Nominal
    s_stream = io.StringIO(subject)
    n_stream = io.StringIO(nominal)

    output = [HTML_TEMPLATE]

    async for cmd in ui_feeder(config, s_stream, n_stream):
        if cmd.kind == E_DisplayCmd.SECTION_HEADER:
            output.append(f"<div class='header'>{cmd.text}</div>")
        
        elif cmd.kind == E_DisplayCmd.ROW_DATA:
            output.append("<div class='row'>")
            # --- Subject Side ---
            output.append(f"<div class='line-no'>{cmd.line_n_s}</div><div class='side'>")
            for cell in cmd.cells_s:
                output.append(f"<span class='token {cell.relation_id.name}' title='Ref Cell: {cell.nominal_ref_i}'>{cell.subject or ''}</span>")
            output.append("</div>")

            # --- Nominal Side ---
            output.append(f"<div class='line-no'>{cmd.line_n_n}</div><div class='side'>")
            for cell in cmd.cells_n:
                output.append(f"<span class='token {cell.relation_id.name}'>{cell.nominal or ''}</span>")
            output.append("</div></div>")

        elif cmd.kind == E_DisplayCmd.ROW_GAP:
            output.append("<div class='GAP'></div>")

    output.append("</div></body></html>")
    
    print("\n".join(output))

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_html())
