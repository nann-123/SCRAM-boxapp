!!-----------------------------------------------------------------------
!!     Copyright (C) 2003-2014, ENPC - INRIA - EDF R&D
!!     Author(s): Hilel Dergaoui
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
!!    This module contains methods to compute particle coagulation rate
!!-----------------------------------------------------------------------
module Coagulation
  use Physicalbalance
  use Discretization 
  use CoefficientRepartition
  use CoeffRepartitionBoxmodel
  use Initialization
  
  implicit none

contains

  subroutine Gain (distribution, coagulation_rate_gain,c_number)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine computes the gain rate of coagulation
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     c_number: aerosol number concentration(#/m^3)
!     distribution:number/mass distribution before the coagulation(~/m^3)
!
!     -- OUTPUT VARIABLES
!
!     coagulation_rate_gain: the gain rate of coagulation(~/m^3/s)
!------------------------------------------------------------------------   
    implicit none
    integer::k,i,j,l
    double precision::distribution(N_size)
    double precision::coagulation_rate_gain(N_size)
    double precision ::c_number(N_size)
    double precision :: gain_term
    do k=1,N_size
       coagulation_rate_gain(k) = 0.d0
    enddo
    
    do k=1,N_size 
      gain_term=0.d0
      do l=1,repartition_coefficient(k)%n
	!check all possible repartition_coefficient combination of grid 1 and grid 2 into grid k
	i=index1_repartition_coefficient(k)%arr(l)! index of grid 1
	j=index2_repartition_coefficient(k)%arr(l)! index of grid 2
	if(IsNaN(kernel_coagulation(i,j)) ) then
	  print*, "kernel_coagulation(",i,j,")=",kernel_coagulation(i,j)!The problem is here NaN
	  kernel_coagulation(i,j)=0.d0
	endif
	gain_term=gain_term+kernel_coagulation(j,i)*repartition_coefficient(k)%arr(l)&
	    *c_number(i)*distribution(j)
      enddo
       
      coagulation_rate_gain(k) =gain_term
      if(IsNaN(gain_term)) then
	print*,'IsNaN(gain_term)',k,i,j
	stop
      endif
    enddo
  end subroutine Gain
  
  subroutine Loss(distribution, coagulation_rate_loss,c_number)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine computes the loss rate of coagulation
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     c_number: aerosol number concentration(#/m^3)
!     distribution:number/mass distribution before the coagulation(~/m^3)
!
!     -- OUTPUT VARIABLES
!
!     coagulation_rate_loss: the loss rate of coagulation(~/m^3/s)
!------------------------------------------------------------------------   
    implicit none 
    integer::j,i
    double precision:: distribution(N_size)
    double precision:: coagulation_rate_loss(N_size)
    double precision :: loss_term
    double precision ::c_number(N_size)
    do j=1,N_size 
      coagulation_rate_loss(j) =0.d0
    enddo
    do j=1,N_size 
      loss_term=0.d0
      do i=1,N_size
	if(IsNaN(kernel_coagulation(j,i)) ) then
	  print*, "kernel_coagulation(",j,i,")=",kernel_coagulation(j,i)
	  kernel_coagulation(j,i)=0.d0
	endif
	!loss by coagulation between grid k and i
	loss_term= loss_term + kernel_coagulation(j,i) &
	      * c_number(i)
      enddo
      if(IsNaN(loss_term)) then
	print*,'IsNaN(loss_term)',i,j
	stop
      endif
      coagulation_rate_loss(j) =loss_term*distribution(j)
    enddo
     
  end subroutine loss
 
  subroutine Rate(rate_number,rate_mass,c_number,c_mass)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine computes coagulation rate for number and each species
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     c_number: aerosol number concentration(#/m^3)
!     c_mass: aerosol mass concentration(�g/m^3)
!
!     -- OUTPUT VARIABLES
!
!     rate_number: the coagulation rate of number concentration(#/m^3/s)
!     rate_mass: the loss rate of mass concentration(�g/m^3/s)
!------------------------------------------------------------------------   
    implicit none
    integer :: j,i,jesp,p,c
    double precision::distribution(N_size)
    double precision::coagulation_rate_loss(N_size)
    double precision::coagulation_rate_gain(N_size)
    double precision ::c_number(N_size)
    double precision ::c_mass(N_size,N_aerosol)
    double precision ::rate_number(N_size)
    double precision ::rate_mass(N_size,N_aerosol)
    double precision :: event_rate
    double precision :: src_mass_i, src_mass_j, product_mass
    double precision :: product_species_mass(N_aerosol)
    double precision :: total_product_mass, add_mass_tgt1, add_mass_tgt2
    ! Debug marker variables
    character(len=8) :: dbg
    integer :: statdbg
    
    if (.not. coeff_use_legacy_mode()) then
      call coeff_prepare_pair_mapping(c_number, c_mass)
      call coeff_reset_deltas()
      rate_number = 0.d0
      rate_mass = 0.d0
      coeff_last_coag_mass_before = 0.d0
      coeff_last_coag_number_before = sum(c_number)
      coeff_last_coag_event_rate_sum = 0.d0
      do i = 1, N_species
        jesp = List_species(i)
        coeff_last_coag_mass_before = coeff_last_coag_mass_before + sum(c_mass(:,jesp))
      enddo
      do p = 1, coeff_pair_count
        i = coeff_pair_src1(p)
        j = coeff_pair_src2(p)
        product_species_mass = 0.d0
        total_product_mass = 0.d0
        if (i == j) then
          event_rate = 0.5d0 * kernel_coagulation(i,j) * c_number(i) * c_number(j)
        else
          event_rate = kernel_coagulation(i,j) * c_number(i) * c_number(j)
        endif
        if (event_rate == 0.d0) cycle
        coeff_last_coag_event_rate_sum = coeff_last_coag_event_rate_sum + event_rate

        if (i == j) then
          coeff_last_delta_number(i) = coeff_last_delta_number(i) - 2.d0 * event_rate
          rate_number(i) = rate_number(i) - 2.d0 * event_rate
        else
          coeff_last_delta_number(i) = coeff_last_delta_number(i) - event_rate
          coeff_last_delta_number(j) = coeff_last_delta_number(j) - event_rate
          rate_number(i) = rate_number(i) - event_rate
          rate_number(j) = rate_number(j) - event_rate
        endif

        do c = 1, coeff_pair_candidate_count(p)
          if (coeff_pair_candidate_weights(c,p) <= 0.d0) cycle
          coeff_last_delta_number(coeff_pair_candidate_cells(c,p)) = coeff_last_delta_number(coeff_pair_candidate_cells(c,p)) + &
            coeff_pair_candidate_weights(c,p) * event_rate
          rate_number(coeff_pair_candidate_cells(c,p)) = rate_number(coeff_pair_candidate_cells(c,p)) + &
            coeff_pair_candidate_weights(c,p) * event_rate
        enddo

        do i = 1, N_species
          jesp = List_species(i)
          src_mass_i = event_rate * c_mass(coeff_pair_src1(p),jesp) / max(c_number(coeff_pair_src1(p)), TINYN)
          if (coeff_pair_src1(p) == coeff_pair_src2(p)) then
            src_mass_j = src_mass_i
          else
            src_mass_j = event_rate * c_mass(coeff_pair_src2(p),jesp) / max(c_number(coeff_pair_src2(p)), TINYN)
          endif
          product_mass = src_mass_i + src_mass_j

          coeff_last_delta_mass(coeff_pair_src1(p),jesp) = coeff_last_delta_mass(coeff_pair_src1(p),jesp) - src_mass_i
          rate_mass(coeff_pair_src1(p),jesp) = rate_mass(coeff_pair_src1(p),jesp) - src_mass_i
          if (coeff_pair_src1(p) == coeff_pair_src2(p)) then
            coeff_last_delta_mass(coeff_pair_src1(p),jesp) = coeff_last_delta_mass(coeff_pair_src1(p),jesp) - src_mass_j
            rate_mass(coeff_pair_src1(p),jesp) = rate_mass(coeff_pair_src1(p),jesp) - src_mass_j
          else
            coeff_last_delta_mass(coeff_pair_src2(p),jesp) = coeff_last_delta_mass(coeff_pair_src2(p),jesp) - src_mass_j
            rate_mass(coeff_pair_src2(p),jesp) = rate_mass(coeff_pair_src2(p),jesp) - src_mass_j
          endif
          product_species_mass(jesp) = product_mass
          total_product_mass = total_product_mass + product_mass
        enddo

        if (total_product_mass <= 0.d0) cycle

        do i = 1, N_species
          jesp = List_species(i)
          do c = 1, coeff_pair_candidate_count(p)
            if (coeff_pair_candidate_weights(c,p) <= 0.d0) cycle
            add_mass_tgt1 = coeff_pair_candidate_weights(c,p) * product_species_mass(jesp)
            coeff_last_delta_mass(coeff_pair_candidate_cells(c,p),jesp) = coeff_last_delta_mass(coeff_pair_candidate_cells(c,p),jesp) + add_mass_tgt1
            rate_mass(coeff_pair_candidate_cells(c,p),jesp) = rate_mass(coeff_pair_candidate_cells(c,p),jesp) + add_mass_tgt1
          enddo
        enddo
      enddo
      coeff_last_coag_mass_after = coeff_last_coag_mass_before + sum(coeff_last_delta_mass)
      coeff_last_coag_mass_residual = coeff_last_coag_mass_after - coeff_last_coag_mass_before
      coeff_last_coag_number_after = coeff_last_coag_number_before + sum(coeff_last_delta_number)
      coeff_last_coag_number_residual = sum(coeff_last_delta_number) + coeff_last_coag_event_rate_sum
      return
    endif

    do  j = 1,N_size
      distribution(j) = c_number(j)
    enddo
    ! Debug marker: optionally emit unique tag when coagulation Rate is executed
    call get_environment_variable('SCRAM_DEBUG', dbg, status=statdbg)
    if (statdbg == 0 .and. trim(dbg) == '1') then
      write(*,*) 'SCRAM_DEBUG: COAGULATION Rate executed'
    end if
    call  Gain (distribution, coagulation_rate_gain,c_number)
    call  Loss (distribution, coagulation_rate_loss,c_number)
    do j = 1,N_size
      rate_number(j) =0.5d0*coagulation_rate_gain(j) - coagulation_rate_loss(j)!
    enddo
	
    do i=1,N_species!loop by species
      jesp=List_species(i)
      do j = 1,N_size! Reassigned distribution by mass of each species
	  distribution(j) = c_mass(j,jesp)
      enddo
      call  Gain (distribution,coagulation_rate_gain,c_number)
      call  Loss (distribution,coagulation_rate_loss,c_number)
      do j = 1,N_size
	  rate_mass(j,jesp) = coagulation_rate_gain(j) - coagulation_rate_loss(j)!
      enddo
    enddo
     
  end subroutine Rate
     
end module Coagulation
