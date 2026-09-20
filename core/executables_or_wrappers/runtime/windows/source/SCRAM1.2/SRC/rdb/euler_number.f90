SUBROUTINE EULER_NUMBER(ns, nesp, dbound, grand, alpha, &
     d, diam, X, logdiam, kloc, LMD, rho, Qesp, N)

!!$------------------------------------------------------------------------
!!$     
!!$     -- INPUT VARIABLES
!!$     
!!$     
!!$     ns             : number of sections
!!$     nesp           : number of species
!!$     dbound         : list of limit bound diameter [\mu m]
!!$     grand          : list of 0 or 1
!!$                      1 = cutting with the upper box
!!$                      0 = cutting with the lower box
!!$     alpha          : list of fraction of each species in Q
!!$     diam           : list of mean diameter after condensation/evaporation
!!$     kloc           : list of bin where is diam
!!$     logdiam        : log(d)
!!$     X              : log(diam)
!!$     d              : list of mean diameter before condensation/evaporation
!!$     j              : time integration
!!$     section_pass   : bin include 100nm  
!!$     LMD            : list of liquid mass density of each species
!!$ 
!!$     -- VARIABLES
!!$     
!!$     Q              : Mass concentration
!!$     N_esp          : Number concentration by bin and species
!!$     rho            : density per bin
!!$     Eps_machine    : tolerance due to the lack of precision of the machine     
!!$     Ndonne_esp     : Temporary number concentration 
!!$     frac           : fraction define by X and logdiam
!!$     Qd             : fraction of concentration give at the adjacent bin
!!$
!!$     -- INPUT/OUTPUT VARIABLES
!!$      
!!$     N            : Number concentration by bin
!!$     Qesp         : Mass concentration by bin and species
!!$      
!!$     -- OUTPUT VARIABLES
!!$     
!!$     
!!$------------------------------------------------------------------------


  IMPLICIT NONE
  INCLUDE 'parameuler.inc'
  INCLUDE 'CONST.INC'

  ! ------ Input 
  INTEGER, INTENT(in) :: ns, nesp
  INTEGER, DIMENSION(ns), INTENT(in) :: grand
  DOUBLE PRECISION, DIMENSION(ns), INTENT(in) :: X, logdiam 
  DOUBLE PRECISION, DIMENSION(ns), INTENT(in) :: d , diam
  DOUBLE PRECISION, DIMENSION(ns+1), INTENT(in) ::dbound
  INTEGER, DIMENSION(ns), INTENT(in) :: kloc
  DOUBLE PRECISION, DIMENSION(ns, nesp), INTENT(in) :: alpha 
  DOUBLE PRECISION, DIMENSION(nesp), INTENT(in) :: LMD
  ! ------ Input/Output
  DOUBLE PRECISION, DIMENSION(ns), INTENT(inout) :: N
  DOUBLE PRECISION, DIMENSION(ns, nesp), INTENT(inout) :: Qesp
  ! ------
  INTEGER k, jesp
  DOUBLE PRECISION, DIMENSION(ns) :: rho
  DOUBLE PRECISION, DIMENSION(ns) :: Q
  DOUBLE PRECISION, DIMENSION(ns, nesp) :: N_esp, Ndonne_esp
  DOUBLE PRECISION Nd, frac
  DOUBLE PRECISION Nnouveau, Nancien


  Q = 0.d0
  DO k = 1,ns
     DO jesp = 1, nesp
        Q(k) = Q(k) + Qesp(k, jesp)
        N_esp(k, jesp) = alpha(k,jesp) * N(k)
     ENDDO
  ENDDO

  Ndonne_esp = 0.d0

  !***** test

  Nnouveau = 0.d0
  Nancien = 0.d0

  DO k = 1, ns
     Nancien = Nancien + N(k)
  ENDDO


  DO k = 1,ns 

     IF (grand(k) == 0)THEN

        IF (kloc(k) .NE. 1) THEN
           frac = (logdiam(k) - X(k))/ &
                (logdiam(k) - DLOG10(d(kloc(k)-1))) 
        ELSE
           frac = (logdiam(k) - X(k))/ &
                (logdiam(k) - DLOG10(dbound(1)))
        ENDIF

        DO jesp = 1, nesp

           Nd = N_esp(k, jesp) * frac

           IF (kloc(k) .NE. 1) THEN
              Ndonne_esp(kloc(k)-1, jesp)  = &
                   Ndonne_esp(kloc(k)-1, jesp) + Nd 
              Ndonne_esp(kloc(k), jesp) = &
                   Ndonne_esp(kloc(k), jesp) + N_esp(k, jesp) - Nd
           ELSE
              Ndonne_esp(kloc(k), jesp) = &
                   Ndonne_esp(kloc(k), jesp) + N_esp(k, jesp)
           ENDIF
           N_esp(k, jesp) = 0.d0
        ENDDO

     ELSE
        IF (kloc(k) .NE. ns) THEN
           frac = (X(k) - logdiam(k))/ &
                (DLOG10(d(kloc(k)+1)) - logdiam(k)) 
        ELSE
           frac = (X(k) - logdiam(k))/ &
                (DLOG10(dbound(ns+1)) - logdiam(k))
        ENDIF

        DO jesp = 1, nesp

           Nd =  N_esp(k, jesp) * frac

           IF (kloc(k) .NE. ns) THEN
              Ndonne_esp(kloc(k)+1,jesp) = &
                   Ndonne_esp(kloc(k)+1, jesp) + Nd
              Ndonne_esp(kloc(k), jesp) = &
                   Ndonne_esp(kloc(k), jesp) + N_esp(k, jesp) - Nd
           ELSE
              Ndonne_esp(kloc(k), jesp) = &
                   Ndonne_esp(kloc(k),jesp) + N_esp(k, jesp)
           ENDIF
           N_esp(k, jesp)=0.d0
        ENDDO
     ENDIF

  ENDDO



  N = 0.d0
  Q = 0.d0
  DO k = 1,ns
     DO jesp = 1, nesp
        N_esp(k, jesp) = N_esp(k, jesp) + Ndonne_esp(k, jesp)
        N(k) = N(k) + N_esp(k, jesp)
     ENDDO

     !***** Recalculation of mass concentration from number concentration 
     CALL COMPUTE_DENSITY(ns,nesp,N_esp,LMD,k,rho(k))

     DO jesp = 1, nesp
        Qesp(k, jesp) = rho(k) * (PI/6D0) * N_esp(k,jesp) &
             * (d(k)*d(k)*d(k))
        Q(k) = Q(k) + Qesp(k,jesp)
     ENDDO
  ENDDO


  !***** tests

  DO k = 1, ns
     Nnouveau = Nnouveau + N(k)
  ENDDO


  IF (DABS (1D0 - (Nnouveau/Nancien)) .GE. Eps_machine) then
     PRINT *, "1 - Nnew/Nold  =", 1D0 - (Nnouveau/Nancien)
     STOP
  ENDIF

  CALL TEST_MASS_NB(ns,nesp,rho,dbound,Q,N,Qesp)


END SUBROUTINE EULER_NUMBER


