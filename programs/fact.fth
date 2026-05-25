var result
var n

nkey n !
1 result !

begin
  n @ 0 = if
    result @ . 1
  else
    n @ result @ * result !
    n @ 1 - n !
    0
  endif
until