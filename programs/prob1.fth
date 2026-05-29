var vpal_orig
var vpal_rev
var vi
var vj
var vbest
var vp

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

0 vbest !
999 vi !

begin

  vi @ vj !                 \ vj = vi

  begin
    vi @ vj @ * vp !

    vp @ vbest @ > if       \ if (vp := vi * vj > vbest)

      vp @ palindrome? if   \ if (palindrome?(vp))
        vp @ vbest !        \ vbest = bp
      endif

    endif

    vj @ 1 - vj !

    vj @ 100 < 
    vp @ vbest @ < 
    |
  until

  vi @ 1 - vi !
  vi @ 100 <

until

vbest @ .