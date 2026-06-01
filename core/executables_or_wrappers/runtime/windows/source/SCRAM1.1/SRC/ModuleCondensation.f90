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
!!    This module contains methods to compute particle condensation rate
!!-----------------------------------------------------------------------
Module Condensation
  use Discretization
  use Initialization
  use Thermodynamics  
  implicit none
 
contains
  subroutine SULFDYN(Q1,Q,N1,N,c_gas,dqdt,dtx)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine solve sulferic acid condensation by explicit solution
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     c_gas: aerosol gas phase concentration(�g/m^3)
!     dtx: condensation time step (s)
!
!     -- INPUT/OUTPUT VARIABLES
!
!     Q: aerosol mass concentration of second order evaluation(�g/m^3)
!     N: aerosol number concentration of second order evaluation(#/m^3)
!
!     -- OUTPUT VARIABLES
!
!     Q1: aerosol mass concentration of first order evaluation(�g/m^3)
!     N1: aerosol number concentration of first order evaluation(#/m^3)
!     dqdt: mass derivation(�g/m^3/s)
!
!------------------------------------------------------------------------
    implicit none
    integer::j,jesp
    double precision :: dqdt(N_size,N_aerosol)
    double precision ::c_gas(N_aerosol)!micg/m^-3
    double precision :: ce_kernal_coef_tot ! c/e kernel coef (m3.s-1)
    double precision :: Q1(N_size,N_aerosol) ! Mass concentration
    double precision :: Q(N_size,N_aerosol) ! Mass concentration
    double precision :: N1(N_size) ! Number concentration
    double precision :: N(N_size) ! Number concentration
    double precision :: dtx,tmp!Time steps

    ! Debug marker: optionally emit unique tag when condensation SULFDYN is executed
    character(len=8) :: dbgc
    integer :: statdgc

    jesp=ESO4!Pointer
    ce_kernal_coef_tot = 0.0d0

    call get_environment_variable('SCRAM_DEBUG', dbgc, status=statdgc)
    if (statdgc == 0 .and. trim(dbgc) == '1') then
      write(*,*) 'SCRAM_DEBUG: CONDENSATION SULFDYN executed'
    end if

    do j = 1,N_size! Reassigned distribution by mass of each species
      call compute_condensation_transfer_rate(diffusion_coef(jesp), &
      quadratic_speed(jesp), accomodation_coefficient(jesp), &
      wet_diameter(j), dqdt(j,jesp))
      ce_kernal_coef_tot=ce_kernal_coef_tot+N(j)*dqdt(j,jesp)
    enddo
     ! print*,"accomodation_coefficient",accomodation_coefficient(jesp)
    do j = 1,N_size! Reassigned distribution by mass of each species
      tmp=(dqdt(j,jesp)*N(j)/ce_kernal_coef_tot)*&
      (1.0D0-DEXP(-ce_kernal_coef_tot*dtx))*c_gas(jesp)
      if(tmp.gt.0.d0) then
	addm(jesp)=addm(jesp)+tmp
      else
	tmp=0.d0
      endif
      Q(j,jesp) = Q(j,jesp)+tmp!renew mass
      Q1(j,jesp) = Q(j,jesp)
      N1(j)=N(j)
      dqdt(j,jesp)=tmp/dtx!for redistribution
    enddo

  end subroutine SULFDYN

  subroutine KERCOND(qn,q,c_gas,Wet_diam,Temperature,ce_kernel,ce_kernal_coef_i,jj)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine computes particle condensation kernels
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     c_gas: aerosol gas phase concentration(�g/m^3)
!     Wet_diam: wet diameters (s)
!     q: aerosol mass concentration (�g/m^3)
!     qn: aerosol number concentration (#/m^3)
!     Temperature: temperature
!     ce_kernal_coef_i: c/e kernel coefficient          ([m3.s-1]).
!     jj: current bin index 
!
!     -- OUTPUT VARIABLES
!
!     ce_kernel: particle condensation kernels (�g/m^3/s)
!
!------------------------------------------------------------------------
    implicit none
    integer:: jesp,N_size,init,jj
    double precision:: qn,qext(N_aerosol),init_bulk_gas(N_aerosol)
    double precision:: qinti(N_inside_aer),ce_kernal_coef_i(N_aerosol)
    double precision:: surface_equilibrium_conc(N_aerosol),ce_kernel(N_aerosol)
    double precision:: Kelvin_effect(N_aerosol),Wet_volume
    double precision:: Wet_diam,Wet_diam_used,rhop
    double precision::c_gas(N_aerosol)!micg/m^-3
    double precision:: q(N_aerosol)!mass concentration in current grid point
    double precision:: qih,emw_tmp,rhop_tmp,Temperature


!!     ******Initialization to zero
    do jesp=E1,E2
      Kelvin_effect(jesp)=0.D0
      ce_kernel(jesp)=0.D0
      qext(jesp)=0.D0
      init_bulk_gas(jesp)=0.D0
      surface_equilibrium_conc(jesp)=0.D0!surface eqlibrium concentration
    end do

    do jesp=E1,E2
      init_bulk_gas(jesp)=c_gas(jesp)!initial bulk gas conc (�g.m-3)
      qext(jesp)=q(jesp)
    enddo

    call surface_eq_conc(qext,qinti,surface_equilibrium_conc)!calculate the equilibrium between aerosols and gas-phase

    ! we prevent evaporation when conc
    ! are too near from zero
    do jesp=E1,E2
      if (qext(jesp).LE.TINYM) then
	surface_equilibrium_conc(jesp)=0.D0
      endif
      if (surface_equilibrium_conc(jesp).lt.0.D0) then
	surface_equilibrium_conc(jesp)=0.D0
      endif
    end do
!     ******c/e kernel coefficient
    do jesp=G1,G2
      if (aerosol_species_interact(jesp).gt.0) then
	call COMPUTE_CONDENSATION_TRANSFER_RATE(&
	      diffusion_coef(jesp), &! diffusion coef (m2.s-1)
	      quadratic_speed(jesp),& ! quadratic mean speed (m.s-1)
	      accomodation_coefficient(jesp),& ! accomadation coef (adim)
	      Wet_diam,   & ! wet aero diameter (µm)
	      ce_kernal_coef_i(jesp) ) ! c/e kernel coef (m3.s-1)
      endif
    enddo

!     Aerosol wet density in � g.� m -3
    rhop = 0.d0
    do jesp= 1,N_aerosol
      rhop=rhop+qext(jesp)
    enddo

    Wet_volume=Wet_diam**3.d0*cst_pi6
    rhop =rhop/Wet_volume        ! �g.�m-3
    rhop_tmp = rhop * 1.D12 ! kg/m3
    Wet_diam_used =DMAX1(Wet_diam,Dmin)
    do jesp=G1,G2
      if (aerosol_species_interact(jesp).gt.0) then
	emw_tmp = molecular_weight_aer(jesp) * 1.D-6 ! g/mol
	call COMPUTE_KELVIN_COEFFICIENT(&
		Temperature,&          ! temperature (Kelvin)
		emw_tmp,&       ! ext mol weight (g.mol-1)
		surface_tension(jesp),&   ! surface tension (N.m-1) from INC
		Wet_diam_used,&         ! wet aero diameter (�m)
		rhop_tmp,&      ! aerosol density (kg.m-3)
		Kelvin_effect(jesp) )   ! kelvin effect coef (adim)
      endif
    enddo
!!     ******Not limited c/e kernels

    do jesp=G1,G2
      if (aerosol_species_interact(jesp).gt.0) then
	ce_kernel(jesp)= ce_kernal_coef_i(jesp)& ! kernel coef (m3.s-1)
	    *( init_bulk_gas(jesp)&    ! bulk gas conc (�g.m-3)
	    -surface_equilibrium_conc(jesp)&      ! equi gas conc (�g.m-3) unknow
	    *Kelvin_effect(jesp) )     ! kelvin coef (adim)
      endif
    enddo
    
    init=0
    do jesp=G1, G2
	if (qext(jesp).gt.TINYM) then
	  init=1
	endif
    enddo
    
    if (qext(EH2O).eq.0.D0.AND.init.eq.1) then ! solid
      call DRYIN( Temperature,&   ! local temperature (Kelvin)
	  qinti,&         ! int sld inorg conc (�g.m-3)
	  N_aerosol,&         ! size of vectors following below
	  init_bulk_gas,&         ! bulk gas conc (�g.m-3)
	  ce_kernal_coef_i,&           ! kernel coef (m3.s-1)
	  Kelvin_effect,&          ! kelvin coef (adim)
	  surface_equilibrium_conc,&         ! equi gas conc (�g.m-3)
	  ce_kernel )       ! modified c/e kernel
			      ! liq or mix : H+ limitation flux
    else
      qih=qinti(IH)/qn    ! �g ,qn is number (qih is H+ per particl)
      !print*,'water go',qext(EH2O)
      call HPLFLIM( ALFHP,& ! percentage of H+ allowed to c/e(0.1)
	  qih,&            ! int H+ conc (�g)
	  N_aerosol,&          ! size of vectors following below
	  init_bulk_gas,&          ! bulk gas conc (�g.m-3)
	  ce_kernal_coef_i,&            ! kernel coef (m3.s-1)
	  Kelvin_effect,&           ! kelvin coef (adim)
	  surface_equilibrium_conc,&          ! equi gas conc (�g.m-3)
	  ce_kernel )        ! modified c/e kernel
    endif
    concentration_mass(jj,EH2O)=qext(EH2O)!water updated here
    do jesp=1,N_inside_aer
      concentration_inti(JJ,jesp)=qinti(jesp)
    enddo
   
  end subroutine KERCOND
   
  subroutine surface_eq_conc(qext,qinti,surface_equilibrium_conc)
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine computes the local (surface) aerosol equilibrium within each bin.
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!     qext: aerosol mass concentration(�g/m^3)
!     qinti: aerosol internal species mass concentration(�g/m^3)
!
!     -- OUTPUT VARIABLES
!
!     surface_equilibrium_conc: surface equilibrium concentration of aerosol species
!
!------------------------------------------------------------------------
    implicit none
    integer:: jesp
    double precision:: surface_equilibrium_conc(N_aerosol)!surface_equilibrium_conc : equilibrium gas concentration    ([\mu.g.m^-3]).
    double precision:: qext(N_aerosol)!QEXT : external aerosol concentration ([\mu.g.m^-3]).
    double precision:: qinti(N_inside_aer)!QINTI : internal inorganic concentration ([\mu.g.m^-3]).not used
    double precision:: qtinorg

!!     ******zero init
    do jesp=1,N_aerosol
      surface_equilibrium_conc(jesp)=0.D0
    end do

    !!     ******organics et inorganics thermodynamics
    do jesp=1,N_inside_aer!N_inside_aer=21
      qinti(jesp)=0.d0
    enddo
    qext(EH2O)=0.d0
			      ! sum of inorganic mass
    qtinorg=0.D0
    do jesp=ENa,ECl
      qtinorg=qtinorg+qext(jesp)
    end do

    call EQINORG( N_aerosol,qext,&         ! ext inorg aero conc (�g.m-3)
		qinti,&         ! int inorg aero conc (�g.m-3)
		surface_equilibrium_conc )        ! inorg eq gas conc (�g.m-3)

    do jesp=G1,G2!
      if(surface_equilibrium_conc(jesp).lt.TINYM) surface_equilibrium_conc(jesp)=0.d0
    enddo    
  end subroutine surface_eq_conc
   
End module Condensation