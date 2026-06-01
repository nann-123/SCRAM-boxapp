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
!!    This module contains methods to initialize mass and number concentration
!!-----------------------------------------------------------------------
MODULE Discretization
  use Initialization
  use CoefficientRepartition
  use CoeffRepartitionBoxmodel
  use Thermodynamics
  use Physicalbalance
  use eRedistribution
  
   implicit none
!system parameters related to 0D simulation   
    integer :: Tag_equi!tag of bulk equilibrium
    integer :: Tag_external
    integer :: init_scenario !Initial distribution conditions 1.hazy 2.urban 3.clear
    integer :: Tag_init!initial method
    integer :: kind_composition
    character (len=256) :: Coefficient_file!repartition coefficient file

    double precision, dimension(:), allocatable:: init_mass
    double precision, dimension(:), allocatable:: init_bin_number    
    double precision, dimension(:), allocatable :: gas_emis! vector storing Gas consentration (emission in 12 h) micm^3cm^-3
    double precision, dimension(:), allocatable :: number_init
    double precision, dimension(:), allocatable :: mass_init
    double precision, dimension(:), allocatable :: per_mass_init!initial percentage of each species within aerosol
    double precision, dimension(:), allocatable :: gas_init! vector storing initial gas consentration �m^3 cm^-3
    double precision, dimension(:), allocatable :: gas_emision_rate!micg/m^-3
    double precision,dimension(:), allocatable :: gas_mass_init
    double precision , dimension(:,:), allocatable :: emission_rate    
    double precision , dimension(:,:), allocatable :: init_bin_mass
    double precision , dimension(:,:), allocatable :: init_bin_emission
    
 contains
  subroutine read_discretization(configuration_file)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine reads input configuration file
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     configuration_file: directory of configuration file
!
!------------------------------------------------------------------------
    implicit none

    integer::k,i,j,s
    double precision::totv,totm
    character (len=256), intent(in) :: configuration_file
    integer :: kind_grid
    double precision,dimension(:), allocatable::diameter

      !initial pointer
    call pointer_initial()
    
    open(unit = 10, file = configuration_file, status = "old")
    read(10,*)Coefficient_file
    read(10,*)with_coag
    read(10,*)with_cond
    read(10,*)with_nucl,nucl_model
    read(10,*)sulfate_computation
    read(10,*)dynamic_solver,tag_thrm
    read(10,*)redistribution_method
    read(10,*)init_scenario
    read(10,*)tag_external
    read(10,*)Temperature
    Temperature=Temperature
    read(10,*)Pressure
    Pressure=Pressure
    read(10,*)Humidity
    Relative_Humidity=Humidity
    read(10,*)tagrho,fixed_density
    read(10,*)final_time
    read(10,*)dtmin
    read(10,*)Cut_dim!Tag_equi!ICUT
    read(10,*)N_sizebin, kind_grid
    read(10,*)N_groups
    read(10,*)N_species,Tag_init
    print*,"N_groups=",N_groups,"N_species=",N_species
    allocate(Index_groups(N_species))
    allocate(gas_emis(N_species))
    allocate(gas_init(N_species))
    allocate(List_species(N_species))
    allocate(per_mass_init(N_species))
    allocate(init_mass(N_species))
    init_mass=0.d0
    allocate(init_bin_mass(N_sizebin,N_species))
    allocate(init_bin_emission(N_sizebin,N_species))
    allocate(init_bin_number(N_sizebin))
    init_bin_emission=0.d0
    do s= 1, N_species!read initial information of each species, one species one line
      if(Tag_init.eq.0) then
	      read(10,*) List_species(s),Index_groups(s),gas_init(s),gas_emis(s),init_mass(s)
      else
	      read(10,*) List_species(s),Index_groups(s),gas_init(s),&
	      gas_emis(s),(init_bin_mass(k,s),k=1,N_sizebin)
	      do k=1,N_sizebin
	        init_mass(s)=init_mass(s)+init_bin_mass(k,s)
	      enddo
      endif
    enddo
    if(nucl_model.ne.5) then
      read(10,*) (init_bin_number(k),k=1,N_sizebin)
      do s=1,min(N_species,2)
	      read(10,*) (init_bin_emission(k,s),k=1,N_sizebin)
      enddo
    endif
    totm=0.d0
    do s = 1, N_species
      totm=totm+init_mass(s)
    enddo
    do s = 1, N_species
      per_mass_init(s)=init_mass(s)/totm!init percentage of each species
    enddo
    print*,"N_sizebin=",N_sizebin
    if(tagrho.eq.1) then
      totv=0.d0
      totm=100.d0
      do s=1,N_species
	  totv=totv+(totm*per_mass_init(s))/mass_density_aer(s)!�g/�m3
      enddo
      fixed_density=totm/totv!average density
      fixed_density_l= fixed_density * 1.0d+18
      print*,'fixed_density',fixed_density
    else
      mass_density_aer(EH2O)=fixed_density
      fixed_density_l= fixed_density * 1.0d+9 !�g/m3	       ! convert from kg/m3 to �g/�m3 or �g/m3
      fixed_density = fixed_density * 1.0d-9 !�g/�m3
      do s=1,N_species
	  mass_density_aer(s)=fixed_density!LMDL(4)!LMDL(List_species(s))
      enddo
      print*,'Fixed Density',fixed_density,fixed_density_l
    endif
    final_time = final_time *6.0d+1*6.0d+1!hour into second
    if(init_scenario.eq.1) then
      print*,'Initial Condition Hazy'
    elseif(init_scenario.eq.2) then
      print*,'Initial Condition Urban'
    else
      print*,'Initial Condition Clear'
    endif
    print*,'Method',dynamic_solver
    print*,'Cuting Diameter',Cut_dim
    print*,'Temperature',Temperature
    print*,'Pressure',Pressure
    print*,'Relative Humidity',Humidity
    print*,'Simulation Time',final_time,'s'
    print*,'Initial Time Step',timestep_splitting,'s'
    allocate(discretization_mass(N_sizebin+1))
    allocate(size_diam_av(N_sizebin))
    allocate(size_mass_av(N_sizebin))
    allocate(number_init(N_sizebin))
    allocate(mass_init(N_sizebin))
    allocate(diameter(N_sizebin+1))
    allocate(diam_bound(N_sizebin+1))
    allocate(size_sect(N_sizebin))

    ! diameter in �m
    if (kind_grid == 0) then
      read(10,*)dmin,dmax
      do k = 1,N_sizebin+1
	  diameter(k)= dmin * (dmax / dmin)**((k - 1) / dble(N_sizebin))
	  diam_bound(k) = diameter(k)
	  discretization_mass(k) = fixed_density * pi * diameter(k)**3 / 6.d0!diameter into mass
      enddo
    else
      read(10,*)(diameter(k),k=1,N_sizebin+1)
      do k = 1,N_sizebin+1
	  diam_bound(k) = diameter(k)
	  discretization_mass(k) = fixed_density * pi * diameter(k)**3 / 6.d0
      enddo
      print*,"bin bounds:",diam_bound
    endif

    do k =1,N_sizebin
    size_sect(k)=dlog10(diameter(k+1)/diameter(k))
    enddo

    do k= 1, N_sizebin
	size_diam_av(k)=dsqrt (diameter(k)*diameter(k+1))!average
	size_mass_av(k) = size_diam_av(k)**3 *fixed_density*pi/6.d0
    enddo
    read(10,*) kind_composition

    N_size = 0
    read(10,*)N_frac
    allocate(frac_bound(N_frac+1))
    if (kind_composition == 1) then
      call FracDiscretization!auto fraction discretization
    elseif(kind_composition == 0) then
      read(10,*)(frac_bound(k),k=1,N_frac+1)!set fraction bounds manully
      call FracDiscretization!auto fraction discretization
    endif

    allocate(concentration_index(N_size, 2))
    allocate(concentration_index_iv(N_sizebin, N_fracmax))

    j = 1
    do k = 1,N_sizebin
      do i = 1, N_fracmax
	  concentration_index(j, 1) = k
	  concentration_index(j, 2) = i
	  concentration_index_iv(k,i) = j
	  j = j + 1
      enddo
    enddo

    !calculate ICUT the corresponding cell index of the cuting diameter
    if(Cut_dim.gt.diam_bound(1)) then
      do k= 1,N_sizebin
	if(diam_bound(k).lt.Cut_dim.and.diam_bound(k+1).ge.Cut_dim) then
	  ICUT=concentration_index_iv(k,N_fracmax)
	endif
      enddo
    print*,'ICUT',ICUT,concentration_index(ICUT, 1)      
    else
    ICUT=0
    print*,'ICUT',ICUT
    endif

    close(10)

  end subroutine read_discretization

  subroutine FracDiscretization()
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine automatically computes particle compositions.
!     Information of particle compositions is saved under "INIT/fractions.txt"
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!------------------------------------------------------------------------
    implicit none

    double precision:: sumfrac
    integer,dimension(:), allocatable:: counter
    integer:: Nubvaild
    integer:: i,s,j,k,s1,rankk

    open(unit = 11, file = "INIT/fractions.txt")
    Nubvaild=0
    rankk=0
    allocate(counter(N_groups-1))
    !auto define the fraction bounds
    if (kind_composition == 1) then
      do i = 1, N_frac+1
	frac_bound(i)=dble(i-1)/N_frac
      enddo
    endif

    !calculate the maximum fraction combinations
    do i = 1, N_frac
      do s = 1, N_groups-1
	counter(s)=1!initial the counter
      enddo
      if(N_groups.gt.2) then
      ! when the index counter of second species reaches its top, move to the N_aerosol fraction bin of first species
	do while(counter(2).le.N_frac)!Traversal all the possible combination
	  sumfrac=frac_bound(i)!(i+1)!take the base fraction bounds of current bin of first species
	  do s =2, N_groups-1
	      rankk=rankk+1
	      j=counter(s)!the fraction bin index for species s
	      sumfrac=sumfrac+frac_bound(j)!(j+1)!calculate one possible combination
	  enddo
	  if (sumfrac.lt.1.d0) then
	    Nubvaild=Nubvaild+1!get one possible combination
	    write(unit=11,FMT=*) frac_bound(i), frac_bound(i+1)!for first species
	    do s=2, N_groups-1
	      j=counter(s)!write down possible combinations
	      write(unit=11,FMT=*) frac_bound(j), frac_bound(j+1)
	    enddo
	    write(unit=11,FMT=*) frac_bound(1), frac_bound(N_frac+1)!for last species
	  endif
	!when the second last species hasn't reaches its top,
	  if(counter(N_groups-1).le.N_frac) then
	    counter(N_groups-1)=counter(N_groups-1)+1!move the index of second last species
	  endif
	!!optimized rank method
	!![3,Ngroup_aer-1]
	  do s=3,N_groups-1!check every neighbor counter, form back to forward
	    j=N_groups+2-s
	    sumfrac=frac_bound(counter(j-1))+frac_bound(counter(j))
	    if(sumfrac.ge.1.d0) then
	      do s1=j,N_groups-1
		counter(s1)=1
	      enddo
		  counter(j-1)=counter(j-1)+1
	    endif
	  enddo
	enddo
      else!in case of only two/one species
	Nubvaild=N_frac
	do s=1, N_groups-1
	  j=counter(s)
	  write(unit=11,FMT=*) frac_bound(i), frac_bound(i+1)
	enddo
	write(unit=11,FMT=*) frac_bound(1), frac_bound(N_frac+1)
      endif
    enddo
    CLOSE(11)
    print*,"rank=",rankk

    N_fracmax=Nubvaild!get the N_fracmax
    allocate(discretization_composition(N_sizebin, N_fracmax, N_groups, 2))
    print*,'N_fracmax',N_fracmax
    do k = 1,N_sizebin!k is the number of bins
      N_fracmax = N_fracmax
      N_size = N_size + N_fracmax
    enddo

     open(unit = 11, file = "INIT/fractions.txt",status = "old")

    do i = 1, N_fracmax
      do s = 1, N_groups
         read(11,*)discretization_composition(1, i, s, 1), discretization_composition(1, i, s, 2)
      enddo
   enddo

    do k = 1,N_sizebin!k is the number of bins
      do i = 1, N_fracmax!N_fracmax is the number of fraction combination
	  do s = 1, N_groups
	    discretization_composition(k, i, s, 1) = discretization_composition(1, i, s, 1)!s is the tag of species and 1 is the mim fraction limit
	    discretization_composition(k, i, s, 2) = discretization_composition(1, i, s, 2)!2 is max fraction limit
	  enddo! Here the fraction distribution of other bins are the same as the first bin
      enddo
    enddo
    CLOSE(11)
  end subroutine  FracDiscretization
 
  subroutine Init_distribution()
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine initialize mass and number concentration based
!     on initialization methods indicate within configuration files.
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!------------------------------------------------------------------------   
    IMPLICIT NONE
    integer:: tag_file    
    integer :: j,k,i,j1,j2,Czero,f,s,jesp,g
    double precision::mass_frac(N_sizebin),numb_frac,binx_mass(N_sizebin)
    double precision::weight,mass_tmp,numb_tmp,ttmass
    double precision::tmp
    double precision::speciesfrac(N_aerosol,N_sizebin)
    double precision::mass_fine,mass_coarse,f_fine_coarse
    double precision::totalv,singlev,thdim,emw_tmp
    
    allocate(density_aer_bin(N_size))!
    allocate(density_aer_size(N_sizebin))!
    allocate(dqdt(N_size,N_aerosol))!
    allocate(cell_mass_av(N_size))!
    allocate(cell_diam_av(N_size))!
    allocate(wet_diameter(N_size))!
    allocate(wet_mass(N_size))!
    allocate(wet_volume(N_size))
    allocate(addm(N_aerosol))!
    allocate(concentration_inti(N_size,N_inside_aer))
    allocate(concentration_number(N_size))!
    allocate(concentration_number_tmp(N_size))!
    allocate(concentration_mass(N_size,N_aerosol))!
    allocate(concentration_mass_tmp(N_size,N_aerosol))!
    allocate(frac_grid(N_size,N_groups))!
    allocate(mass_total_grid(N_size))!
    allocate(total_mass(N_aerosol))
    allocate(total_aero_mass(N_aerosol))
    allocate(concentration_gas(N_aerosol))
    allocate(emission_rate(N_size,N_aerosol))
    allocate(gas_emision_rate(N_aerosol))
    allocate(gas_mass_init(N_aerosol))
    allocate(concentration_tmp1(N_sizebin,N_fracmax))!N_fracmax max possible fraction combinations
    allocate(kernel_coagulation(N_size,N_size))!!
    allocate(ce_kernal_coef(N_size,N_aerosol))
    allocate(Kelvin_effect_ext(N_size,N_aerosol))
    allocate(bin_mass(N_sizebin))
    allocate(bin_number(N_sizebin))
    allocate(rho_wet_cell(N_size))
    !statistic
    n_grow_nucl=0.d0
    n_grow_coag=0.d0
    m_grow_cond=0.d0
    n_emis=0.d0
    m_emis=0.d0
    bin_mass=0.d0
    bin_number=0.d0
    o_total_mass=0.d0
    record_time=0.d0
    density_aer_bin=0.d0
    density_aer_size=0.d0
    addm=0.d0
    mass_frac=0.d0
    ce_kernal_coef=0.d0
    Kelvin_effect_ext=1.d0
    concentration_inti=0.d0
    concentration_number=0.d0
    concentration_mass=0.d0
    gas_mass_init=0.d0
    concentration_gas=0.d0
    emission_rate=0.d0
    gas_emision_rate=0.d0
    total_aero_mass=0.d0
    total_mass=0.d0
    mass_tmp=0.d0
    numb_tmp=0.d0
    speciesfrac=1.d0!adjust mass distribution for different species
    mass_fine=0.d0
    mass_coarse=0.d0
