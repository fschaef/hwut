"""SPDX License: MIT; (C) Frank-Rene Schäfer; Project: hwut
_______________________________________________________________________________

PURPOSE: Definition of core structures, namely 'E_Verdict' and 'Configuration'.
_______________________________________________________________________________
"""
from enum import Enum, auto

class E_Verdict(Enum):
    MISFIT           = auto()
    DIFFERENT        = auto()
    EQUIVALENT       = auto()
    ERROR_IN_SUBJECT = auto()
    ERROR_IN_NOMINAL = auto()

class Configuration:
    __slots__ = ("strip_whitespace_f",           
                 "analogy_f",                   
                 "whitespace_f",                
                 "backslash_f",                 
                 "numeric_tolerance_ratio",     
                 "equivalent_pattern_list",     
                 "visible_nothing_pattern_list",
                 "potpourri_max_comparison_count")
    
    def __init__(self):
        # ToleranceTable
        self.strip_whitespace_f           = True
        self.analogy_f                    = True
        self.whitespace_f                 = True
        self.backslash_f                  = True
        self.numeric_tolerance_ratio      = 0    # [0:1] 0=perfect fit; 1=any number works
        self.equivalent_pattern_list      = []
        self.visible_nothing_pattern_list = []

        # ComperatorPotpourri
        self.potpourri_max_comparison_count = 128

