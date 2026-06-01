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
!!    This module contains methods for simulation result output
!!-----------------------------------------------------------------------
Module Resultoutput
  use Discretization
  use Initialization
  implicit none
contains

  subroutine write_result()
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine save simulation results into *.txt files
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!------------------------------------------------------------------------
    implicit none
    
    integer::k,i,s,j,f,s2,g,jesp
    double precision :: some,mean,std,val,frac
    character( len = 2 ) :: cTemp
    double precision::mass_inits(N_inside_aer)!total mass of internal species
    double precision, dimension(:,:),allocatable:: concentration_tmp
    double precision, dimension(:,:),allocatable:: concentration_tmp2
    double precision, dimension(:,:),allocatable:: concentration_water
    double precision, dimension(:,:),allocatable::concentration_tmp3
    double precision, dimension(:,:),allocatable::massf1,numbf1
    double precision, dimension(:,:),allocatable::mass_group

    allocate(concentration_water(N_sizebin,N_fracmax))
    allocate(concentration_tmp(N_sizebin,N_fracmax))
    allocate(concentration_tmp2(N_sizebin,N_fracmax))
    allocate(concentration_tmp3(N_sizebin,N_fracmax))
    allocate(mass_group(N_sizebin,N_groups))
    print*,'N_fracmax',N_fracmax
    mass_inits=0d0
    concentration_tmp2=0d0
    concentration_tmp3=0d0
    concentration_water=0d0
    total_water=0.d0
    do j=1, N_size
      k= concentration_index(j, 1)
      i= concentration_index(j, 2)
      total_water=total_water+concentration_mass(j,EH2O)
      if(N_frac.eq.1) then
	k=j
	concentration_index(j, 1)=j
      endif
      concentration_water(k,i)=concentration_water(k,i)+&
      concentration_mass(j,EH2O)
      do s=1,N_species
	jesp=List_species(s)
	concentration_tmp2(k,i)=concentration_tmp2(k,i)+&
	concentration_mass(j,jesp)
	concentration_tmp3(k,i)=concentration_tmp3(k,i)+&
	concentration_mass(j,jesp)/density_aer_bin(j)
      enddo
    enddo
    do j=1,N_size
     do jesp=1,N_inside_aer
       mass_inits(jesp)=mass_inits(jesp)+concentration_inti(j,jesp)
      enddo
    enddo
    
    OPEN(UNIT=10,ACCESS='APPEND',FILE="RESULT/report.txt")

    write(unit=10,FMT=*) "Results: total_water",total_water
    write(unit=10,FMT=*) "        jesp","    concentration_gas","        total_aero_mass",&
    "              total_mass","             gas_emision_rate"
    print*,"        jesp","    concentration_gas","        total_aero_mass",&
    "              total_mass"
    do s=1,N_species
	    jesp=List_species(s)
	    write(unit=10,FMT=*) jesp,concentration_gas(jesp),total_aero_mass(jesp),total_mass(jesp)
	    print*,jesp,concentration_gas(jesp),total_aero_mass(jesp),total_mass(jesp)
    enddo
    write(unit=10,FMT='(2(A10,1X,ES15.6),A10,1X,F15.6,A10,1X,ES15.6)') "Nub Nucl",n_grow_nucl,&
            "Nub Coag",n_grow_coag,"Mass Cond",m_grow_cond,"n_emis",n_emis
    write(unit=10,FMT=*) 'm_emis',m_emis,'inital total mass',o_total_mass
    print*,"Nub Nucl",n_grow_nucl,'Nub Coag',n_grow_coag,&
    'Mass Cond',m_grow_cond,'n_emis',n_emis
    print*,'m_emis',m_emis,'inital total mass',o_total_mass
    CLOSE(10)
    
    print*,"total_water",total_water

    if(redistribution_method.lt.2.and.with_cond.eq.1) then
      call compute_average_bin_diameter()
    endif
      
    OPEN(UNIT=10,FILE="RESULT/result_mass_inter.txt")
    do jesp=1,N_inside_aer
      write(unit=10,FMT=*)jesp,mass_inits(jesp)
    enddo
    CLOSE(10)
    
    OPEN(UNIT=10,FILE="RESULT/result_inter.bin")
    do j=1,N_size
      do jesp=1,N_inside_aer
        write(unit=10,FMT=*)j,jesp,concentration_inti(j,jesp)
      enddo
    enddo
    CLOSE(10)
    
    OPEN(UNIT=10,FILE="RESULT/result_mass.bin")
    do j=1,N_size
      do jesp=1,N_aerosol
        write(unit=10,FMT=*)j,jesp,concentration_mass(j,jesp)
      enddo
    enddo
    CLOSE(10)
 
    OPEN(UNIT=10,FILE="RESULT/result_number.bin")
    do j=1,N_size
      write(unit=10,FMT=*)j,concentration_number(j)
    enddo
    CLOSE(10)
 
    if(redistribution_method.lt.2) then
      size_sect (1)=dlog10(size_diam_av(2)/size_diam_av(1))
      if(size_sect (1).lt.0.d0) then
	      size_sect (1)=-size_sect (1)
      endif
      do i=2,N_sizebin-1
	      some=dlog10(size_diam_av(i+1)/size_diam_av(i-1))/2d0
	      if(some.lt.0.d0)then
	        some=-some
	      endif
	      size_sect (i)=some!dabs(some)
      enddo
      if(size_diam_av(N_sizebin)/size_diam_av(N_sizebin-1).ne.1.d0) then
	      size_sect (N_sizebin)=dlog10(size_diam_av(N_sizebin)/size_diam_av(N_sizebin-1))
      else
	      size_sect (N_sizebin)=size_sect (N_sizebin-1)
      endif
    endif

    OPEN(UNIT=10,FILE="RESULT/mass_result.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
        some=some +concentration_tmp2(k,i)
      enddo
	    write(unit=10,FMT=*) size_diam_av(k),(concentration_tmp2(k,i)/size_sect(k),&
	     i=1,N_fracmax), some/size_sect(k)
    enddo
    CLOSE(10)
    
    OPEN(UNIT=10,FILE="RESULT/fraction.txt")
    do k=1,N_sizebin
!! liu 
      DO i=1,N_fracmax
        IF (concentration_tmp2(k,i)<=0.d0) concentration_tmp2(k,i)=1.d-30
      ENDDO
!!
      write(unit=10,FMT=*) size_diam_av(k),&
	     (concentration_mass(concentration_index_iv(k,i),ESO4)&
	      /concentration_tmp2(k,i),i=1,N_fracmax)
    enddo      
    CLOSE(10)

    OPEN(UNIT=10,FILE="RESULT/mean_fraction_std.txt")
    do k=1,N_sizebin
      some=0d0
      val=0.d0
      mean=0.d0
      std=0.d0
      do i=1,N_fracmax
	j=concentration_index_iv(k,i)
	if(concentration_number(j).gt.0.d0) then
	  frac=concentration_mass(j,ESO4)/concentration_tmp2(k,i)
	  some=some +frac*concentration_number(j)
	  !print*,k,i,frac,concentration_number(j)
	  val=val+concentration_number(j)!get one sample
	endif
      enddo
      mean=some/val
      IF (val .le. 0.d0) mean=0.d0 !! liu
      some=0d0
      do i=1,N_fracmax
	j=concentration_index_iv(k,i)
	if(concentration_number(j).gt.0.d0) then
	  frac=concentration_mass(j,ESO4)/concentration_tmp2(k,i)
	  some=some +concentration_number(j)*((frac-mean)**2.d0)
	endif
      enddo
      std=(some/val)**0.5d0
      IF (val .le. 0.d0) std=0.d0  !! liu
      write(unit=10,FMT=*) size_diam_av(k),mean,std
    enddo
    CLOSE(10)

    OPEN(UNIT=10,FILE="RESULT/mass_result_o.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
        IF (concentration_tmp2(k,i)<=1.d-20) concentration_tmp2(k,i)=0.d0
	      some=some +concentration_tmp2(k,i)
      enddo
      write(unit=10,FMT=*) size_diam_av(k),(concentration_tmp2(k,i),&
	    i=1,N_fracmax), some
    enddo
    CLOSE(10)    
    OPEN(UNIT=10,FILE="RESULT/mass_result_sbin.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
	      some=some +concentration_tmp2(k,i)
      enddo
      write(unit=10,FMT=*) size_diam_av(k), some/size_sect(k)
    enddo
    CLOSE(10)

    OPEN(UNIT=10,FILE="RESULT/mass_water_sbin.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
	      some=some +concentration_water(k,i)
      enddo
      write(unit=10,FMT=*) size_diam_av(k),some/size_sect(k)
    enddo
    CLOSE(10)

    OPEN(UNIT=10,FILE="RESULT/mass_water.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
	      some=some +concentration_water(k,i)
      enddo
      write(unit=10,FMT=*) size_diam_av(k),(concentration_water(k,i)/size_sect(k),&
	  i=1,N_fracmax), some/size_sect(k)
    enddo
    CLOSE(10)

    OPEN(UNIT=10,FILE="RESULT/volume_result.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
	      some=some +concentration_tmp3(k,i)
      enddo
      write(unit=10,FMT=*) size_diam_av(k),(concentration_tmp3(k,i)/size_sect(k),&
	i=1,N_fracmax) , some/size_sect(k)
    enddo
    CLOSE(10)
    
    OPEN(UNIT=10,FILE="RESULT/volume_result_o.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
	      some=some +concentration_tmp3(k,i)
      enddo
      write(unit=10,FMT=*) size_diam_av(k),(concentration_tmp3(k,i),&
	i=1,N_fracmax) , some
    enddo
    CLOSE(10)       
    
    OPEN(UNIT=10,FILE="RESULT/volume_result_sbin.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
	      some=some +concentration_tmp3(k,i)
      enddo
      write(unit=10,FMT=*) size_diam_av(k), some/size_sect(k)
    enddo
    CLOSE(10)

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
		do s2=1,N_species
		  massf1(k,f)=massf1(k,f)+concentration_mass(j,s2)
		enddo
		  numbf1(k,f)=numbf1(k,f)+concentration_number(j)
	      endif
	    enddo
	  enddo
	enddo
	write( cTemp,'(i2)' ) g
	OPEN(UNIT=10,FILE='RESULT/mass_result_sp' // trim(adjustl( cTemp )) // '.txt')
	do k=1,N_sizebin
	  some=0d0
	  do f=1,N_frac
	    some=some +massf1(k,f)
	  enddo
	  write(unit=10,FMT=*) size_diam_av(k),(massf1(k,f)&
	  /size_sect(k),f=1,N_frac), some/size_sect(k)
	enddo
	CLOSE(10)

	OPEN(UNIT=10,FILE='RESULT/number_result_sp' // trim(adjustl( cTemp )) // '.txt')
	do k=1,N_sizebin
	  some=0d0
	  do f=1,N_frac
	    some=some +numbf1(k,f)
	  enddo
	  write(unit=10,FMT=*) size_diam_av(k),(numbf1(k,f)&
	  /size_sect(k),f=1,N_frac), some/size_sect(k)
	enddo
	CLOSE(10)
      enddo
    endif

    if(N_species.gt.1) then
    !!write volume results of each size bin for each species 
      do s=1,N_species
	jesp=List_species(s)
	write( cTemp,'(i2)' ) s
	OPEN(UNIT=10,FILE='RESULT/volume_result_s' // trim(adjustl( cTemp )) // '.txt')
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
	OPEN(UNIT=10,FILE='RESULT/mass_result_s' // trim(adjustl( cTemp )) // '.txt')
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
	OPEN(UNIT=10,FILE='RESULT/mass_result_g' // trim(adjustl( cTemp )) // '.txt')
	do k=1,N_sizebin
	    write(unit=10,FMT=*) size_diam_av(k) , mass_group(k,g)/size_sect(k)
	enddo
	CLOSE(10)
      enddo
    endif

    concentration_tmp=0d0
    do j=1, N_size
      k= concentration_index(j, 1)
      i= concentration_index(j, 2)
      concentration_tmp(k,i)=concentration_number(j)
    enddo

    OPEN(UNIT=10,FILE="RESULT/number_result.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
	some=some +concentration_tmp(k,i)
      enddo
      write(unit=10,FMT=*)size_diam_av(k),(concentration_tmp(k,i)&
      /size_sect(k),i=1,N_fracmax), some/size_sect(k)
    enddo
    CLOSE(10)
    
    OPEN(UNIT=10,FILE="RESULT/number_result_o.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
	some=some +concentration_tmp(k,i)
      enddo
      write(unit=10,FMT=*)size_diam_av(k),(concentration_tmp(k,i),&
      i=1,N_fracmax), some
    enddo
    CLOSE(10)    
        
    OPEN(UNIT=10,FILE="RESULT/number_result_sbin.txt")
    do k=1,N_sizebin
      some=0d0
      do i=1,N_fracmax
	some=some +concentration_tmp(k,i)
      enddo
      write(unit=10,FMT=*)size_diam_av(k),some/size_sect(k)
    enddo
    CLOSE(10)

    deallocate(concentration_water)
    deallocate(concentration_tmp)
    deallocate(concentration_tmp2)
    deallocate(concentration_tmp3)
    deallocate(mass_group)
    if(N_species.gt.2.and.kind_composition.eq.1) then    
    deallocate(massf1)
    deallocate(numbf1)
    endif

  end subroutine write_result
  
  end module Resultoutput