!calculate the refferenced initial mass and number distribution of each bin
    call dist_init_mass_number(fixed_density_l)

  if(nucl_model.eq.5) then

  elseif(Tag_init.eq.0) then
!    compute the percentage of mass distribution
      do k=1,N_sizebin
      mass_tmp=mass_tmp+mass_init(k)
      if(diam_bound(k+1).lt.2.5d0) then
	mass_fine=mass_fine+mass_init(k)
      else
	mass_coarse=mass_coarse+mass_init(k)
      endif
    enddo

    f_fine_coarse=mass_fine/mass_coarse

    do k=1,N_sizebin
      mass_frac(k)=mass_init(k)/mass_tmp
    enddo

    ttmass=0.d0

     do s = 1, N_species
	ttmass=ttmass+init_mass(s)
     enddo

     if(tagrho.eq.1) then!modified the initial species mass distribution
      do k=1,N_sizebin
	if(init_scenario.eq.1) then
	thdim=1.d0
	elseif(init_scenario.eq.2) then
	thdim=2.d0
	elseif(init_scenario.eq.3) then
	thdim=0.7d0
	endif
	  if(diam_bound(k+1).lt.thdim) then
	    speciesfrac(ENa,k)=diam_bound(k+1)!no sea salt in fine mode
	    speciesfrac(ECl,k)=diam_bound(k+1)
	    speciesfrac(EMD,k)=diam_bound(k+1)
	    if(init_scenario.eq.1) then
	    speciesfrac(ESO4,k)=8.38d-1/diam_bound(k+1)!Hazy
	    speciesfrac(ENH4,k)=8.40d-1/diam_bound(k+1)!Hazy
	    speciesfrac(ENO3,k)=8.40d-1/diam_bound(k+1)!Hazy
	    elseif(init_scenario.eq.2) then
	    speciesfrac(ESO4,k)=3.64d-1/diam_bound(k+1)!urban
	    speciesfrac(ENH4,k)=3.64d-1/diam_bound(k+1)!urban
	    speciesfrac(ENO3,k)=3.64d-1/diam_bound(k+1)!urban
	    elseif(init_scenario.eq.3) then
	    speciesfrac(ESO4,k)=6.64d-1/diam_bound(k+1)!urban
	    speciesfrac(ENH4,k)=6.64d-1/diam_bound(k+1)!urban
	    speciesfrac(ENO3,k)=6.64d-1/diam_bound(k+1)!urban
	    endif
	  else
	    speciesfrac(ENa,k)=1.0d0+0.44d0*f_fine_coarse
	    speciesfrac(ECl,k)=1.0d0+0.44d0*f_fine_coarse
	    speciesfrac(EMD,k)=1.0d0+0.44d0*f_fine_coarse
	    if(init_scenario.eq.1) then
	    speciesfrac(ESO4,k)=8.38d-1/diam_bound(k+1)**2.d0!Hazy
	    speciesfrac(ENH4,k)=8.40d-1/diam_bound(k+1)**2.d0!Hazy
	    speciesfrac(ENO3,k)=8.40d-1/diam_bound(k+1)**2.d0!Hazy
	    elseif(init_scenario.eq.2) then
	    speciesfrac(ESO4,k)=3.64d-1/diam_bound(k+1)!**2.d0!urban
	    speciesfrac(ENH4,k)=3.64d-1/diam_bound(k+1)!**2.d0!urban
	    speciesfrac(ENO3,k)=3.64d-1/diam_bound(k+1)!**2.d0!urban
	    elseif(init_scenario.eq.3) then
	    speciesfrac(ESO4,k)=6.64d-1/diam_bound(k+1)!**2.d0!urban
	    speciesfrac(ENH4,k)=6.64d-1/diam_bound(k+1)!**2.d0!urban
	    speciesfrac(ENO3,k)=6.64d-1/diam_bound(k+1)!**2.d0!urban
	    endif
	  endif
      enddo
     endif

     numb_frac=ttmass/mass_tmp!scale factor of number distribution based on the scale
						  !between real total mass and refferenced mass
  endif
  !INIT gas concentration
     do s = 1, N_species
          jesp=List_species(s)
	gas_mass_init(jesp)=gas_init(s)!µg/m3
     enddo

  do i = 1, N_aerosol
     weight= molecular_weight_aer(i) * 1.D-6 ! g/mol
     call compute_gas_diffusivity(temperature, pressure, molecular_diameter(i), weight,collision_factor_aer(i), diffusion_coef(i))
     call compute_quadratic_mean_velocity(temperature, weight,quadratic_speed(i))
  end do

  do jesp=EBiA2D,EPOAhP
    accomodation_coefficient(jesp)=0.5D0
    emw_tmp = molecular_weight_aer(jesp) * 1.D-6 ! g/mol
    call COMPUTE_SATURATION_CONCENTRATION(temperature,&
      emw_tmp, vaporization_enthalpy(jesp), saturation_pressure(jesp), soa_sat_conc(jesp) )
  enddo
         tmp = 1.D0/RGAS * (1.D0 / Temperature - 1.D0 / 298.D0)
