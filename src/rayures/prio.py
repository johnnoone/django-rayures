from operator import itemgetter
from collections import defaultdict

__all__ = ['PrioritySet']


def key_generator(key):
    result = []
    parts = key.split('.')
    for parts in iterakey(key.split('.')):
        result.append('.'.join(parts))
    return sorted(result)


def iterakey(parts):
    if not parts:
        raise StopIteration
    first, *remains = parts
    if remains:
        for x in iterakey(remains):
            if x[0] == '*':
                # fold *.* to *
                yield x
            else:
                yield ('*', *x)
            yield (first, *x)
    else:
            yield '*',
            yield first,


class PrioritySet:
    def __init__(self):
        self.funcs = defaultdict(dict)

    def add(self, key, func, position=None):
        self.funcs[key][func] = position
        return func

    def __getitem__(self, key):
        funcs = {}
        for k in key_generator(key):
            funcs.update(self.funcs[k])
        funcs.update(self.funcs[key])
        return [func for func, _ in sorted(funcs.items(), key=itemgetter(1))]
