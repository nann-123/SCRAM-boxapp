! SCRAM1.2 regression: pair stoichiometry, source/target coincidence,
! species closure and positivity with very large actual time-step budgets.
program test_nearest12
  use Initialization
  use CoagulationNearest12
  implicit none
  double precision :: n(2),q(2,N_aerosol),rn(2),rm(2,N_aerosol),dt
  integer :: trial,i,s
  N_size=2;N_sizebin=2;N_fracmax=1;N_groups=1;N_species=2
  allocate(List_species(2),Index_groups(2),diam_bound(3),cell_diam_av(2))
  allocate(concentration_index(2,2),concentration_index_iv(2,1))
  allocate(discretization_composition(2,1,1,2),kernel_coagulation(2,2))
  List_species=[1,2];Index_groups=1;diam_bound=[0.01d0,0.1d0,1.d0]
  cell_diam_av=[0.05d0,0.5d0];fixed_density=1.d-9;mass_density_aer=1.d-9
  concentration_index(:,1)=[1,2];concentration_index(:,2)=1
  concentration_index_iv(:,1)=[1,2];discretization_composition=0.d0
  n=[1.d8,2.d8];q=0.d0
  do i=1,2
    q(i,1)=0.3d0*n(i)*acos(-1.d0)/6.d0*cell_diam_av(i)**3*fixed_density
    q(i,2)=0.7d0*n(i)*acos(-1.d0)/6.d0*cell_diam_av(i)**3*fixed_density
  enddo
  do trial=1,6
    kernel_coagulation=1.d-14
    if(trial<=3) then
      kernel_coagulation=0.d0;kernel_coagulation(1,1)=1.d-14
    endif
    dt=10.d0**(4*mod(trial-1,3));scram_coag_flux_dt=dt
    call nearest_rate(rn,rm,n,q)
    if(abs(sum(rn)+nearest_event_rate_sum)>1.d-12*max(nearest_event_rate_sum,1.d-30)) &
      error stop 'incorrect particle number loss'
    do s=1,2
      if(abs(sum(rm(:,s)))>1.d-12*max(sum(abs(rm(:,s))),1.d-30)) &
        error stop 'species mass not conserved'
    enddo
    if(any(n+dt*rn < -1.d-12*maxval(n))) error stop 'negative number'
    if(any(q+dt*rm < -1.d-12*maxval(q))) error stop 'negative mass'
  enddo
  print *, 'PASS: 6 coagulation mass/number/positivity cases'
end program
