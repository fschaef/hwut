# shell.awk -- the command interpreter of a serial adapter's service shell.
# Answers each command line with 'OK' or 'ERR <reason>'.
#   set <key> <value>   get <key>   reset [all | <key>]
#   key:   baud parity stop echo
#   value: a number, on, off, odd, even, none
function is_key(k)   { return k ~ /^(baud|parity|stop|echo)$/ }
function is_value(v) { return v ~ /^[0-9]+$/ || v ~ /^(on|off|odd|even|none)$/ }
{
    if ($1 == "set" && NF == 3)      { print (is_key($2) && is_value($3)) ? "OK" : "ERR value" }
    else if ($1 == "get" && NF == 2) { print is_key($2) ? "OK" : "ERR key" }
    else if ($1 == "reset" && NF == 1) print "OK"
    else if ($1 == "reset" && NF == 2) { print ($2 == "all" || is_key($2)) ? "OK" : "ERR key" }
    else print "ERR syntax"
}
