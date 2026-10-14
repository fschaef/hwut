import sys
def f(a):
    if a > 1:
        return 1
    elif a > 0:
        return 2
    return 3
f(int(sys.argv[1]))
