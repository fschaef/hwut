-- A tiny FSM: IDLE -> RUN -> DONE, advanced by 'enable'.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity blinker is
  port (
    clk    : in  std_logic;
    rst    : in  std_logic;
    enable : in  std_logic;
    done   : out std_logic
  );
end entity;

architecture rtl of blinker is
  type state_t is (IDLE, RUN, DONE_S);
  signal state : state_t := IDLE;
  signal count : unsigned(3 downto 0) := (others => '0');
begin
  process (clk)
  begin
    if rising_edge(clk) then
      if rst = '1' then
        state <= IDLE;
        count <= (others => '0');
      else
        case state is
          when IDLE =>
            if enable = '1' then
              state <= RUN;
            end if;
          when RUN =>
            count <= count + 1;
            if count = 3 then
              state <= DONE_S;
            end if;
          when DONE_S =>
            state <= DONE_S;
        end case;
      end if;
    end if;
  end process;

  done <= '1' when state = DONE_S else '0';

  -- psl default clock is rising_edge(clk);
  -- psl COVER_REACH_DONE : cover {state = DONE_S};
  -- psl COVER_ABORT      : cover {state = RUN; state = IDLE};
  -- psl ASSERT_COUNT_RUN : assert always (count > 0 -> state /= IDLE);
end architecture;
