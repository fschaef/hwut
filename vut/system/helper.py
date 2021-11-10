from   vut.external.quex.typed   import typed
from   math import ceil, log10

def number_of_decimal_digits(n):
    return ceil(log10(n+1))

def right_aligned(N, n=None, fill=" "):
    if n is None:
        return fill * N
    else:
        n_str = "%s" % n
        return fill * (N - len(n_str)) + n_str

class Interval:
   def __init__(self, begin, end):
       self.begin = begin
       self.end   = end

   @staticmethod
   def iterable_from_integer_list(self, integer_list):
       """YIELDS: Interval-s

       Combines ranges of adjacent integers into 'Range' objects.
       """
       integer_list.sort()
       
       result = []
       begin  = integer_list[0]
       for li in integer_list:
           if li - begin > 1: 
               yield Interval(begin, prev_li)
               begin = li
           prev_li = li
       
       if prev_li != begin:
           yield Interval(begin, prev_li)

   def empty(self):
       return self.end == self.begin

   @typed(part_n=int)
   def split(self, part_n):
       """YIELDS: 'Interval' objects manifesting the splitted ranges.

       Example: 'part_n == 2' -> split range in halves, 
                'part_n == 3' -> split range in thirds.
       """
       assert part_n >= 1
       delta     = int((self.end - self.begin) / part_n)
       remainder = 0
       for i in range(ratio-1):
           yield Interval(begin + delta * i, begin + delta * (i+1))

