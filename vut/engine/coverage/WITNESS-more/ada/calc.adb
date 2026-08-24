with Ada.Text_IO; use Ada.Text_IO;
procedure Calc is
   N : Integer := 5;
begin
   if N < 0 then
      Put_Line ("negative");
   else
      Put_Line ("answer" & Integer'Image (2 * N));
   end if;
end Calc;
