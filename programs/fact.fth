: fact ( n -- res )
  dup 0 = if
    1 swap drop
  else
    dup 1 - fact *
  endif
;

nkey fact .