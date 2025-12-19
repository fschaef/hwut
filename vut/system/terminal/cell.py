from   enum        import Enum, auto
from   itertools   import chain
from   typeguard   import typechecked
from   collections import namedtuple
from   vut.system.terminal.styled_text import ColorText, ColorTextList, E_Alignment, CellFormat

def format(fe, content):
    """RETURNS: Formats 'content' to fit cell specified by 'fe'.
    """
    if content is None:
        return fe.color_code + fe.string
    elif type(content) == str: 
        return fe.color_code + _plain_text(fe, content)
    else:                 
        result = _color_text_list(fe, content)
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

def _color_text_list(fe, color_text_list):
    """RETURNS: Colored, formatted text.
        
    Formats cell according to format expression and the text provided as tuples
    (color, text). Right aligned text is pruned from left, and vice versa.
    """
    result       = color_text_list.prepare_offset(fe.text_offset)
    total_length = sum(len(sub_text) for _, sub_text in result)
    result       = result.prune(total_length, fe.width, fe.alignment)
    total_length = sum(len(sub_text) for _, sub_text in result)

    return result.padding(fe, total_length)

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


