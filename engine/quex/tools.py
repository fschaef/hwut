# Project Quex (http://quex.sourceforge.net); License: MIT;
# (C) 2005-2020 Frank-Rene Schaefer; 
#_______________________________________________________________________________
def areinstance(a, b, cls):
    verdict_a = isinstance(a, cls)
    verdict_b = isinstance(b, cls)
    if verdict_a != verdict_b: return False, None
    elif verdict_a:            return True, True
    elif verdict

