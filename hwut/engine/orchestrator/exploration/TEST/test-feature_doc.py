#! /usr/bin/env python3
#
# @hwut {
#     title      = "The doc file of features: blocks, audiences, the retired, and what may not stand"
#     choices {
#         read      { features = ["doc-read"] }
#         audiences { features = ["doc-audiences-fold"] }
#         faults    { features = ["doc-faults-named"] }
#         prototypes { features = ["doc-prototype-blocks"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut-feature-doc.dat', read (spec 43 section 2; intend/43 T-c,
         T-g, T-p, T-s).

CHOICES: read, audiences, faults, prototypes;

read       a block's 'documents:' line, its title (the first prose line)
           and its doc (the rest), blank lines around them dropped; a block
           with prose only, one with nothing; a retired block; comments
           before the first heading; no file, None.

audiences  '[[CUSTOMERS]]' declares them; 'to' adds an audience to the
           feature and everything below it in the forest, 'not' takes an
           inherited one off; a feature in no forest line keeps its own.

faults     each named with file and line: text before the first heading, a
           heading of no shape, a feature id that is no id, 'CUSTOMERS' as
           an id, an id documented twice (plain and plain, plain and
           retired), a retired id that stands in a forest line, an
           audience not declared (with 'did you mean'), an audience line of
           no shape, '[[CUSTOMERS]]' twice.

prototypes (intend/44 p-5, p-8) what documents an instance: its own
           block; else its member's; else the block of the prototype it
           stands in, or of one around that; an inner prototype's
           instance by '[[+Q]]'. Audiences fold down the instance tree.
           A block of a prototype not declared, or of an instance the
           forest does not hold, is a fault.
______________________________________________________________________________
"""
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.engine.orchestrator.exploration.feature_forest \
    import forest_of_text                                          # noqa E402
from hwut.engine.orchestrator.exploration.feature_doc \
    import doc_of_text, read_doc, DocFault                         # noqa E402

FOREST = forest_of_text("gateway : forwarding, buses\n"
                        "forwarding : fwd, keeporder\n")

TEXT = """# the explanation
# of the gateway

[[CUSTOMERS]]
manager:   the one who puts us under pressure
integreng: the integration engineer
# a comment among them
intern:    the student

[[gateway to manager, integreng]]
documents: gateway/README.txt, spec/routing.txt#3 ,https://example.org/g

The gateway forwards what reaches it.

It forwards CAN to MOST,
  and MOST to CAN.

[[forwarding not manager]]
Frames reach their destination.

[[fwd to intern]]
[[keeporder]]
Order is kept per sender.
[[lonely to intern]]
A feature in no line.

[[old-thing:retired]]
documents: old.txt
What was once claimed.
"""


def read():
    """RETURN: None. The blocks as read."""
    doc = doc_of_text(TEXT, FOREST)
    for entry in list(doc.entry_db.values()) + list(doc.retired_db.values()):
        print("[%s]%s line %i" % (entry.id, " retired" if entry.retired_f
                                  else "", entry.line_n))
        print("    title      %r" % entry.title)
        print("    doc        %r" % entry.doc)
        print("    documents  %s" % (entry.document_tuple,))
        print("    to / not   %s / %s" % (entry.to_tuple, entry.not_tuple))
    print("customers  %s" % doc.customer_db)
    print("no file    %s" % read_doc(tempfile.mkdtemp(), FOREST))


def audiences():
    """RETURN: None. Each feature's audiences, folded down the forest."""
    doc = doc_of_text(TEXT, FOREST)
    for each in ("gateway", "forwarding", "fwd", "keeporder", "buses",
                 "lonely"):
        print("%-11s %s" % (each, doc.audience_db.get(each, ())))


def faults():
    """RETURN: None. Each fault as it is said."""
    customers = "[[CUSTOMERS]]\nmanager: m\nintegreng: i\n"
    for label, text in (
            ("text before",     "a sentence\n[[a]]\n"),
            ("heading shape",   "[[a b c]]\n"),
            ("to nothing",      "[[a to]]\n"),
            ("not an id",       "[[a.b]]\n"),
            ("audience no id",  customers + "[[a to x.y]]\n"),
            ("CUSTOMERS id",    "[[CUSTOMERS to manager]]\n"),
            ("CUSTOMERS retired", "[[CUSTOMERS:retired]]\n"),
            ("twice",           "[[a]]\nx\n[[a]]\ny\n"),
            ("plain, retired",  "[[a]]\nx\n[[a:retired]]\ny\n"),
            ("retired in forest", "[[keeporder:retired]]\n"),
            ("audience unknown", customers + "[[gateway to integeng]]\n"),
            ("audience line",   "[[CUSTOMERS]]\nmanager the one\n"),
            ("CUSTOMERS twice", customers + customers)):
        try:
            doc_of_text(text, FOREST)
            print("%-17s read" % label)
        except DocFault as fault:
            print("%-17s %s" % (label, fault))


PROTOTYPE_FOREST = forest_of_text("port-a : +show\nport-b : +show\n"
                                  "+show : greet, +talk\n"
                                  "+talk : ask, answer\n"
                                  "+lone : solo\n")

PROTOTYPE_TEXT = """[[CUSTOMERS]]
user: who runs it

[[+show to user]]
What every port shows.
[[greet]]
It says hello.
[[port-b+greet]]
Port b says hello its own way.
[[+talk]]
It talks.
"""


def prototypes():
    """RETURN: None. The block that documents each instance, the
    audiences, and the faults of prototype blocks."""
    from hwut.engine.orchestrator.exploration.feature_doc \
        import effective_entry                                     # noqa E402
    doc = doc_of_text(PROTOTYPE_TEXT, PROTOTYPE_FOREST)
    print("ids        %s" % sorted(doc.entry_db))
    for each in ("port-a+show", "port-a+greet", "port-b+greet",
                 "port-a+talk", "port-b+ask", "port-a", "solo"):
        entry = effective_entry(doc.entry_db, PROTOTYPE_FOREST, each)
        print("%-13s %-15s %s" % (each, entry.id if entry else None,
                                  doc.audience_db.get(each, ())))
    lonely = doc_of_text("[[+lone]]\nAlone.\n", PROTOTYPE_FOREST)
    print("x+solo        %s (only '[[+lone]]' stands)"
          % effective_entry(lonely.entry_db, PROTOTYPE_FOREST, "x+solo").id)
    for label, text in (
            ("undeclared",  "[[+nothing]]\nx\n"),
            ("no instance", "[[port-c+greet]]\nx\n"),
            ("member twice", "[[greet]]\nx\n[[greet]]\ny\n")):
        try:
            doc_of_text(text, PROTOTYPE_FOREST)
            print("%-13s read" % label)
        except DocFault as fault:
            print("%-13s %s" % (label, fault))


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The doc file of features: blocks, audiences, the retired, and what may not stand",
        choice_map = {"read": read, "audiences": audiences, "faults": faults,
                      "prototypes": prototypes},
    ).run()
