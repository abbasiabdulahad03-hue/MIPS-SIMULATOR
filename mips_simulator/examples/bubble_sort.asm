# bubble_sort.asm — sorts 5 integers
.data
    arr:     .word 42, 17, 93, 5, 68
    msg_pre: .asciiz "Before: "
    msg_pst: .asciiz "\nAfter:  "
    space:   .asciiz " "
    newline: .asciiz "\n"

.text
main:
    li   $v0, 4
    la   $a0, msg_pre
    syscall
    la   $a1, arr
    li   $a2, 5
    jal  print_array

    la   $a0, arr
    li   $a1, 5
    jal  bubble_sort

    li   $v0, 4
    la   $a0, msg_pst
    syscall
    la   $a1, arr
    li   $a2, 5
    jal  print_array

    li   $v0, 10
    syscall

bubble_sort:
    addi $sp,$sp,-16
    sw   $ra,12($sp)
    sw   $s0,8($sp)
    sw   $s1,4($sp)
    sw   $s2,0($sp)
    move $s0,$a0
    move $s1,$a1
    addi $s1,$s1,-1
outer:
    beqz $s1,done
    li   $s2,0
inner:
    bge  $s2,$s1,next
    sll  $t0,$s2,2
    add  $t1,$s0,$t0
    lw   $t2,0($t1)
    lw   $t3,4($t1)
    ble  $t2,$t3,noswap
    sw   $t3,0($t1)
    sw   $t2,4($t1)
noswap:
    addi $s2,$s2,1
    j    inner
next:
    addi $s1,$s1,-1
    j    outer
done:
    lw   $ra,12($sp)
    lw   $s0,8($sp)
    lw   $s1,4($sp)
    lw   $s2,0($sp)
    addi $sp,$sp,16
    jr   $ra

print_array:
    addi $sp,$sp,-16
    sw   $ra,12($sp); sw $s0,8($sp); sw $s1,4($sp); sw $s2,0($sp)
    move $s0,$a1; move $s1,$a2; li $s2,0
pa_loop:
    bge  $s2,$s1,pa_done
    sll  $t0,$s2,2
    add  $t1,$s0,$t0
    lw   $a0,0($t1)
    li   $v0,1
    syscall
    li   $v0,4; la $a0,space; syscall
    addi $s2,$s2,1
    j    pa_loop
pa_done:
    lw $ra,12($sp); lw $s0,8($sp); lw $s1,4($sp); lw $s2,0($sp)
    addi $sp,$sp,16
    jr   $ra
