from   enum        import Enum, auto
from   itertools   import chain
from   typeguard   import typechecked
from   collections import namedtuple
from   vut.system.terminal.styled_text import ColorText, ColorTextList, E_Alignment, CellFormat

@typechecked
def format(fe: CellFormat, content: None | str | ColorTextList):
    """RETURNS: Formats 'content' to fit cell specified by 'fe'.
    """
    if content is None:
        return fe.color_code + fe.string
    elif type(content) == str: 
        return fe.color_code + _plain_text(fe, content)
    elif isinstance(content, ColorTextList):                 
        result = content.format(fe)
        return result.render(fe.color_code)

def _plain_text(fe, string):
    """RETURNS: Plain text of formatted 'string'. 
        
    In case, that text exceeds boundaries, it is pruned,  Right aligned
    text is pruned from the left, and vice versa.
    """
    def _prepare_offset(text_offset, text):
        """RETURNS: string with appropriate text offset

        where the string is adapted such that the text offset is prepared.
        """
        if text_offset > 0:
            if text_offset >= len(text): return ""
            else:                        return text[text_offset:] 
        elif text_offset == 0:
            return text
        else:
            # Add some offset at the beginning
            return " " * (-text_offset) + text

    result       = _prepare_offset(fe.text_offset, string)
    total_length = len(result)
    result       = _plain_text_prune(total_length, fe.width, fe.alignment, result)
    total_length = len(result)

    return _plain_text_padding(fe, total_length, result)

def _plain_text_prune(total_length, width, alignment, text):
    """RETURNS: string pruned to width.
    """
    cut_n = total_length - width
    if   cut_n <= 0:                      return text
    elif alignment == E_Alignment.RIGHT:  return text[cut_n:] 
    else:                                 return text[:-cut_n]

def _plain_text_padding(fe, total_length, text):
    """RETURNS: string

    with additional characters such that the total length == 'total_length'.
    """
    # text must be pruned before call to this function
    assert fe.width     >= total_length
    assert total_length >= len(text)

    if   fe.alignment == E_Alignment.RIGHT:  return text.rjust(fe.width, " ") 
    elif fe.alignment == E_Alignment.LEFT:   return text.ljust(fe.width, " ")
    else:                                    return text


