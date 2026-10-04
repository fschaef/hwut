# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
The converters (coverage D-44, D-45): 'hwut.cov.conv.to_humans' (a
coverage file, binary to text and back) and, over a whole output
directory, 'to_lcov', 'to_html', 'to_cobertura', 'to_jacoco', 'to_json',
'to_tex' and 'to_pdf' -- each a visitor ('../visitor.py') over the one
fold ('../summary.py'), with the one command line of '_face.py'.
'hwut-coverage.sty' is the package 'to_tex' writes its document for.
"""