! the formula is inversed compared
! to that of vapore pressure because
! partition coefficient are inversely
! proportional to vapore pressure
         do i=1,nesp_pankow
            j=pankow_species(i)
            soa_part_coef(j) = Temperature / 298.D0& ! temperature dependency of partition coefficient
                * partition_coefficient(j) * DEXP(vaporization_enthalpy(j) * tmp)
         enddo
         tmp = 1.D0/RGAS * (1.D0 / Temperature - 1.D0 / 300.D0) !Reference at 300K for prymary organic aerosol
         do i=1,nesp_pom
            j=poa_species(i)
            soa_part_coef(j) = Temperature / 300.D0& ! temperature dependency of partition coefficient
                * partition_coefficient(j) * DEXP(vaporization_enthalpy(j) * tmp)
         enddo

	binx_mass=0.d0
	do k=1,N_sizebin
	  do s=1, N_species
	    binx_mass(k)=binx_mass(k)+init_bin_mass(k,s)
	  enddo
	enddo
!INIT mass and number distribution of each grid
  if(nucl_model.eq.5) then !specified for the valiation test
	if (N_frac.eq.1) then !internal mixing
	  do j=1,N_size!index of cells
	    concentration_mass(j,ESO4)=mass_init(j)/2.d0
	    concentration_mass(j,EBC)=mass_init(j)/2.d0
	    concentration_number(j)=number_init(j)
	  enddo
	else!external mixing
	  do j=1,N_size!index of cells
	      k= concentration_index(j, 1)!index of size bins
	      f= concentration_index(j, 2)!index of frac combinations
	      if(discretization_composition(k, f, 1,2).eq.1.d0) then
		  concentration_mass(j,ESO4)=mass_init(k)/2.d0
		  concentration_number(j)=number_init(k)/2.d0
	      endif
	      if(discretization_composition(k, f, 1,1).eq.0.d0) then
		  concentration_mass(j,EBC)=mass_init(k)/2.d0
		  concentration_number(j)=number_init(k)/2.d0
	      endif
	  enddo
	endif
  else !! nucl_model.NE.5
  if (N_frac.gt.1) then
	!case of external mixing
	  print*, "External mixing..."
	  do j=1,N_size!index of cells
	    do s=1, N_species!index of species
	      jesp=List_species(s)
	      g=Index_groups(s)
	      k= concentration_index(j, 1)!index of size bins
	      f= concentration_index(j, 2)!index of frac combinations
	      if(g.lt.N_groups) then
		    if(discretization_composition(k, f, g,2).eq.1.d0) then!checking top fraction (particles with single species)
	        if(Tag_init.eq.0) then
		        concentration_mass(j,jesp) = init_mass(s)*mass_frac(k)*speciesfrac(jesp,k)!mass_init(k)
		        concentration_number(j) = concentration_number(j)+number_init(k)*numb_frac*per_mass_init(s)
		      else
		        if(init_bin_emission(k,s).gt.0.d0) then
		          emission_rate(j,jesp)=init_bin_emission(k,s)
		        endif
		        if(tag_external.eq.1) then !!in case of external mixed initial condition
		          concentration_mass(j,jesp) = init_bin_mass(k,s)
		          concentration_number(j) = concentration_number(j)+init_bin_number(k)&
			          *init_bin_mass(k,s)/binx_mass(k)
		        endif
		      endif
		    endif
	      else
		    Czero=0
		    do g=1,N_groups-1
		      if(discretization_composition(k, f, g,1).gt.0.d0) then
		        Czero=1
		      endif
		    enddo
		    if(Czero.eq.0.d0) then
		      if(Tag_init.eq.0) then
		        concentration_mass(j,jesp) = init_mass(s)*mass_frac(k)*speciesfrac(jesp,k)!mass_init(k)
		        concentration_number(j) = concentration_number(j)+number_init(k)*numb_frac*per_mass_init(s)!/N_species
		      else
		        if(init_bin_emission(k,s).gt.0.d0) then
		        emission_rate(j,jesp)=init_bin_emission(k,s)
		        endif
		        if(tag_external.eq.1) then !!in case of external mixed initial condition
		        concentration_mass(j,jesp) = init_bin_mass(k,s)
		        concentration_number(j) = concentration_number(j)+init_bin_number(k)&
			        *init_bin_mass(k,s)/binx_mass(k)
		        endif
		      endif
		    endif
		    endif
	    enddo
	  enddo
  else
	!case of internal mixing N_size=N_sizebin
	  print*, "Internal mixing..."
	  do k=1,N_sizebin
	    do s=1,N_species
	      jesp=List_species(s)
	      if(Tag_init.eq.0) then
		      concentration_mass(k,jesp) = init_mass(s)*mass_frac(k)*speciesfrac(jesp,k)!mass_init(k)
	      else
		    if(init_bin_emission(k,s).gt.0.d0) then
		      emission_rate(k,jesp)=init_bin_emission(k,s)
		    endif
		    concentration_mass(k,jesp) = init_bin_mass(k,s)
	      endif
	    enddo
	    concentration_number(k)=init_bin_number(k)
	  enddo
  endif
  endif

  if(tag_external.eq.0.and.N_frac.gt.1) then!incase of internal mixed initial condition
    do k=1,N_sizebin
	  do s=1, N_species!index of species
	    jesp=List_species(s)
	    j=concentration_index_iv(k,1)
	    concentration_mass(j,jesp) = init_bin_mass(k,s)
	    concentration_number(j) = init_bin_number(k)
	  enddo
    enddo
  endif


  if(tag_external.eq.0) then!incase of internal mixed initial condition
    if(N_frac.gt.1) then
	    call redistribution_fraction()!fraction redistribution
    endif
  endif

  if(nucl_model.eq.5) then!specified for the valiation test
      
  elseif(Tag_init.eq.0) then!calculate number_init
	  do j=1,N_size
	    totalv=0.d0
	    k=concentration_index(j, 1)
	    singlev=size_diam_av(k)**3*pi/6.d0!µm3
	    do s=1,N_species
	      jesp=List_species(s)
	      totalv=totalv+concentration_mass(j,jesp)/mass_density_aer(s)!µm3
	    enddo
	    concentration_number(j)=totalv/singlev
	  enddo
  endif

      OPEN(UNIT=10,FILE="RESULT/report.txt")
      write(unit=10,FMT=*)"Discretization:"
    if(init_scenario.eq.1) then
	write(unit=10,FMT=*) 'Initial Condition Hazy'
     elseif(init_scenario.eq.2) then
	write(unit=10,FMT=*) 'Initial Condition Urban'
     else
	write(unit=10,FMT=*) 'Initial Condition Clear'
     endif
     write(unit=10,FMT=*) 'Condensation',with_cond,'Coagulation',with_coag,'Nucleation',tag_nucl,nucl_model
     write(unit=10,FMT=*) 'Method',dynamic_solver
     write(unit=10,FMT=*) 'Temperature',Temperature
     write(unit=10,FMT=*) 'Pressure',Pressure
     write(unit=10,FMT=*) 'Relative Humidity',Humidity
     write(unit=10,FMT=*) 'Simulation Time',final_time,'s'
     write(unit=10,FMT=*)"N_groups=",N_groups,"    N_species=",N_species,"    N_sizebin=",N_sizebin
      write(unit=10,FMT=*)"        jesp","    concentration_gas","        total_aero_mass",&
      "              total_mass","             gas_emision_rate"
      print*,"        jesp","    concentration_gas","        total_aero_mass",&
      "              total_mass","             gas_emision_rate"

      !calculate initial total_mass
      do s=1,N_species
	  jesp=List_species(s)
	  if(nucl_model.eq.5) then!specified for the valiation test
	    gas_emision_rate(ESO4)=2.29D-4!micg m^-3/s
	  else
	    gas_emision_rate(jesp)=gas_emis(s)!/final_time!micg m^-3/s
	  endif
	  do i=1,N_size
	  total_aero_mass(jesp)=total_aero_mass(jesp)+concentration_mass(i,jesp)
	  enddo
	  total_mass(jesp)=total_aero_mass(jesp)+gas_mass_init(jesp)!total mass is the sum of aerosol mass and gas mass
	  concentration_gas(jesp)=gas_mass_init(jesp)
	  write(unit=10,FMT=*)jesp,concentration_gas(jesp),total_aero_mass(jesp),total_mass(jesp),gas_emision_rate(jesp)
	  print*,jesp,concentration_gas(jesp),total_aero_mass(jesp),total_mass(jesp),gas_emision_rate(jesp)
	  o_total_mass=o_total_mass+total_aero_mass(jesp)
      enddo
	  write(unit=10,FMT=*)'initial total mass',o_total_mass
      CLOSE(10)

      !call  mass_to_number(concentration_mass,concentration_number)!test only, number will be recomputed based on mass and fixed diameters

      call  compute_average_diameter()

      call  compute_average_bin_diameter()

      call write_initial()
