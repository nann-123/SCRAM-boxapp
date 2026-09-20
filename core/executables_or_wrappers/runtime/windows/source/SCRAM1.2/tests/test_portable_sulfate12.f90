program test_portable_sulfate12
 use Initialization
 use Condensation,only:SULFDYN
 use, intrinsic::ieee_arithmetic
 implicit none
 double precision::q(2,N_aerosol),q1(2,N_aerosol),n(2),n1(2),gas(N_aerosol)
 double precision::rate(2,N_aerosol),dt,kernel(2),expected,sink
 integer::trial,i
 N_size=2;allocate(wet_diameter(2),addm(N_aerosol));wet_diameter=[0.02d0,0.2d0]
 diffusion_coef=0.d0;quadratic_speed=200.d0;accomodation_coefficient=0.65d0
 do trial=1,4
  n=[1.d8,2.d8];gas=0.d0;gas(ESO4)=1.d0;q=0.d0;q(:,ESO4)=0.1d0
  q1=q;rate=0.d0;addm=0.d0;diffusion_coef(ESO4)=1.d-5;dt=10.d0
  if(trial==1) diffusion_coef(ESO4)=0.d0
  if(trial==2) n=0.d0
  if(trial==3) dt=0.d0
  sink=0.d0
  do i=1,2
   call compute_condensation_transfer_rate(diffusion_coef(ESO4),quadratic_speed(ESO4), &
     accomodation_coefficient(ESO4),wet_diameter(i),kernel(i))
   sink=sink+n(i)*kernel(i)
  enddo
  expected=gas(ESO4)*(1.d0-exp(-sink*dt))
  call SULFDYN(q1,q,n1,n,gas,rate,dt)
  if(any(.not.ieee_is_finite(q)).or.any(.not.ieee_is_finite(rate))) error stop 'nonfinite sulfate'
  if(abs(sum(q(:,ESO4))-0.2d0-expected)>1.d-12) error stop 'incorrect sulfate increment'
  if(any(n1/=n)) error stop 'sulfate changed number'
  if(sum(q(:,ESO4))-0.2d0>gas(ESO4)*(1.d0+1.d-12)) error stop 'sulfate budget exceeded'
 enddo
 print*,'PASS: 4 standalone sulfate zero-sink/zero-number/zero-dt/analytic-budget cases'
end program
