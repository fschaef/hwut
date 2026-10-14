# A branch taken and one not, a loop, a method never called.
def double(n)
  if n.negative?
    -2 * n
  else
    2 * n
  end
end

def never_called(n)
  n + 1
end

total = 0
[1, 2, 3].each { |n| total += double(n) }
puts "total: #{total}"
