!!-----------------------------------------------------------------------
!!     Copyright (C) 2003-2014, ENPC - INRIA - EDF R&D
!!     Author(s): Shupeng Zhu
!!
!!     This file is part of the Size Composition Resolved Aerosol Model (SCRAM), a
!!     component of the air quality modeling system Polyphemus.
!!
!!     Polyphemus is developed in the INRIA - ENPC joint project-team
!!     CLIME and in the ENPC - EDF R&D joint laboratory CEREA.
!!
!!     Polyphemus is free software; you can redistribute it and/or modify
!!     it under the terms of the GNU General Public License as published
!!     by the Free Software Foundation; either version 2 of the License,
!!     or (at your option) any later version.
!!
!!     Polyphemus is distributed in the hope that it will be useful, but
!!     WITHOUT ANY WARRANTY; without even the implied warranty of
!!     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
!!     General Public License for more details.
!!
!!     For more information, visit the Polyphemus web site:
!!     http://cerea.enpc.fr/polyphemus/
!!-----------------------------------------------------------------------
!!
!!     -- DESCRIPTION
!!    This is the main program for 0D simulation, it contains time
!!    evolution structure of SCRAM
!!-----------------------------------------------------------------------
PROGRAM SCRAM

  use Discretization
  use Condensation
  use eRedistribution
  use Initialization
  use Adaptstep
  use Resultoutput
  use CoefficientRepartition
  use CoeffRepartitionBoxmodel
  use Coagulation
  use Congregation
  use netcdf
  
  implicit none

  integer ::solver, n
  character (len=256) :: configuration_file!initial configure file
  character(len=3)::vchar
  double precision :: current_time,equilibrium_time,timestep_emis
  double precision :: timestep_coag,timestep_cond
  double precision :: cpu_t1,cpu_t2,cpu_step_t1,cpu_step_t2
  
  call cpu_time(cpu_t2)

  ! Initialisation: discretization and distribution  
  call getarg(1, configuration_file)!obtain the path of configuration file
  call read_discretization(configuration_file)!Read user configuration and initialization data
  call coeff_boxmodel_init()
  call Init_distribution()!initialize system data
  
  ! Check the validity of coagulation repartition coefficients
   if (with_coag.eq.1 .and. coeff_use_legacy_mode()) then
    call check_repart_coeff()
   endif

  call mass_conservation(concentration_mass,concentration_number,concentration_gas,total_mass)
  call coeff_record_timestep(0.d0)
      
  print*, "Calculation in progress..."
  ! Starts the simulation for solving the general dynamic equations of externally
  ! mixed aerosols by condensatio/evaporation, coagulation, nucleation, emissions.

  initial_time_splitting = 0.d0
  current_time=0.D0
  equilibrium_time=0.D0
  do while (equilibrium_time.lt.final_time)
    !in case of hybrid, fixed timestep for equilibrium bins
    if(ICUT.gt.1.and.ICUT.ne.N_size) then
      equilibrium_time=equilibrium_time+MIN(600.D0,final_time-equilibrium_time)! Equilibrium timestep
    else
      equilibrium_time=final_time
    endif
    
    do while (current_time.lt.equilibrium_time)
      ! Estimate the emission time step
      !!!!!!!!!!!!!!!!!!!! timestep_emis should be an argument of EmissionTimeStep
      call emission_step(equilibrium_time,current_time,timestep_emis)
      timestep_emis=MIN(timestep_emis,equilibrium_time-current_time)
      ! Solve emissions
      call emission(current_time,timestep_emis)!
      current_time=current_time+timestep_emis

		do while (initial_time_splitting.lt.current_time)
		  call coeff_mark_step_start()
		  call cpu_time(cpu_step_t1)
		
       ! Solve coagulation, condensation/evaporation and nucleation
       ! Compute the characteristic time step of each physical processes.
       !!!!!!!!!!!!!!!!!!!!! dt = timestep_splitting should be an argument of init_time_step!!!!!!
	call initstep(concentration_mass,concentration_number,concentration_gas,&
	timestep_coag,timestep_cond,timestep_splitting, current_time)
	timestep_cond=1.d0
	! Solve with the slowest process (coagulation).
	if (with_coag.eq.1) then
	  current_sub_time=initial_time_splitting
	  final_sub_time=current_sub_time+timestep_splitting
	  tag_coag=1
	  tag_cond=0
	  tag_nucl=0
	  sub_timestep_splitting=timestep_coag
	  solver=1            ! only etr for coagulation
	  call  processearo(solver)
	endif

	if(N_frac.gt.1) then
	  call redistribution_fraction()!fraction redistribution
	endif
	
        ! Solve the fastest process (condensation/evaporation and nucleation).
	if (with_cond+tag_nucl.gt.0) then
	  current_sub_time   = initial_time_splitting
	  final_sub_time  = current_sub_time + timestep_splitting
	  tag_coag   = 0
	  tag_cond   = with_cond
	  tag_nucl   = with_nucl
	  solver=dynamic_solver
	  sub_timestep_splitting=timestep_cond
	  call  processearo(solver)
	  call mass_conservation(concentration_mass,concentration_number,concentration_gas, total_mass)
	  ! Redistribute concentrations on fixed fraction sections
	  if(N_frac.gt.1) then
	    call redistribution_fraction()!fraction redistribution
	  endif
	  ! Redistribute concentrations on fixed size sections
	  if(redistribution_method.ge.2) then! .and.with_cond+with_coag.eq.2
	    call redistribution_size(redistribution_method)!size redistribution
	  endif
	endif

	if (with_cond+tag_nucl+with_coag.eq.0) then
	  final_sub_time  = initial_time_splitting + timestep_splitting!pure emission
	endif
        ! Check mass conservation
		call mass_conservation(concentration_mass,concentration_number,concentration_gas, total_mass)
		initial_time_splitting = final_sub_time
		call cpu_time(cpu_step_t2)
		call coeff_set_step_runtime(cpu_step_t2 - cpu_step_t1)
		call coeff_record_timestep(initial_time_splitting)
		n=initial_time_splitting*100/final_time
		write(vchar,'(i3)') n
	 write (*,'(A,A,A)') 'Progress: ', trim(adjustl(vchar)), '%'
      enddo
      
      !do C/E equilibrium after each emission
      if (with_cond.gt.0) then      
	if(ICUT.gt.1.and.ICUT.eq.N_size) then
	  call  bulkequi_inorg()!equlibrium for inorganic
	endif
	call  bulkequi_org()!equilibrium for organic
	! Check mass conservation
	call mass_conservation(concentration_mass,concentration_number,concentration_gas, total_mass)
	if(N_frac.gt.1) then
	  call redistribution_fraction()!fraction redistribution
	endif
	if(redistribution_method.ge.2) then! .and.with_cond+with_coag.eq.2
	  call redistribution_size(redistribution_method)!size redistribution
	endif
      endif
    
    enddo
    !compute equilibrium bins in case of hybrid methods
    if (with_cond.gt.0) then
      if(ICUT.gt.1.and.ICUT.ne.N_size) then
	call  bulkequi_inorg()!equlibrium for inorganic
      endif
      call mass_conservation(concentration_mass,&
      concentration_number,concentration_gas, total_mass)
      if(N_frac.gt.1) then
	call redistribution_fraction()!fraction redistribution
      endif
      if(redistribution_method.ge.2) then! .and.with_cond+with_coag.eq.2
	call redistribution_size(redistribution_method)!size redistribution
      endif
    endif
    
  enddo

  print *, ''

  ! Check mass conservation
  call mass_conservation(concentration_mass,concentration_number,&
  concentration_gas, total_mass)

  call cpu_time(cpu_t1)
  print*,'total run time:',cpu_t1-cpu_t2
  OPEN(UNIT=10,ACCESS='APPEND',FILE="RESULT/report.txt")
  write(unit=10,FMT=*)"Total run time:",cpu_t1-cpu_t2
  CLOSE(10)
  call write_result()
  
end PROGRAM SCRAM
