#! /usr/bin/env python3
# @hwut {
#     title    = "Bitcoin (2010): the sum of two outputs wraps negative, and 184 billion BTC pass the check"
#     choices {
#         v0.3.10 { features = ["headline-transaction", "boundary-matrix", "wrap-accepted"]
#                   tolerance { constraints = ["accepted_invalid > 0", "rejected_valid == 0"] } }
#         v0.3.11 { features = ["headline-transaction", "boundary-matrix", "every-invalid-refused"]
#                   tolerance { constraints = ["accepted_invalid == 0", "rejected_valid == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  what the output-value check of a Bitcoin transaction answers for
         two outputs and one input at the value boundaries of int64 --
         against the exact answer
HISTORY  On 15 August 2010 block 74638 held a transaction with two outputs
of 92233720368.54277039 BTC each (CVE-2010-5139). The client summed output
values in a signed 64-bit integer; the two values together overflowed and
wrapped to a small negative number, so 'outputs do not exceed the input'
held, and the transaction was valid by the rules as written: about 184
billion bitcoin had been created. Release 0.3.11 refused any output, and
any running sum, above MAX_MONEY (21 million BTC); the chain was forked
back to before the block within hours.

REQUIREMENT  A transaction is accepted exactly when every output lies in
             [0, MAX_MONEY], their sum does not exceed MAX_MONEY, and their
             sum does not exceed the input. Exact -- no wrap.

THE UNIT  '../check.c', C, int64_t as in the client, compiled per run with
-fwrapv (an overflow wraps, as on the machines of 2010): the check of
0.3.10 (outputs >= 0, sum <= input), or with -DRELEASE_0_3_11 the check of
0.3.11 (also each output and each running sum <= MAX_MONEY). Values in
satoshi, 1 BTC = 100 000 000.

