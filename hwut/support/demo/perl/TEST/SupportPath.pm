# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: WHERE THE PERL TEST SUPPORT STANDS -- named here, once, for every
#          test of this directory that uses it ('garage.pl', 'screen.pl'):
#
#              use FindBin;  use lib $FindBin::Bin;  use SupportPath;
#              use Hwut::Runner;
#
#          PERL5LIB, Perl's own mechanism, wins: its directories stand in
#          @INC before this one, which is APPENDED. Only where PERL5LIB does
#          not name the support is the path below used -- relative to the
#          test's directory, or as written where it is absolute.
#______________________________________________________________________________
package SupportPath;
use strict;
use warnings;
use FindBin;

BEGIN { my $at = "../../../test_writing/perl"; push @INC, ($at =~ m{^/} ? $at : "$FindBin::Bin/$at") }   # HWUT-SUPPORT-PATH

1;
