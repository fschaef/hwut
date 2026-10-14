       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 N PIC S9(4) VALUE 5.
       01 R PIC S9(4).
       PROCEDURE DIVISION.
           IF N < 0
               DISPLAY "NEGATIVE"
           ELSE
               COMPUTE R = 2 * N
               DISPLAY "ANSWER " R
           END-IF.
           STOP RUN.