!calculate the wet diameter
    call compute_wet_mass_diameter(1,N_size,concentration_mass,concentration_number,&
	concentration_inti,wet_mass,wet_diameter,wet_volume,cell_diam_av)

  if (with_coag.eq.1) then !if coagulation

    do i=1,len(trim(Coefficient_file))!judge the input files
      if(Coefficient_file(i:i)==".")then
	  if(Coefficient_file(i+1:i+2)=="nc".or.Coefficient_file(i+1:i+2)=="NC") then
	    tag_file=1
	  elseif (Coefficient_file(i+1:i+3)=="bin".or.Coefficient_file(i+1:i+3)=="BIN") then
	    tag_file=0
	  elseif (Coefficient_file(i+1:i+3)=="txt".or.Coefficient_file(i+1:i+3)=="TXT") then
	    tag_file=2
	  else
	  print*,"Unsupported input file type!"
	  stop
	  endif
      endif
    enddo
    if (coeff_use_legacy_mode()) then
      print*,'Coefficient Repartition Database:',Coefficient_file
      call ReadCoefficient(Coefficient_file,tag_file) ! defined in ModuleCoefficientRepartition
    else
      print*,'Coefficient Repartition Prototype Mode:',trim(coeff_repartition_mode_name)
      print*,'Coefficient Cache Mode:',trim(coeff_cache_mode_name)
    endif
    !kernel_cagulation :

    call  COMPUTE_AIR_FREE_MEAN_PATH(Temperature,&
       Pressure, air_free_mean_path, viscosity)
     call  compute_average_diameter()
       do j1 = 1, N_size
       do j2 = 1, j1
	  call compute_bidisperse_coagulation_kernel(Temperature,air_free_mean_path,&
		     wet_diameter(j1),wet_diameter(j2),&
                     wet_mass(j1),wet_mass(j2), kernel_coagulation(j1,j2))
                                        ! symmetric kernels
         kernel_coagulation(j2,j1)=kernel_coagulation(j1,j2)
       enddo
  enddo
  endif

  end subroutine Init_distribution

  subroutine dist_init_mass_number(ro)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine initialize mass and number concentration based
