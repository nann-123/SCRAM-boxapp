! SCRAM1.2 regression: both movement directions, open tails, repeated remaps,
! two dry species + water, and an arbitrarily dilute positive population.
program test_remap12
  use ConservativeRemap12
  implicit none
  integer :: trial,k,s
  double precision :: b(5),p(4),rho(3),q(4,3),n(4),dry(4),nb,mb(3),v,d
  double precision :: target(4)
  b=[1.d0,2.d0,4.d0,8.d0,16.d0];p=sqrt(b(1:4)*b(2:5));rho=[1.d0,2.d0,1.d0]
  do trial=1,100
    ! Bin1 grows into bin2; bin4 evaporates into bin2; open tails retained.
    target=[3.d0,0.5d0,30.d0,3.d0]
    n=[1.d0,2.d0,3.d0,1.d-25]*dble(trial)
    do k=1,4
      v=acos(-1.d0)/6.d0*target(k)**3*n(k)
      q(k,1)=0.3d0*v*rho(1);q(k,2)=0.7d0*v*rho(2);q(k,3)=0.1d0*v
    enddo
    nb=sum(n);mb=sum(q,dim=1)
    call moving_center_dualpivot(4,3,3,b,p,rho,q,n,dry)
    if(abs(sum(n)-nb)>5.d-12*nb) error stop 'number not conserved'
    if(any(abs(sum(q,dim=1)-mb)>5.d-12*mb)) error stop 'species not conserved'
    if(any(n<0.d0).or.any(q<0.d0)) error stop 'negative remap output'
    ! Second pass must be stable (including when accumulated cohorts mix).
    call moving_center_dualpivot(4,3,3,b,p,rho,q,n,dry)
    if(abs(sum(n)-nb)>5.d-12*nb) error stop 'repeat number not conserved'
    if(any(abs(sum(q,dim=1)-mb)>5.d-12*mb)) error stop 'repeat mass not conserved'
  enddo
  print *, 'PASS: 100 bidirectional, tail, dilute and repeat remap cases'
end program
