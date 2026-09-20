program test_portable_reference12
 use Initialization
 use ConservativeRemap12,only:port_remap=>moving_center_dualpivot
 use RemapReference12,only:ref_remap=>moving_center_dualpivot
 implicit none
 integer::i,j,k,a,trial,count
 double precision::x,y,d,v,alpha,temp,density
 double precision::mass(N_aerosol),gas(N_aerosol),massref(N_aerosol),gasref(N_aerosol),kp(N_aerosol)
 double precision::bound(5),pivot(4),rho(3),q(4,3),qr(4,3),n(4),nr(4),dry(4),dryref(4)
 count=0
 do i=1,20
  d=10.d0**(-4.d0+0.3d0*i)
  do j=1,4
   alpha=0.25d0*(j-1)
   v=100.d0+100.d0*j
   call compute_condensation_transfer_rate(1.d-5,v,alpha,d,x)
   call ref_compute_condensation_transfer_rate(1.d-5,v,alpha,d,y)
   call same(x,y,'transport');count=count+1
  enddo
 enddo
 do i=1,20
  temp=250.d0+i;density=1000.d0;d=10.d0**(-10.d0+0.5d0*i)
  call compute_kelvin_coefficient(temp,98.d0,0.08d0,d,density,x)
  call ref_compute_kelvin_coefficient(temp,98.d0,0.08d0,d,density,y)
  call same(x,y,'Kelvin');count=count+1
 enddo
 call compute_kelvin_coefficient(0.d0,98.d0,0.08d0,1.d0,1000.d0,x)
 call same(x,1.d0,'Kelvin invalid denominator');count=count+1
 bound=[1.d0,2.d0,4.d0,8.d0,16.d0];pivot=sqrt(bound(1:4)*bound(2:5));rho=[1.d0,2.d0,1.d0]
 do trial=1,100
  n=[1.d2,1.d3,1.d4,1.d-5]*10.d0**(mod(trial,6)-3)
  do k=1,4
   d=pivot(k)*(0.4d0+0.02d0*trial)
   q(k,1)=n(k)*acos(-1.d0)/6.d0*d**3*0.4d0
   q(k,2)=n(k)*acos(-1.d0)/6.d0*d**3*0.6d0*2.d0
   q(k,3)=0.1d0*q(k,1)
  enddo
  qr=q;nr=n
  call port_remap(4,3,3,bound,pivot,rho,q,n,dry)
  call ref_remap(4,3,3,bound,pivot,rho,qr,nr,dryref)
  do k=1,4
   call same(n(k),nr(k),'remap number');call same(dry(k),dryref(k),'remap dry mass')
   do i=1,3
    call same(q(k,i),qr(k,i),'remap species')
   enddo
  enddo
  count=count+1
 enddo
 write(*,*) 'PASS portable reference differential scenarios:',count
contains
 subroutine same(a,b,label)
  double precision,intent(in)::a,b
  character(len=*),intent(in)::label
  if(abs(a-b)>1.d-12*max(abs(a),abs(b),1.d-100)) then
   write(*,*)label,a,b
   error stop 'CESM differential mismatch'
  endif
 end subroutine
end program
