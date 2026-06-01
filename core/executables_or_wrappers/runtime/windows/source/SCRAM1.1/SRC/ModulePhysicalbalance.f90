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
!!    This module contains methods related to particles physical characteristics
!!-----------------------------------------------------------------------
MODULE Physicalbalance
  use Initialization
   implicit none

 contains
  subroutine compute_average_diameter()
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine compute particle dry diameter of each
!     bins
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!------------------------------------------------------------------------   
    implicit none
    integer::k,s,j,jesp
    double precision::mass_total
    double precision::volum_cell,av_volum_cl

    !call compute_all_density()!renew the density of each bin

    do j= 1, N_size
        k=concentration_index(j, 1)!size bins
        cell_mass_av(j)=size_mass_av(k)
        cell_diam_av(j)=size_diam_av(k)
 	volum_cell=0.d0
 	mass_total =0.d0
 	do s= 1, N_species
 	  jesp=List_species(s)
          mass_total = mass_total + concentration_mass(j,jesp)
 	  mass_total_grid (j) =mass_total
 	  volum_cell=volum_cell+concentration_mass(j,jesp)/mass_density_aer(s)
 	enddo
 	if (concentration_number(j).gt.0.d0) then
          cell_mass_av(j) =dble(mass_total)/dble(concentration_number(j)) !mass of single particle
          av_volum_cl=dble(volum_cell)/dble(concentration_number(j))
 	  cell_diam_av(j)  = (6.d0*av_volum_cl/pi)**(1.D0/3.D0) ! µm
 	else
 	  concentration_number(j)=0.d0
 	  cell_diam_av(j)=size_diam_av(k)
 	endif
 	if(cell_diam_av(j).eq.0.d0) then
 	  cell_diam_av(j)=size_diam_av(k)
 	elseif(cell_diam_av(j).lt.diam_bound(1)) then
 	  cell_diam_av(j)=diam_bound(1)
 	endif
    enddo

  end  subroutine compute_average_diameter

  subroutine compute_average_bin_diameter()
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine compute particle dry diameter of each
!     size bins
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!------------------------------------------------------------------------  
    implicit none
    integer::k,s,j,fr,jesp
    double precision::mass_sizebin(N_sizebin),number_sizebin(N_sizebin)
    double precision::volum_sizebin(N_sizebin),av_volum_sb(N_sizebin)

    call compute_all_density()!renew the density of each bin

    do k= 1, N_sizebin
      mass_sizebin(k)=0.d0
      number_sizebin(k)=0.d0
      av_volum_sb(k)=0.d0
      volum_sizebin(k)=0.d0
      do fr = 1, N_fracmax
	j=concentration_index_iv(k,fr)
	number_sizebin(k)=number_sizebin(k)+concentration_number(j)
	do s= 1, N_species
	  jesp=List_species(s)
	  mass_sizebin(k)=mass_sizebin(k)+concentration_mass(j,jesp)
	  volum_sizebin(k)=volum_sizebin(k)+concentration_mass(j,jesp)/mass_density_aer(s)
	enddo
      enddo
      if (number_sizebin(k).gt. 0.d0)then
	av_volum_sb(k)=dble(volum_sizebin(k))/dble(number_sizebin(k))
	size_mass_av(k)=dble(mass_sizebin(k))/dble(number_sizebin(k)) !mass of single particle
	size_diam_av(k)=(av_volum_sb(k)*6.d0/pi)**(1.d0/3.d0)
      else
	size_mass_av(k) = size_diam_av(k)**3 *fixed_density*pi/6.d0
      endif
      if(size_diam_av(k) .lt. diam_bound(1)) then
	size_diam_av(k)=diam_bound(1)
      endif
    enddo
    
  end  subroutine compute_average_bin_diameter

  subroutine computer_number()
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine compute particle based on particle mass
!     and fixed diameter.
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!------------------------------------------------------------------------  
    implicit none
    integer::k,s,j,jesp
    double precision::volum_cell

    do j= 1, N_size
      k=concentration_index(j, 1)!size bins
      volum_cell=0.d0
      do s= 1, N_species
	jesp=List_species(s)
	volum_cell=volum_cell+concentration_mass(j,jesp)/mass_density_aer(s)
      enddo
      concentration_number(j)=(6.d0*volum_cell)/((size_diam_av(k)**3.d0)*pi)
    enddo
  end  subroutine computer_number

  subroutine compute_all_density()
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine update overall density of each bin and size bin
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!------------------------------------------------------------------------  
    implicit none

    integer::k,s,j,f,idx,jesp
    double precision, allocatable :: subrho(:),masstot(:)
    double precision, allocatable :: subrho2(:),masstot2(:)
    double precision :: rho_local

    allocate(subrho(N_size), masstot(N_size))
    allocate(subrho2(N_sizebin), masstot2(N_sizebin))

    subrho = 0.d0
    masstot = 0.d0
    subrho2 = 0.d0
    masstot2 = 0.d0

    do k = 1, N_size
      do s = 1, N_species
        jesp = List_species(s)
        rho_local = mass_density_aer(jesp)
        if (rho_local <= 0.d0) rho_local = fixed_density
        masstot(k) = masstot(k) + concentration_mass(k,jesp)
        subrho(k) = subrho(k) + concentration_mass(k,jesp) / rho_local
      enddo
      if (masstot(k) > 0.d0 .and. subrho(k) > 0.d0) then
        density_aer_bin(k) = masstot(k) / subrho(k)
      else
        density_aer_bin(k) = fixed_density_l
      endif
    enddo

    do j = 1, N_sizebin
      do f = 1, N_fracmax
        idx = concentration_index_iv(j,f)
        if (idx < 1 .or. idx > N_size) cycle
        subrho2(j) = subrho2(j) + subrho(idx)
        masstot2(j) = masstot2(j) + masstot(idx)
      enddo
      if (masstot2(j) > 0.d0 .and. subrho2(j) > 0.d0) then
        density_aer_size(j) = masstot2(j) / subrho2(j)
      else
        density_aer_size(j) = fixed_density_l
      endif
    enddo

    if (allocated(subrho)) deallocate(subrho)
    if (allocated(masstot)) deallocate(masstot)
    if (allocated(subrho2)) deallocate(subrho2)
    if (allocated(masstot2)) deallocate(masstot2)

  end  subroutine compute_all_density