THE SPACE  space_iterator over input x output_a x output_b:
    input     0.5 BTC (the model's), MAX_MONEY
    outputs   0, 1 satoshi, MAX_MONEY, MAX_MONEY + 1 satoshi, 2^62,
              the 2010 value 9223372036854277039, 2^63 - 1
2 x 7 x 7 = 98 transactions; the truth is computed with Python's exact
integers.

WHAT THE TEST PRINTS
  1. THE 2010 TRANSACTION: both outputs, their exact sum, the int64 sum
     the client saw, and the release's answer.
  2. ONE MATRIX PER INPUT, output_a down, output_b across. A cell:
         o  accepted, rightly      .  rejected, rightly
         X  ACCEPTED, though invalid      !  REJECTED, though valid
  3. The counts as bindings.

CHOICES
    v0.3.10   accepts every pair whose int64 sum wraps to <= the input:
              the X cells, among them the 2010 transaction.
    v0.3.11   the same space without an X.

HOW TO READ THE GOOD  An 'X' is a transaction that creates money. The
matrices stand in '##! verbatim'. Bindings: '((accepted_invalid: N))',
law '> 0' for 0.3.10 and '== 0' for 0.3.11; '((rejected_valid: N))',
law '== 0' for both -- the fix refuses nothing it should accept.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
import hwut.test_writing_support.python.space_iterator as space_iterator

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")

COIN       = 100000000
MAX_MONEY  = 21000000 * COIN
VALUE_2010 = 9223372036854277039            # 92233720368.54277039 BTC
INPUT_LIST  = [("0.5 BTC", COIN // 2), ("MAX_MONEY", MAX_MONEY)]
OUTPUT_LIST = [("0", 0), ("1 sat", 1), ("MAX", MAX_MONEY), ("MAX+1", MAX_MONEY + 1),
               ("2^62", 2 ** 62), ("2010", VALUE_2010), ("2^63-1", 2 ** 63 - 1)]
CHOICE_DB  = {"v0.3.10": [], "v0.3.11": ["-DRELEASE_0_3_11"]}


def valid_f(input_value, output_list):
    """
    RETURN: True, if the transaction is valid by the exact rule: every
                  output in [0, MAX_MONEY], their sum <= MAX_MONEY and
                  <= the input;
            False, else.
    """
    total = sum(output_list)
    return all(0 <= v <= MAX_MONEY for v in output_list) \
           and total <= MAX_MONEY and total <= input_value


def int64(value):
    """RETURN: int, 'value' wrapped to a signed 64-bit integer."""
    value &= 2 ** 64 - 1
    return value - 2 ** 64 if value >= 2 ** 63 else value


def btc(satoshi):
    """RETURN: str, 'satoshi' written in BTC with all eight decimals."""
    sign = "-" if satoshi < 0 else ""
    return "%s%d.%08d BTC" % (sign, abs(satoshi) // COIN, abs(satoshi) % COIN)


def answers(flag_list, case_list):
    """
    RETURN: list of str, the unit's answer per case of 'case_list'
            (input, a, b): 'accepted' or 'rejected: <reason>'.
    """
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "check")
        subprocess.check_call(["gcc", "-Wall", "-Werror", "-O1", "-fwrapv"] + flag_list
                              + ["-o", exe, os.path.join(UNIT, "check.c")])
        text = "".join("%d %d %d\n" % case for case in case_list)
        out = subprocess.run([exe], input=text, capture_output=True, text=True, check=True).stdout
    return out.splitlines()


def main(choice):
    """RETURN: int, 0 once the transaction and the matrices are printed."""
    flag_list = CHOICE_DB[choice]
    case_list = [(i, a, b) for (_, i), (_, a), (_, b)
                 in space_iterator.do([INPUT_LIST, OUTPUT_LIST, OUTPUT_LIST])]
    headline = (COIN // 2, VALUE_2010, VALUE_2010)
    answer_list = answers(flag_list, case_list + [headline])
    verdict_db = dict(zip(case_list, answer_list))

    print("release %s, check.c compiled with -fwrapv%s" % (choice, " " + " ".join(flag_list) if flag_list else ""))
    print()
    print("1. THE 2010 TRANSACTION (block 74638), against the model's input of 0.5 BTC")
    print("##! verbatim")
    print("   output 1      %s" % btc(VALUE_2010))
    print("   output 2      %s" % btc(VALUE_2010))
    print("   exact sum     %s" % btc(2 * VALUE_2010))
    print("   int64 sum     %s   <- wrapped" % btc(int64(2 * VALUE_2010)))
    print("   input         %s" % btc(COIN // 2))
    print("   exact rule    %s" % ("valid" if valid_f(*headline[:1], list(headline[1:])) else "INVALID"))
    print("   release says  %s" % answer_list[-1])
    print("####")
    print()
    print("2. EVERY PAIR OF OUTPUTS, per input (a down, b across)")
    accepted_invalid = rejected_valid = 0
    label_list = [label for label, _ in OUTPUT_LIST]
    for input_label, input_value in INPUT_LIST:
        print("input %s" % input_label)
        print("##! verbatim")
        print(("   %-7s %s" % ("a / b", " ".join("%-6s" % label for label in label_list))).rstrip())
        for label_a, a in OUTPUT_LIST:
            cell_list = []
            for _, b in OUTPUT_LIST:
                accepted = verdict_db[(input_value, a, b)] == "accepted"
                valid = valid_f(input_value, [a, b])
                cell = {(True, True): "o", (False, False): ".",
                        (True, False): "X", (False, True): "!"}[(accepted, valid)]
                accepted_invalid += cell == "X"
                rejected_valid   += cell == "!"
                cell_list.append("%-6s" % cell)
            print(("   %-7s %s" % (label_a, " ".join(cell_list))).rstrip())
        print("####")
    print("(o accepted rightly  . rejected rightly  X ACCEPTED though invalid  ! REJECTED though valid)")
    print()
    print("3. THE COUNTS over %d transactions" % len(case_list))
    if choice == "v0.3.10":
        print("    accepted, though invalid ((accepted_invalid: %d))   law > 0    %s"
              % (accepted_invalid, "the bug, reproduced" if accepted_invalid else "BROKEN: not reproduced"))
    else:
        print("    accepted, though invalid ((accepted_invalid: %d))   law == 0   %s"
              % (accepted_invalid, "kept" if accepted_invalid == 0 else "BROKEN"))
    print("    rejected, though valid   ((rejected_valid: %d))   law == 0   %s"
          % (rejected_valid, "kept" if rejected_valid == 0 else "BROKEN"))
    return 0


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    status = main(choice)
    print("<hwut-end>")
    sys.exit(status)
