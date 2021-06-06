from collections import deque

class Cache(dict):
    def __init__(self, size):
        self.size = size

    def __setitem__(self, key, entry):
        if len(self) >= self.size:
            # Cache filled => delete the first (random) key that pops up.
            del self[next(iter(self))]
        dict.__setitem__(self, key, entry)

    def get(self, key, func, *args):
        entry = dict.get(self, key)
        if entry is None:
            entry     = func(*args)
            self[key] = entry
        return entry


class HwutIterator:
    def __init__(self, iterable):
        self.__prefetch = deque()
        self.__iterable = iter(iterable)

    def __iter__(self):
        return self

    def collect_until(self, auxiliary, condition=lambda x, y: x == y, constructor=lambda x: x):
        result        = deque()
        walk_distance = 0
        while 1 + 1 == 2:
            try:
                candidate = next(self)
            except StopIteration:
                self.__prefetch.extendleft(result) # reset the read content
                return None, None
            walk_distance += 1
            if condition(candidate, auxiliary, walk_distance):
                return list(result), candidate
            result.append(candidate)

    def remaining(self):
        result = []
        try:
            while 1 + 1 == 2:
                result.append(next(self))
        except StopIteration:
            return result

    def count_remaining(self):
        count = 0
        try:
            while 1 + 1 == 2:
                count += 1
                next(self)
        except StopIteration:
            return count

    def undo(self, value):
        self.__prefetch.appendleft(value)

    def undo_list(self, list_value):
        self.__prefetch.extendleft(list_value)

    def __next__(self):
        if self.__prefetch:
            result = self.__prefetch.pop()
        else:
            result = next(self.__iterable) # raises 'StopIteration'
        return result

class LineProviderFromArray:
    def __init__(self, line_list):
        self.__line_list = line_list
        self.__i = -1

    def get(self):
        if self.__i == len(self.__line_list) - 1:
            return None
        else:
            self.__i += 1
            return self.__line_list[self.__i]