!     on classic scenarios (Urban, Hazy and Clear).
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!     ro: Aerosol density(�g/m^3)
!------------------------------------------------------------------------   
    IMPLICIT NONE

    !CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
    !  DONNEES :
    !
    !  MEAN DIAMETER :      DN, DA, DC in m3
    !  STANDARD DEVIATION : SN, SA, SC
    !  TOTAL VOLUME  :      VN, VA, VC in m3/m3
    !
    !  rho en microgramme/m3
    !  vol en m3/m3
    !  Q en microgramme/m3
    !  N en nb de particules/m3
    !CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC

    integer :: i,k
    double precision, DIMENSION(N_sizebin) :: d
    double precision, DIMENSION(101) :: dbound_ref
    double precision, DIMENSION(100) :: d_ref, vol_ref, mass_ref, nb_ref
    double precision :: raison_ref, size_sect_ref

    double precision :: dn, da, dc, sn, sa, sc, vn, va, vc, nn, na, nc
    double precision :: vol_n, vol_a, vol_c, nb_n, nb_a, nb_c,ro
    double precision :: a, b, c, dn_n, dn_a, dn_c, anb, bnb, cnb

    !ro=1.8D12!µg/m3
    !print*,'ro',ro
    if (init_scenario == 1) then
       ! hazy
       dn = 0.044D-6
       da = 0.24D-6
       dc = 6D-6
       sn = 1.2D0
       sa = 1.8D0
       sc = 2.2D0
       vn = 0.09D-12
       va = 5.8D-12
       vc = 25.9D-12
    elseif(init_scenario == 2) then
       ! urban
       dn = 0.038D-6
       da = 0.32D-6
       dc = 5.7D-6
       sn = 1.8D0
       sa = 2.16D0
       sc = 2.21D0
       vn = 0.63D-12
       va = 38.4D-12
       vc = 30.8D-12
    elseif(init_scenario == 3) then
       ! clear
       dn = 0.03D-6
       da = 0.2D-6
       dc = 6D-6
       sn = 1.8D0
       sa = 1.6D0
       sc = 2.2D0
       vn = 0.03D-12
       va = 1D-12
       vc = 5D-12
    endif

    !CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
    ! Sectionnel NB
    !CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC

      do i = 1,N_sizebin
         d(i) = size_diam_av(i) * 1.d-6 !en m
         number_init(i) = 0d0
      enddo

	dn_n = 10D0**(DLOG10(dn) - 3D0*DLOG(10D0)*((DLOG10(sn)**2D0)))
	dn_a = 10D0**(DLOG10(da) - 3D0*DLOG(10D0)*((DLOG10(sa)**2D0)))
	dn_c = 10D0**(DLOG10(dc) - 3D0*DLOG(10D0)*((DLOG10(sc)**2D0)))

	nn = vn * 6D0 / (PI*(dn_n**3D0)*DEXP(4.5D0*(DLOG(sn)**2D0)))
	na = va * 6D0 / (PI*(dn_a**3D0)*DEXP(4.5D0*(DLOG(sa)**2D0)))
	nc = vc * 6D0 / (PI*(dn_c**3D0)*DEXP(4.5D0*(DLOG(sc)**2D0)))

    if (N_sizebin .gt. 200) then

       do k = 1,N_sizebin

          a = (vn/(DSQRT(2D0*PI)*DLOG10(sn))) * &
               DEXP((-5D-1)* (DLOG10(d(k)/(dn))/DLOG10(sn))**2D0)
          b = (va/(DSQRT(2D0*PI)*DLOG10(sa))) * &
               DEXP((-5D-1)* (DLOG10(d(k)/(da))/DLOG10(sa))**2D0)
          c = (vc/(DSQRT(2D0*PI)*DLOG10(sc))) * &
               DEXP((-5D-1)* (DLOG10(d(k)/(dc))/DLOG10(sc))**2D0)
	  !print*,'s',size_sect(k)
          mass_init(k) = ro * (a + b + c) * size_sect(k)

          anb = (nn/(DSQRT(2D0*PI)*DLOG10(sn))) * &
               DEXP((-5D-1)* (DLOG10(d(k)/(dn_n))/DLOG10(sn))**2D0)
          bnb = (na/(DSQRT(2D0*PI)*DLOG10(sa))) * &
               DEXP((-5D-1)* (DLOG10(d(k)/(dn_a))/DLOG10(sa))**2D0)
          cnb = (nc/(DSQRT(2D0*PI)*DLOG10(sc))) * &
               DEXP((-5D-1)* (DLOG10(d(k)/(dn_c))/DLOG10(sc))**2D0)
          number_init(k) = (anb + bnb + cnb)*size_sect(k)

       enddo

    else

    !CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
    !   continuous distribution of initial mass and number with 100 dots * N_sizebin
    !CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
       do k = 1,N_sizebin
        mass_init(k)=0
        number_init(k)=0
	dbound_ref(1) = diam_bound(k)*1D-6
	dbound_ref(101) = diam_bound(k+1)*1D-6
	raison_ref=(dbound_ref(101)/dbound_ref(1)) &
         **(1D0/DFLOAT(100))
	size_sect_ref = (DLOG10(dbound_ref(101)/dbound_ref(1))) &
         /DFLOAT(100)

	do i = 2,100
	  dbound_ref(i) = dbound_ref(i-1) * raison_ref
	enddo

	do i = 1,100
	  d_ref(i) = DSQRT(dbound_ref(i) * dbound_ref(i + 1))
	enddo

	do i = 1,100

	  vol_n = (vn/(DSQRT(2D0*PI)*DLOG10(sn))) * &
		DEXP((-5D-1)*((DLOG10(d_ref(i)/dn)/DLOG10(sn))**2D0))
	  vol_a = (va/(DSQRT(2D0*PI)*DLOG10(sa))) * &
		DEXP((-5D-1)*((DLOG10(d_ref(i)/da)/DLOG10(sa))**2D0))
	  vol_c = (vc/(DSQRT(2D0*PI)*DLOG10(sc))) * &
		DEXP((-5D-1)*((DLOG10(d_ref(i)/dc)/DLOG10(sc))**2D0))

	  vol_ref(i) = vol_n + vol_a + vol_c

	  mass_ref(i) =  vol_ref(i) * size_sect_ref * ro

	  nb_n = (nn/(DSQRT(2D0*PI)*DLOG10(sn))) * &
		DEXP((-5D-1)*((DLOG10(d_ref(i)/dn_n)/DLOG10(sn))**2D0))
	  nb_a = (na/(DSQRT(2D0*PI)*DLOG10(sa))) * &
		DEXP((-5D-1)*((DLOG10(d_ref(i)/dn_a)/DLOG10(sa))**2D0))
	  nb_c = (nc/(DSQRT(2D0*PI)*DLOG10(sc))) * &
		DEXP((-5D-1)*((DLOG10(d_ref(i)/dn_c)/DLOG10(sc))**2D0))

	  nb_ref(i) = (nb_n + nb_a + nb_c)* size_sect_ref

	enddo
