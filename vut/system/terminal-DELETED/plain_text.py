from   typeguard   import typechecked
from   vut.system.terminal.styled_text import E_Alignment, \
                                              CellFormat

@typechecked
def render(fe: CellFormat, string: str):
    """RETURNS: Plain text of formatted 'string'. 
        
    In case, that text exceeds boundaries, it is pruned,  Right aligned
    text is pruned from the left, and vice versa.
    """
    def _prepare_offset(text_offset, text):
        """RETURNS: 'text' treated with an 'offset'. 

        offset == 0: text unchanged.
        offset > 0:  clip text from the left. 
                     offset > len => result is ""
        offset < 0:  put a number of offset spaces " " in front
        """
        if text_offset > 0:
            if text_offset >= len(text): return ""
            else:                        return text[text_offset:] 
        elif text_offset == 0:
            return text
        else:
            return " " * (-text_offset) + text

    result       = _prepare_offset(fe.text_offset, string)

    total_length = len(result)
    result       = prune(total_length, fe.width, fe.alignment, result)

    total_length = len(result)
    result       = padding(fe, total_length, result)

    return result

def prune(cell_length, width, alignment, text):
    """RETURNS: string pruned to width.
    """
    cut_n = cell_length - width
    if   cut_n <= 0:                      return text
    elif alignment == E_Alignment.RIGHT:  return text[cut_n:] 
    else:                                 return text[:-cut_n]

def padding(fe, cell_length, text):
    """RETURNS: string

    with additional characters such that the total length == 'cell_length'.
    """
    # text must be pruned before call to this function
    assert fe.width    >= cell_length
    assert cell_length >= len(text)

    if   fe.alignment == E_Alignment.RIGHT:  return text.rjust(fe.width, " ") 
    elif fe.alignment == E_Alignment.LEFT:   return text.ljust(fe.width, " ")
    else:                                    return text
