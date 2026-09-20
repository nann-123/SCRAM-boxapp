!-----------------------------------------------------------------------
!     Copyright (C) 2005-2007, ENPC - INRIA - EDF R&D
!     
!     This file is part of the air quality modeling system Polyphemus.
!    
!     Polyphemus is developed in the INRIA - ENPC joint project-team
!     CLIME and in the ENPC - EDF R&D joint laboratory CEREA.
!    
!     Polyphemus is free software; you can redistribute it and/or modify
!     it under the terms of the GNU General Public License as published
!     by the Free Software Foundation; either version 2 of the License,
!     or (at your option) any later version.
!     
!     Polyphemus is distributed in the hope that it will be useful, but
!     WITHOUT ANY WARRANTY; without even the implied warranty of
!     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
!     General Public License for more details.
!     
!     For more information, visit the Polyphemus web site:
!     http://cerea.enpc.fr/polyphemus/
!-----------------------------------------------------------------------


      SUBROUTINE COMPUTE_DYNAMIC_VISCOSITY(Temperature,dyn_viscosity)
!------------------------------------------------------------------------
!     
!     -- DESCRIPTION 
!     
!     This function computes the dynamic air viscosity with the 
!     Sutherland law. Ref: Jacobson 1999, p92, eq. 4.55.
!     
!------------------------------------------------------------------------
!     
!     -- INPUT VARIABLES
!     
!     Temperature : temperature ([K]).
!     
!     -- OUTPUT VARIABLES
!     
!     dyn_viscosity: air viscosity ([kg/m/s]).
!     
!------------------------------------------------------------------------

      IMPLICIT NONE
      
      DOUBLE PRECISION:: Temperature, dyn_viscosity
      
      dyn_viscosity = 1.8325d-5 *(416.16d0/&
          ( Temperature + 120.d0))*&
          ( Temperature / 296.16d0 )**1.5d0

      RETURN
    END SUBROUTINE COMPUTE_DYNAMIC_VISCOSITY



      SUBROUTINE COMPUTE_AIR_FREE_MEAN_PATH(Temperature,&
      Pressure, air_free_mean_path, DLmuair)

!------------------------------------------------------------------------
!     
!     -- DESCRIPTION 
!     
!     This function computes the free mean path for air molecules.
!     on the basis of thermodynamic variables. It also returns dynamic
!     viscosity.
!     Ref: Seinfeld & Pandis 1998, page 455 (8.6)
!     
!------------------------------------------------------------------------
!     
!     -- INPUT VARIABLES
!     
!     Temperature : Temperature ([K]).
!     Pressure : Pressure    ([Pa]).
!     
!     -- INPUT/OUTPUT VARIABLES
!     
!     
!     -- OUTPUT VARIABLES
!     
!     AIR_FREE_MEAN_PATH : free mean path ([\micro m]).
!     DLMUAIR            : Dynamic viscosity ([kg/m/s]).
!     
!------------------------------------------------------------------------

      IMPLICIT NONE

      DOUBLE PRECISION:: Temperature,Pressure
      DOUBLE PRECISION:: air_free_mean_path, DLMUAIR
!     Perfect gas constant. ([J.mol-1.K-1])
      DOUBLE PRECISION RGAS
!     Pi.
      DOUBLE PRECISION PI
!     Molar mass of air. ([kg.mol-1])
      DOUBLE PRECISION MMair

      RGAS = 8.314D0
      PI=3.14159265358979323846D0
      MMair = 2.897D-02

      call COMPUTE_DYNAMIC_VISCOSITY(Temperature,DLMUAIR)
      AIR_FREE_MEAN_PATH = DSQRT(PI*RGAS*Temperature/(2.d0*MMAIR))&
       * DLMUAIR * 1.D6 / Pressure 

      RETURN
    END SUBROUTINE COMPUTE_AIR_FREE_MEAN_PATH