!integration
          do i = 1, 100
	  mass_init(k) = mass_init(k)+ mass_ref(i)
	  number_init(k) = number_init(k)+ nb_ref(i)
          enddo
!check new diameter
	  !diam=(( mass_init(k)* 6D0)/(PI * ro * number_init(k)))**(1D0/3D0)
       enddo

     endif

  end subroutine dist_init_mass_number
  
  subroutine write_initial()
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine saves initial condition of the simulation
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!------------------------------------------------------------------------   
     implicit none

    integer::k,i,s,j,f,g,jesp
    double precision :: some
    character( len = 2 ) :: cTemp
    double precision, dimension(:,:),allocatable:: concentration_tmp1,concentration_tmp2
    double precision, dimension(:,:),allocatable::concentration_tmp3
    double precision, dimension(:,:),allocatable::massf1,numbf1
    double precision, dimension(:,:),allocatable::mass_group

    allocate(concentration_tmp1(N_sizebin,N_fracmax))
    allocate(concentration_tmp2(N_sizebin,N_fracmax))
    allocate(concentration_tmp3(N_sizebin,N_fracmax))
    allocate(mass_group(N_sizebin,N_groups))

    concentration_tmp1=0.d0
    concentration_tmp2=0.d0
    concentration_tmp3=0.d0

      do j=1, N_size
	k= concentration_index(j, 1)!k for nb
	i= concentration_index(j, 2)!here i=1 for internal i for nc_max
	concentration_tmp1(k,i)=concentration_number(j)
	do s=1,N_species
	    jesp=List_species(s)
	    concentration_tmp2(k,i)=concentration_tmp2(k,i)+concentration_mass(j,jesp)
	    concentration_tmp3(k,i)=concentration_tmp3(k,i)+concentration_mass(j,jesp)/density_aer_bin(j)
	enddo
      enddo

      if(N_size.eq.N_sizebin) then
      OPEN(UNIT=10,FILE="INIT/file_conc_aer_init")
      do j=1,N_size
	do jesp=1,N_aerosol-1
	  write(unit=10,FMT=*) concentration_mass(j,jesp),jesp,j
	enddo
      enddo
      CLOSE(10)
      OPEN(UNIT=10,FILE="INIT/file_conc_init")
      do jesp=1,N_aerosol-1
	  write(unit=10,FMT=*) concentration_gas(jesp),jesp
      enddo
      CLOSE(10)
      OPEN(UNIT=10,FILE="INIT/file_conc_emission")
      do j=1,N_size
	do jesp=1,N_aerosol-1
	  write(unit=10,FMT=*) emission_rate(j,jesp),jesp,j
	enddo
      enddo
      endif

      OPEN(UNIT=10,FILE="RESULT/number_init.txt")
      do k=1,N_sizebin
	some=0d0
	do i=1,N_fracmax
	    some=some +concentration_tmp1(k,i)
	enddo
	  write(unit=10,FMT=*) size_diam_av(k),(concentration_tmp1(k,i)/size_sect(K),i=1,N_fracmax),&
	      some/size_sect(K)
      enddo
      CLOSE(10)

    OPEN(UNIT=10,FILE="RESULT/mass_init.txt")
      do k=1,N_sizebin
	some=0d0
	do i=1,N_fracmax
	some=some +concentration_tmp2(k,i)
	enddo
	write(unit=10,FMT=*) size_diam_av(k),(concentration_tmp2(k,i)/size_sect(k),i=1,N_fracmax), some/size_sect(k)
      enddo
    CLOSE(10)

      OPEN(UNIT=10,FILE="RESULT/cocentration_number_init.txt")
      do k=1,N_sizebin
	some=0d0
	do i=1,N_fracmax
	  some=some +concentration_tmp1(k,i)
	enddo
	  write(unit=10,FMT=*) size_diam_av(k),some/size_sect(k)!part/cm^3
      enddo
      CLOSE(10)


      OPEN(UNIT=10,FILE="RESULT/cocentration_mass_init.txt")
      do k=1,N_sizebin
	some=0d0
	do i=1,N_fracmax
	  some=some +concentration_tmp2(k,i)
	enddo
	  write(unit=10,FMT=*) size_diam_av(k),some/size_sect(k)!µg/cm^3
      enddo
      CLOSE(10)

      OPEN(UNIT=10,FILE="RESULT/cocentration_volume_init.txt")
      do k=1,N_sizebin
	some=0d0
	do i=1,N_fracmax
	  some=some +concentration_tmp3(k,i)
	enddo
	write(unit=10,FMT=*) size_diam_av(k),some/size_sect(k)
      enddo
      CLOSE(10)

          if(N_species.gt.1) then
    !!write volume results of each size bin for each species
    do s=1,N_species
        jesp=List_species(s)
	write( cTemp,'(i2)' ) s
	OPEN(UNIT=10,FILE='RESULT/volume_init_s' // trim(adjustl( cTemp )) // '.txt')
	do k=1,N_sizebin
	  some=0d0
	  do i=1,N_fracmax
	  j=concentration_index_iv(k,i)
	  some=some +concentration_mass(j,jesp)/mass_density_aer(s)
	  enddo
	    write(unit=10,FMT=*) size_diam_av(k) , some/size_sect(k)
	enddo
	CLOSE(10)
      enddo
    do s=1,N_species
	jesp=List_species(s)
	write( cTemp,'(i2)' ) s
	OPEN(UNIT=10,FILE='RESULT/mass_init_s' // trim(adjustl( cTemp )) // '.txt')
	do k=1,N_sizebin
	  some=0d0
	  do i=1,N_fracmax
	  j=concentration_index_iv(k,i)
	  some=some +concentration_mass(j,jesp)
	  enddo
	    write(unit=10,FMT=*) size_diam_av(k) , some/size_sect(k)
	enddo
	CLOSE(10)
      enddo
    endif

      if(N_species.gt.2.and.kind_composition.eq.1) then
      allocate(massf1(N_sizebin,N_frac))
      allocate(numbf1(N_sizebin,N_frac))
      do g=1,N_groups!this is for the result of 3D representation
	do k = 1,N_sizebin!k is the number of bins
	  do f=1,N_frac
	    massf1(k,f)=0.d0
	    numbf1(k,f)=0.d0
	  enddo
	enddo
	do k = 1,N_sizebin!k is the number of bins
	  do f=1,N_frac
	    do i = 1, N_fracmax!N_fracmax is the number of fraction combination
	      if(discretization_composition(k, i, g, 2).eq.frac_bound(f+1)) then
		j=concentration_index_iv(k,i)
		do jesp=1,N_aerosol
		  massf1(k,f)=massf1(k,f)+concentration_mass(j,jesp)
		enddo
		  numbf1(k,f)=numbf1(k,f)+concentration_number(j)
	      endif
	    enddo
	  enddo
	enddo
	write( cTemp,'(i2)' ) g
	OPEN(UNIT=10,FILE='RESULT/mass_init_sp' // trim(adjustl( cTemp )) // '.txt')
	  do k=1,N_sizebin
	  some=0d0
	  do f=1,N_frac
	  some=some +massf1(k,f)
	  enddo
	    write(unit=10,FMT=*) size_diam_av(k),(massf1(k,f)/size_sect(k),f=1,N_frac), some*1d-06/size_sect(k)
	enddo
	CLOSE(10)

	OPEN(UNIT=10,FILE='RESULT/number_init_sp' // trim(adjustl( cTemp )) // '.txt')
	  do k=1,N_sizebin
	  some=0d0
	  do f=1,N_frac
	  some=some +numbf1(k,f)
	  enddo
	    write(unit=10,FMT=*) size_diam_av(k),(numbf1(k,f)/size_sect(k),f=1,N_frac), some*1d-06/size_sect(k)
	enddo
	CLOSE(10)
      enddo
    endif

     !in case of group mode, save the mass of each group in each size bin
    if(N_groups.ne.N_species) then
      do k=1,N_sizebin
	do g=1,N_groups
	  mass_group(k,g)=0.d0
	enddo
	do i=1,N_fracmax
	  j=concentration_index_iv(k,i)
	  do s=1,N_species
	    jesp=List_species(s)
	    g=Index_groups(s)
	    mass_group(k,g)=mass_group(k,g)+concentration_mass(j,jesp)
	  enddo
	enddo
      enddo

       do g=1,N_groups
	write( cTemp,'(i2)' ) g
	OPEN(UNIT=10,FILE='RESULT/mass_init_g' // trim(adjustl( cTemp )) // '.txt')
	do k=1,N_sizebin
	    write(unit=10,FMT=*) size_diam_av(k) , mass_group(k,g)/size_sect(k)
	enddo
	CLOSE(10)
      enddo
    endif

 end subroutine write_initial


  subroutine emission(current_time,time_step)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine adds the emission into aerosol and gas phase
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     current_time: current time when emission start(s)
!     time_step: emission time step(s)
!
!------------------------------------------------------------------------
    implicit none

    integer::j,jesp,k
    double precision::qemis,current_time,time_step
    double precision::time_emis,emis_dt
    if(nucl_model.eq.5) then
    time_emis=60.d0*60.d0*12.d0
    else
    time_emis=2.64376d3
    endif
    !print*,'emis'
    if((current_time+time_step).lt.time_emis) then
      emis_dt=time_step
    else
      emis_dt=time_emis-current_time
      if(emis_dt.lt.0.d0) emis_dt=0.d0
    endif

      !for non C/E species
    do j=1,N_size
      k=concentration_index(j, 1)
      do jesp=EMD,EBC
	if(emission_rate(j,jesp).gt.0.d0) then
	  if(concentration_mass(j,jesp).ne.concentration_mass(j,jesp)) then
	    print*,j,jesp,concentration_mass(j,jesp),'emission 1'
	  endif
	    qemis=emission_rate(j,jesp)*emis_dt!some precision will be lost due to the different maganitude between concentration_mass and qemis
	    !print*,'current_sub_time',current_time,time_step
	  concentration_mass(j,jesp)=concentration_mass(j,jesp)+qemis
	  concentration_number(j)=concentration_number(j)+qemis/size_mass_av(k)!cell_mass_av(j)
	  n_emis=n_emis+qemis/size_mass_av(k)
	  m_emis=m_emis+qemis
	endif
      enddo
    enddo

    do jesp=EMD,EBC
      total_aero_mass(jesp)=0.d0
    enddo

    do j=1,N_size
      do jesp=EMD,EBC
	if(concentration_mass(j,jesp).ne.concentration_mass(j,jesp)) then
	    print*,j,jesp,concentration_mass(j,jesp),'emission 2'
	    stop
	  endif
	total_aero_mass(jesp)=total_aero_mass(jesp)+concentration_mass(j,jesp)
	total_mass(jesp)=total_aero_mass(jesp)
      enddo
    enddo

	!for C/E species
    do jesp=ENA,N_aerosol
      concentration_gas(jesp)=concentration_gas(jesp)+gas_emision_rate(jesp)*emis_dt
      total_mass(jesp)=total_mass(jesp)+gas_emision_rate(jesp)*emis_dt
    enddo
  end subroutine emission

  subroutine emission_step(t_total,current_time,time_step)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine computes emission time step based on
!     emission rate and background concentrations
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     current_time: current time when emission start(s)
!     t_total: maximum time limitation(s)
!
!     -- OUTPUT VARIABLES
!
!     time_step: emission time step(s)
!
!------------------------------------------------------------------------
    implicit none

    integer::j,jesp,k
    double precision::current_time,time_step
    double precision::tscale,t_total

    !for non C/E species
    time_step=final_time
    if(with_coag.eq.1.and.current_time.lt.2.64376d3) then
      tscale=0.d0
      do j=1,N_size
	k=concentration_index(j, 1)
	do jesp=EMD,EBC
	  if(concentration_mass(j,jesp)*emission_rate(j,jesp).gt.0.d0) then
	    tscale=concentration_mass(j,jesp)/emission_rate(j,jesp)
	    time_step=DMIN1(time_step,tscale)
	  endif
	enddo
      enddo
    endif
	      !for C/E species
    if (with_cond+tag_nucl.gt.0.and.current_time.lt.2.64376d3) then
      do jesp=ENA,N_aerosol
	 if(gas_emision_rate(jesp)*total_aero_mass(jesp).gt.0.d0) then
	    tscale=total_aero_mass(jesp)/gas_emision_rate(jesp)
	    time_step=DMIN1(time_step,tscale)
	 endif
      enddo
    endif

    time_step=DMIN1(time_step,t_total-current_time)
    if(time_step.eq.0.d0) stop
  end subroutine emission_step

end MODULE Discretization
