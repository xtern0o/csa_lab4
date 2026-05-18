( hello, name )

: read-name-echo
  begin
    key
    dup 10 = if
      drop 1
    else
      emit
      0
    endif
  until
;

." Hello, "
read-name-echo