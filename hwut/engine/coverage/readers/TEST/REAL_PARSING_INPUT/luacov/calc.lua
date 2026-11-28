local M = {}

function M.sign(n)
  if n < 0 then
    return -1
  elseif n == 0 then
    return 0
  end
  return 1
end

function M.unused(n)
  return n * 2
end

print(M.sign(-3), M.sign(5))
return M
