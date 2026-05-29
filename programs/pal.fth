var vpal_orig
var vpal_rev

\ буквально s == s[::-1]
: palindrome? ( n -- flag )
  dup vpal_orig !
  0 vpal_rev !
  begin
    dup 10 mod
    vpal_rev @ 10 * +
    vpal_rev !
    10 /
    dup 0 =
  until
  vpal_orig @ vpal_rev @ =
  swap drop
;

nkey palindrome? .