!     -- DESCRIPTION
!     This subroutine computes the gas-phase concentration by mass
!     conservation.
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     c_mass: aerosol mass concentration(�g/m^3)
!     c_number: aerosol number concentration(#/m^3)
!
!     -- INPUT/OUTPUT VARIABLES

!     c_gas: aerosol gas phase concentration(�g/m^3)
!     total_mass: total mass of each species both gas phase and aerosol(�g/m^3)
!
!------------------------------------------------------------------------     
  subroutine mass_conservation(c_mass,c_number,c_gas,total_mass)
    implicit none

    integer::j,jesp,k
    double precision:: c_number(N_size)
    double precision:: c_mass(N_size,N_aerosol)
    double precision:: c_gas(N_aerosol)
    double precision:: total_mass(N_aerosol)

    do jesp=1,N_aerosol
      total_aero_mass(jesp)=0.d0
    enddo
    bin_mass=0.d0
    bin_number=0.d0
    total_number=0.d0
    total_mass_t=0.d0
	  !check all not negtive value is allowed
    do j=1,N_size
      k=concentration_index(j, 1)
      if(c_number(j).ne.c_number(j)) then
      c_number(j)=0.d0
      endif
      total_number=total_number+c_number(j)
      bin_number(k)=bin_number(k)+c_number(j)
      do jesp=1,N_aerosol-1
	if(c_mass(j,jesp).lt.0.d0) then
	  c_mass(j,jesp)=0.d0
	endif
	if(c_mass(j,jesp).ne.c_mass(j,jesp)) then
	  c_mass(j,jesp)=0.d0
	endif
	total_mass_t=total_mass_t+c_mass(j,jesp)
	bin_mass(k)=bin_mass(k)+c_mass(j,jesp)
      enddo
    enddo

    do j=1,N_size
      do jesp=1,N_aerosol
	total_aero_mass(jesp)=total_aero_mass(jesp)+c_mass(j,jesp)
      enddo
    enddo

    do jesp=ESO4,N_aerosol-1
      !renew the gas_condensation (reduce into aerosol)
      if(total_mass(jesp).gt.total_aero_mass(jesp)) then
	c_gas(jesp)=total_mass(jesp)-total_aero_mass(jesp)
      else
	c_gas(jesp)=0.d0
	total_aero_mass(jesp)=total_mass(jesp)
      endif
    enddo

    do jesp=1,N_aerosol
      if(total_aero_mass(jesp).lt.0.d0) then
	total_aero_mass(jesp) =0.d0
      endif
      if(total_mass(jesp).lt.0.d0) then
	total_mass(jesp) =0.d0
      endif
    enddo

  end subroutine mass_conservation

  subroutine check_mass_number()
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine checks mass and number coexistence,
!     to avoid bins contains only mass or only number
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!------------------------------------------------------------------------             
    implicit none
    integer:: j,jesp
    double precision:: tmp_cell_mass

    do j= 1, N_size
      tmp_cell_mass=0.d0
      do jesp=1,N_aerosol
	tmp_cell_mass=tmp_cell_mass+concentration_mass(j,jesp)
	if(concentration_mass(j,jesp).lt.0.d0) stop
      enddo
      if(tmp_cell_mass*concentration_number(j).eq.0.d0&
	.and.tmp_cell_mass+concentration_number(j).ne.0.d0) then
	do jesp=1,N_aerosol
	  if(concentration_mass(j,jesp).gt.0.d0) print*,jesp,concentration_mass(j,jesp)
	enddo
	print*,current_sub_time,j,tmp_cell_mass,concentration_number(j)
      endif
    enddo
      
  end subroutine
   
  subroutine check_av_diam(c_mass,c_number)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine checks whether average diameter of each bins
!     still located within size bounds
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     c_mass: aerosol mass concentration(�g/m^3)
!     c_number: aerosol number concentration(#/m^3)
!------------------------------------------------------------------------   
    implicit none

    integer:: j,k,jesp,s,fr
    double precision::loss_mass
    double precision::volum_cell,av_volum_cl
    double precision::c_mass(N_size,N_aerosol)
    double precision::c_number(N_size)
    double precision:: total_aer(N_aerosol)
    double precision:: mass_cell(N_size)


    loss_mass=0.d0
    mass_cell=0.d0
    total_aer=0.d0
    !check the aerosol mass
    do j= 1, N_size
      do s= 1, N_species
	jesp=List_species(s)
	if(c_mass(j,jesp).lt.0.d0) then
	  c_mass(j,jesp)=0.d0
	endif
	total_aer(jesp)=total_aer(jesp)+c_mass(j,jesp)
	mass_cell(j)=mass_cell(j)+c_mass(j,jesp)
      end do
    end do

    if(redistribution_method.gt.2) then
      do j= 1, N_size
	k=concentration_index(j, 1)!size bins
	volum_cell=0.d0
	do s= 1, N_species
	  jesp=List_species(s)
	  volum_cell=volum_cell+c_mass(j,jesp)/mass_density_aer(s)
	enddo
	if(c_number(j).gt.TINYN.AND.mass_cell(j).gt.N_species*TINYM) then
          av_volum_cl=dble(volum_cell)/dble(c_number(j))
	  cell_diam_av(j)  = (6.d0*av_volum_cl/pi)**(1.D0/3.D0) ! �m
	  if(cell_diam_av(j).eq.0.d0) then
	    cell_diam_av(j)=size_diam_av(k)
	  elseif(cell_diam_av(j).lt.diam_bound(1)) then
	    cell_diam_av(j)=diam_bound(1)
	  endif
	  if(cell_diam_av(j).lt.diam_bound(k)) then
	    cell_diam_av(j)=diam_bound(k)!dsqrt(cell_diam_av(j)*size_diam_av(k))
	    av_volum_cl=pi*(cell_diam_av(j)**3.d0)/6.d0
	    c_number(j)=volum_cell/av_volum_cl
	  elseif(cell_diam_av(j).gt.diam_bound(k+1)) then
	    cell_diam_av(j)=diam_bound(k+1)!dsqrt(cell_diam_av(j)*size_diam_av(k))
	    av_volum_cl=pi*(cell_diam_av(j)**3.d0)/6.d0
	    c_number(j)=volum_cell/av_volum_cl
	  endif
	  if(cell_diam_av(j).lt.diam_bound(k).or.cell_diam_av(j).gt.diam_bound(k+1)) then
	    cell_diam_av(j)=size_diam_av(k)!dsqrt(cell_diam_av(j)*size_diam_av(k))
	    av_volum_cl=pi*(cell_diam_av(j)**3.d0)/6.d0
	    c_number(j)=volum_cell/av_volum_cl
	  endif
	else!renew the number based on mass and av_diam
	  cell_diam_av(j)=size_diam_av(k)
	  av_volum_cl=pi*(size_diam_av(k)**3.d0)/6.d0
	  c_number(j)=volum_cell/av_volum_cl
	endif
      enddo

      do j = 1, N_size
	k=concentration_index(j, 1)!size bins
	if(cell_diam_av(j).lt.diam_bound(k).or.cell_diam_av(j).gt.diam_bound(k+1)) then
	  fr=concentration_index(j, 2)
	  print*,"Cell ",j,k,fr,"diameter error!"
	  print*,cell_diam_av(j),"[",diam_bound(k),",",diam_bound(k+1),"]"
	  print*,c_number(j),mass_cell(j)
	  stop
	endif
      enddo
    endif
  end subroutine check_av_diam
     
  subroutine check_diam_fraction(c_mass,c_number)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine checks whether average diameter of each bins
!     still located within size bounds, as well as their fractions
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     c_mass: aerosol mass concentration(�g/m^3)
!     c_number: aerosol number concentration(#/m^3)
!------------------------------------------------------------------------   
    implicit none
    integer::k,g,j,jesp,s,f
    double precision:: mass_groups(N_size,N_groups)!mass by groups
    double precision::c_mass(N_size,N_aerosol)
    double precision::c_number(N_size)
    double precision::f1,f2
    double precision::tmp
    double precision::volum_cell,av_volum_cl
    integer:: tag_error
    !calculate redistribution map
    tag_error=0
!! Initialize to zero the variation in mass and number concentrations due to
!! redistribution
    do j= 1, N_size
	mass_total_grid (j)=0.d0
	do s= 1, N_species
	  jesp=List_species(s)	  
	  mass_total_grid (j)=mass_total_grid (j) + c_mass(j,jesp)
	enddo       
    enddo

    if(N_frac.gt.1) then
      do j= 1, N_size !!for each grid the number of size sections x fraction sections
  !      Compute fraction of each species in the grid point before redistribution
         do g= 1, N_groups
	  frac_grid(j,g)=0.d0!Fraction of group g in grid j
	  mass_groups(j,g)=0.d0
	enddo
	do s= 1, N_species
	  jesp=List_species(s)
	  g=index_groups(s)
	  mass_groups(j,g)=mass_groups(j,g)+c_mass(j,jesp)
	enddo
	do g= 1, N_groups
	    if(mass_total_grid (j).gt.0d0) then
	      frac_grid(j,g) =mass_groups(j,g)/mass_total_grid (j)
	    endif
	enddo
	k=concentration_index(j,1)
	f=concentration_index(j,2)
	!check their composition
	if(mass_total_grid (j).gt.0.d0) then
	  do g= 1, N_groups
	    f1=discretization_composition(1, f, g, 1)
	    f2=discretization_composition(1, f, g, 2)
	    if(frac_grid(j,g).lt.f1.or.frac_grid(j,g).gt.f2) then
	    endif
	  enddo
	endif
      enddo
    endif

     do j= 1, N_size
	k=concentration_index(j, 1)!size bins
	f=concentration_index(j,2)
	volum_cell=0.d0
	do s= 1, N_species
	  jesp=List_species(s)
	  volum_cell=volum_cell+c_mass(j,jesp)/mass_density_aer(s)
	enddo
	if(c_number(j).gt.TINYN.AND.mass_total_grid (j).gt.N_species*TINYM) then
          av_volum_cl=dble(volum_cell)/dble(c_number(j))
          tmp=cell_diam_av(j)
	  cell_diam_av(j)  = (6.d0*av_volum_cl/pi)**(1.D0/3.D0) ! �m
	  if(cell_diam_av(j).lt.diam_bound(k).or.cell_diam_av(j).gt.diam_bound(k+1))then
	    av_volum_cl=(pi*size_diam_av(k)**3.d0)/6.d0
	    c_number(j)=volum_cell/av_volum_cl
	  endif
	endif
    enddo

    if(tag_error.eq.1) stop
      
  end subroutine check_diam_fraction

  subroutine mass_to_number(c_mass,c_number)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine computes particle number based on particle mass
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     c_mass: aerosol mass concentration(�g/m^3)
!     c_number: aerosol number concentration(#/m^3)
!------------------------------------------------------------------------   
    implicit none
    integer::k,j,jesp,s
    double precision::c_mass(N_size,N_aerosol)
    double precision::c_number(N_size)
    
    do j= 1, N_size
      k=concentration_index(j, 1)!size bins
      mass_total_grid (j)=0.d0
      do s= 1, N_species
	jesp=List_species(s)
	mass_total_grid (j)=mass_total_grid (j) + c_mass(j,jesp)
      enddo
      c_number(j)=mass_total_grid (j)/size_mass_av(k)
    enddo

  end subroutine mass_to_number
 
end MODULE Physicalbalance
