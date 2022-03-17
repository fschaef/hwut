from   enum      import Enum, auto
from   itertools import chain

class E_Alignment(Enum):
    LEFT  = auto()
    RIGHT = auto()

def format(fe, content):
    """RETURNS: Formats 'content' to fit cell specified by 'fe'.
    """
    if content is None:
        return fe.color_code + fe.string
    elif type(content) == str: 
        return fe.color_code + _plain_text(fe, content)
    else:                 
        result = _color_text_list(fe, content)
        return _color_text_list_apply(fe, result)

def _plain_text(fe, string):
    """RETURNS: Plain text of formatted 'string'. 
        
    In case, that text exceeds boundaries, it is pruned,  Right aligned
    text is pruned from the left, and vice versa.
    """
    result       = _plain_text_prepare_offset(fe.text_offset, string)
    total_length = len(result)
    result       = _plain_text_prune(total_length, fe.width, fe.alignment, result)
    total_length = len(result)

    return _plain_text_padding(fe, total_length, result)

def _color_text_list(fe, color_text_list):
    """RETURNS: Colored, formatted text.
        
    Formats cell according to format expression and the text provided as tuples
    (color, text). Right aligned text is pruned from left, and vice versa.
    """
    result       = _color_text_list_prepare_offset(fe.text_offset, color_text_list)
    total_length = sum(len(sub_text) for _, sub_text in result)
    result       = _color_text_list_prune(total_length, fe.width, fe.alignment, result)
    total_length = sum(len(sub_text) for _, sub_text in result)

    return _color_text_list_padding(fe, total_length, result)

def _color_text_list_apply(fe, color_text_list):
    """RETURNS: list of strings

    where the color codes of the elements of the 'color_text_list'
    are applied. That is, it transforms tuples of (color, text) into
    text with color control characters.
    """ 
    def _color(fe, color):
        return fe.color_code if not color else color

    result = [
        _color(fe, color) + sub_text
        for color, sub_text in color_text_list
    ]
    result.append(fe.color_code)
    return "".join(result)

def _plain_text_prepare_offset(text_offset, text):
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

def _color_text_list_prepare_offset(text_offset, color_text_list):
    """RETURNS: list of (color, string)

    where the string is adapted such that the text offset is prepared.
    """
    if text_offset > 0:
        return list(_color_text_list_prune_begin(color_text_list, text_offset))
    elif text_offset == 0:
        return color_text_list
    else:
        # Add some offset at the beginning (color = default cell color)
        return [("", " " * (-text_offset))] + color_text_list

def _plain_text_prune(total_length, width, alignment, text):
    """RETURNS: string pruned to width.
    """
    cut_n = total_length - width
    if   cut_n <= 0:                      return text
    elif alignment == E_Alignment.RIGHT:  return text[cut_n:] 
    else:                                 return text[:-cut_n]

def _color_text_list_prune(total_length, width, alignment, color_text_list):
    """RETURNS: list of (color, text)

    such that the given text width is not exceeded. Right aligned text
    is pruned from the left, and vice versa.
    """
    cut_n = total_length - width

    if   cut_n <= 0:          
        return color_text_list
    elif alignment == E_Alignment.RIGHT: 
        return list(_color_text_list_prune_begin(color_text_list, cut_n))
    else:
        remaining_n = total_length - cut_n
        return list(_color_text_list_prune_end(color_text_list, remaining_n))

def _color_text_list_prune_begin(color_text_list, cut_n):
    """RETURNS: Colored text.

    Considers list of tuples (color, text) and cuts of 'cut_n' characters
    from the front of the text.
    """
    assert cut_n > 0

    flush_f = False
    for color, sub_text in color_text_list:
        if flush_f:
            yield color, sub_text
        elif len(sub_text) >= cut_n:
            yield color, sub_text[cut_n:]
            flush_f = True
        else:
            cut_n -= len(sub_text)

def _color_text_list_prune_end(color_text_list, remaining_n):
    """RETURNS: Colored text.

    Considers list of tuples (color, text) and cuts of 'cut_n' characters
    from the back of the text.
    """
    for color, sub_text in color_text_list:
        if len(sub_text) >= remaining_n:
            yield color, sub_text[:remaining_n]
            break
        remaining_n -= len(sub_text)
        yield color, sub_text

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


def _color_text_list_padding(fe, total_length, color_text_list):
    """RETURNS: list of (color, text) with padding left/right.

    Prepares content according to format expression and returns the
    text.
    """
    assert fe.width >= total_length
    # Remove empty strings
    color_text_list = [ ct for ct in color_text_list if ct[1] ]

    add_n = fe.width - total_length
    if add_n <= 0: 
        return color_text_list
    elif fe.alignment == E_Alignment.RIGHT:
        if add_n: return [(None, " " * add_n)] + color_text_list 
        else:     return color_text_list
    elif fe.alignment == E_Alignment.LEFT:
        if add_n: return color_text_list + [(None, " " * add_n)]
        else:     return color_text_list
    else:
        assert False

