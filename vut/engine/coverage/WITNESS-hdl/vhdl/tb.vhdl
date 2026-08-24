-- Testbench: reset, then enable long enough to reach DONE_S.
library ieee;
use ieee.std_logic_1164.all;

entity tb is
end entity;

architecture sim of tb is
  signal clk    : std_logic := '0';
  signal rst    : std_logic := '1';
  signal enable : std_logic := '0';
  signal done   : std_logic;
  signal stop   : boolean   := false;
begin
  dut : entity work.blinker
    port map (clk => clk, rst => rst, enable => enable, done => done);

  clk <= not clk after 5 ns when not stop else '0';

  process
  begin
    wait for 12 ns;
    rst    <= '0';
    wait for 10 ns;
    enable <= '1';
    wait for 100 ns;
    stop   <= true;
    wait;
  end process;
end architecture;
