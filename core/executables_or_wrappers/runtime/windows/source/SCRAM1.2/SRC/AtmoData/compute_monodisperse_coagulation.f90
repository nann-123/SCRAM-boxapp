!-----------------------------------------------------------------------
!     Copyright (C) 2006-2007, ENPC - INRIA - EDF R&D
!     Author(s): Vivien Mallet, Edouard Debry
!     
!     This file is part of AtmoData library, a tool for data processing
!     in atmospheric sciences.
!    
!     AtmoData is developed in the INRIA - ENPC joint project-team CLIME
!     and in the ENPC - EDF R&D joint laboratory CEREA.
!    
!     AtmoData is free software; you can redistribute it and/or modify
!     it under the terms of the GNU General Public License as published
!     by the Free Software Foundation; either version 2 of the License,
!     or (at your option) any later version.
!     
!     AtmoData is distributed in the hope that it will be useful, but
!     WITHOUT ANY WARRANTY; without even the implied warranty of
!     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
!     General Public License for more details.
!     
!     For more information, visit the AtmoData home page:
!          http://cerea.enpc.fr/polyphemus/atmodata.html
!-----------------------------------------------------------------------


!     Function: compute_coagulation_free_transition

!     Computes coagulation kernels for monodispersed
!     aerosols in the free transition regime.
!     2005/3/23: cleaning (Bruno Sportisse).

!     Parameters:
!     dp - aerosol diameter (µm).
!     vmp - mean particle velocity (m/s).
!     stick - sticking probability 0< <1 ().
!     cdifp - diffusion coefficient (m^2/s).
!     deltap - particle Knudsen number (µm).

!     Returns:
!     kercg - coagulation kernel (m^3/s).
      subroutine compute_coagulation_free_transition(dp, cdifp, deltap,&
          vmp, stick, kercg)

      double precision,parameter::pi = 3.141592653589d0

      double precision:: dp, cdifp, deltap
      double precision:: vmp, stick, kercg

      double precision:: beta, dpp

      dpp = dp * 1.d-06         ! convert µm to m

      beta = 1.d0 /&
          ( dp / (dp + deltap)& ! adim
          + 8.d0 * stick&       ! adim
          * cdifp&              ! m2.s - 1
          / vmp&                ! m.s - 1
          / dpp )              ! m
      
      kercg = 8.d0 * pi&         ! adim
          * cdifp&              ! m2.s - 1
          * dpp&                ! m
          * beta               ! adim
      
    end subroutine compute_coagulation_free_transition
      
      
!     Function: compute_coagulation_free_molecular
!
!     Computes coagulation kernels for monodispersed
!     aerosols in the free molecular regime.
!     2005/3/23: cleaning (Bruno Sportisse).
!
!     Parameters:
!     dp - aerosol diameter (µm).
!     vmp - mean particle velocity (m/s).
!     stick - sticking probability 0< <1 ().
!
!     Returns:
!     kercg - coagulation kernel (m^3/s).
      subroutine compute_coagulation_free_molecular(dp, vmp, stick,&
       kercg)

      double precision, parameter::pi = 3.141592653589d0

      double precision:: dp, vmp, stick, kercg

      double precision:: dpp

      dpp = dp * 1.d-06         ! convert µm to m
      
      kercg = pi&                ! adim
          * dpp * dpp&          ! m2
          * vmp&                ! m.s - 1
          * stick              ! adim

      end subroutine compute_coagulation_free_molecular


!     Function: compute_coagulation_continuous
!
!     Computes coagulation kernels for monodispersed
!     aerosols in the continuous regime.
!     2005/3/23: cleaning (Bruno Sportisse).
!
!     Parameters:
!     dp - aerosol diameter (µm).
!     cdifp - diffusion coefficient (m^2/s).
!
!     Returns:
!     kercg - coagulation kernel (m^3/s).
      subroutine compute_coagulation_continuous(dp, cdifp, kercg)

      double precision,parameter::pi = 3.141592653589d0

      double precision ::dp, cdifp, kercg

      double precision:: dpp

      dpp = dp * 1.d-06         ! convert µm to m
      
      kercg = 8.d0 * pi&         ! adim
          * cdifp&              ! m2.s - 1
          * dpp                ! m

    end subroutine compute_coagulation_continuous
