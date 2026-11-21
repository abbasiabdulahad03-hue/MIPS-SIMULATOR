# factorial.asm — iterative n!
.data
    msg: .asciiz "10! = "
    nl:  .asciiz "\n"
.text
main:
    li   $v0,4; la $a0,msg; syscall
    li   $a0,10
    jal  fact
    li   $v0,1; move $a0,$v0; syscall
    li   $v0,4; la $a0,nl; syscall
    li   $v0,10; syscall
fact:
    li   $v0,1
    li   $t0,1
loop:
    bgt  $t0,$a0,done
    mult $v0,$t0
    mflo $v0
    addi $t0,$t0,1
    j    loop
done:
    jr   $ra
