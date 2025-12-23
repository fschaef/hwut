from vut.system.helper import number_of_decimal_digits, right_aligned

class DPMatrix(list):
    def __init__(self, X, Y):
        m = len(X)
        n = len(Y)
        self.dimensions = (m, n)
        self.first      = X
        self.second     = Y
        list.__init__(self, ([0 for x in range(n+1)] for x in range(m+1)))

        # Following steps build L[m+1][n+1] in bottom up fashion. Note that 
        # L[i][j] contains length of LCS of X[0..i-1] and Y[0..j-1].
        for i in range(m+1):
            for j in range(n+1):
                if i == 0 or j == 0:
                    self[i][j] = 0
                elif X[i-1] == Y[j-1]:
                    self[i][j] = self[i-1][j-1] + 1
                else:
                    self[i][j] = max(self[i-1][j], self[i][j-1])

    def get_string(self):
        m, n = self.dimensions
        cell_largest_n = self[m][n]
        cell_digit_n   = number_of_decimal_digits(cell_largest_n) + 1
        row_digit_n    = number_of_decimal_digits(m) + 1
        
        txt = []
        txt.append(right_aligned(row_digit_n))
        txt.append(" |")
        txt.extend(right_aligned(cell_digit_n, i) for i in range(n+1))
        txt.append("\n")
        txt.append(right_aligned(row_digit_n, fill="-"))
        txt.append("-+")
        txt.extend(right_aligned(cell_digit_n, fill="-") for i in range(n+1))
        for row in range(m+1):
            txt.append("\n")
            txt.append(right_aligned(row_digit_n, row))
            txt.append(" |")
            txt.extend(right_aligned(cell_digit_n, self[row][column]) for column in range(n+1))
        return "".join(txt)

    def associations(self):
        m, n = self.dimensions
        X    = self.first
        Y    = self.second

        # Start from the right-most-bottom-most corner and
        # one by one store characters in lcs[]
        i = m
        j = n
        while i > 0 and j > 0:
            # If current character in X[] and Y are same, then current 
            # character is part of LCS
            if X[i-1] == Y[j-1]:
                i-=1
                j-=1
                yield i, j
            # If not same, then find the larger of two and go in the direction 
            # of larger value
            elif self[i-1][j] > self[i][j-1]:
                i-=1
            else:
                j-=1

    def get_sequence(self):
        return reversed("".join(self.first[i] for i, _ in self.associations()))
            

def places_of_increment(subject, nominal):
    """RETURNS:
         
          equivalence_db:  subject index --> equivalent nominal indices
    """
    # map: hash(nominal entry) --> index of nominal entry
    nominal_hash_db = defaultdict(list)
    for ni, x in enumerate(nominal):
        nominal_hash_db[hash(x)].append(ni)

    result = defaultdict(list)
    for si, x in enumerate(subject):
        result[si] = copy(nominal_hash_db.get(hash(x)))

    return result

def cut_same_begin(X, Y):
    for i, entry in enumerate(zip(X, Y)):
        x, y = entry
        if x != y: break
    return i

def cut_same_end(X, Y):
    for i, entry in enumerate(zip(reversed(X), reversed(Y))):
        x, y = entry
        if x != y: break
    return i

def do(X, Y):
    begin_n = cut_same_begin(X, Y)
    begin_n = 0
## yield from ((i, i) for i in range(begin_n))
#end_n   = cut_same_end(X, Y)
    end_n =0
    Lx = len(X)
    Ly = len(Y)
    if end_n:
        pass #yield from ((Lx-i, Ly-i) for i in range(end_n+1))
    yield from DPMatrix(X[begin_n:Lx-end_n], Y[begin_n:Ly-end_n]).associations()
## yield from ((i, i) for i in range(begin_n))

def get_sequence(first, second):
    for i, j in do(first, second):
        print("#i,i", i, j, first[i], second[i])
#return reversed("".join(first[i] for i, _ in do(first, second)))
    return ""

# Driver program
def core(first, second):
    m = DPMatrix(first, second)
    print(m.get_string())
    print()
    lcs = get_sequence(first, second)
    print(first + " vs. " + second + " => " + "".join(lcs))
    print()

def test(first, second):
    core(first, second)
    core(second, first)

if True:
    test("A",   "A")
    test("AB",  "AB")
    test("ABC", "ABC")
    test("A",   "ABC")
    test("XYA", "ABC")
    test("A",   "CBA")
elif False:
    N = 1000
    test("".join("%s" % i for i in range(N)), "".join("%s" % i for i in range(N)))

