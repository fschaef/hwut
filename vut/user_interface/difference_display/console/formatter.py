"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""

from   vut.system.terminal             import GLUE, LEFT, RIGHT, CENTER, FIXED, Fore, Back
from   vut.engine.compare.engine.line  import Line

class ConsoleCanvasFormatter:
    def __init__(self, terminal_width, line_n_width, text_offset, canvas):
        self.line_n_width  = line_n_width
        
        remaining          = terminal_width - 2 * self.line_n_width - 3
        self.subject_width = int(remaining/2)
        self.nominal_width = remaining - self.subject_width
        self.text_offset   = text_offset
        self.canvas        = canvas
        self.setup_formats()

    def add_text_offset(self, value):
        self.text_offset += value
        if self.text_offset < 0:
            self.text_offset = 0
        self.setup_formats()

    def setup_formats(self):
        """Adapts the format expression to local settings of text width's and
        offsets.
        """
        self.normal = self.canvas.prepare_format(
            LEFT(self.subject_width, text_offset=self.text_offset), 
            FIXED(" ", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Bw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED(" ", "Uw"), 
            LEFT(self.nominal_width, text_offset=self.text_offset)
        )

        self.subject_empty = self.canvas.prepare_format(
            FIXED(" " * self.subject_width, "Rw"),
            FIXED("<", "Rw"), 
            FIXED("<" * self.line_n_width, "Rw"), 
            FIXED("|", "Bw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED(" ", "Uw"), 
            LEFT(self.nominal_width, text_offset=self.text_offset)
        )

        self.subject_end = self.canvas.prepare_format(
            FIXED("-" * self.subject_width, "Bw"),
            FIXED("<", "Rw"), 
            FIXED("<" * self.line_n_width, "Rw"), 
            FIXED("|", "Bw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED(" ", "Uw"), 
            LEFT(self.nominal_width, text_offset=self.text_offset)
        )
        self.subject_end_nominal_empty = self.canvas.prepare_format(
            FIXED("-" * self.subject_width, "Bw"),
            FIXED("-", "Bw"), 
            FIXED("-" * self.line_n_width, "Bw"), 
            FIXED("|", "Bw"), 
            FIXED(" " * self.line_n_width, "Rw"), 
            FIXED(" ", "Rw"), 
            FIXED(" " * self.nominal_width, "Rw")
        )

        self.nominal_empty = self.canvas.prepare_format(
            LEFT(self.subject_width, text_offset=self.text_offset), 
            FIXED(" ", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Bw"), 
            FIXED(">" * self.line_n_width, "Rw"), 
            FIXED(">", "Rw"), 
            FIXED(" " * self.nominal_width, "Rw")
        )

        self.nominal_end = self.canvas.prepare_format(
            LEFT(self.subject_width, text_offset=self.text_offset), 
            FIXED(" ", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Bw"), 
            FIXED(">" * self.line_n_width, "Rw"), 
            FIXED(">", "Rw"), 
            FIXED("-" * self.nominal_width, "Bw")
        )

        self.nominal_end_subject_empty = self.canvas.prepare_format(
            FIXED(" " * self.subject_width, "Rw"),
            FIXED(" ", "Rw"), 
            FIXED(" " * self.line_n_width, "Rw"), 
            FIXED("|", "Bw"), 
            FIXED("-" * self.line_n_width, "Bw"), 
            FIXED("-", "Bw"), 
            FIXED("-" * self.nominal_width, "Bw")
        )

        self.both_end = self.canvas.prepare_format(
            FIXED("-" * self.subject_width, "Bw"),
            FIXED("-", "Bw"), 
            FIXED("-" * self.line_n_width, "Bw"), 
            FIXED("|", "Bw"), 
            FIXED("-" * self.line_n_width, "Bw"), 
            FIXED("-", "Bw"), 
            FIXED("-" * self.nominal_width, "Bw")
        )

        self.empty = self.canvas.prepare_format(
            FIXED(" " * self.subject_width, "Rw", text_offset=self.text_offset),
            FIXED(" ", "Rw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED(":", "Bw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED(" ", "Rw"), 
            FIXED(" " * self.nominal_width, "Rw", text_offset=self.text_offset)
        )

        self.filler = self.canvas.prepare_format(
            FIXED(" " * self.subject_width, "Rw", text_offset=self.text_offset),
            FIXED(":", "Bw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED("|", "Bw"), 
            FIXED(" " * self.line_n_width, "Bw"), 
            FIXED(":", "Bw"), 
            FIXED(" " * self.nominal_width, "Rw", text_offset=self.text_offset)
        )

        self.potpourri_begin = self.canvas.prepare_format(
            FIXED("|" * self.subject_width + "|", "Gw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|" + "|" * self.nominal_width, "Gw"),
        )

        self.potpourri_end = self.canvas.prepare_format(
            FIXED("|" * self.subject_width + "|", "Gw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|", "Uw"), 
            LEFT(self.line_n_width, "Uw"), 
            FIXED("|" + "|" * self.nominal_width, "Gw"),
        )

        self.status_line = self.canvas.prepare_format(
            FIXED("[q] quit [h] help [w] up [s] down [a] left [d] right", "Bg"), 
            GLUE(" ", "Wg"),
            RIGHT(15, "Bg"),
            FIXED(" ", "Bg"),
            RIGHT(4, "Bg")
        )

    def end_of_stream_subject(self, line_n):
        return Line.from_string(line_n, "/" * self.subject_width)

    def end_of_stream_nominal(self, line_n):
        return Line.from_string(line_n, "/" * self.nominal_width)

