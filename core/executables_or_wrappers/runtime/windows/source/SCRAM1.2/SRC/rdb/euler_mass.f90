SUBROUTINE EULER_MASS(ns, nesp, dbound, grand, X, diam, d, logdiam, &
     kloc, LMD, Qesp, N)

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
!!$     rho            : density per bin
!!$     Eps_machine    : tolerance due to the lack of precision of the machine     
!!$     Qdonne_esp     : Temporary Mass concentration 
!!$     frac           : fraction define by X and logdiam
!!$     Qd             : fraction of concentration give at the adjacent bin
!!$
!!$     -- INPUT/OUTPUT VARIABLES
!!$      
!!$     N              : Number concentration by bin
!!$     Qesp           : Mass concentration by bin and species
!!$      
!!$     -- OUTPUT VARIABLES
!!$     
!!$     
!!$------------------------------------------------------------------------

  IMPLICIT NONE
  INCLUDE 'parameuler.inc'
  INCLUDE 'CONST.INC'


  ! ------ Input 
  INTEGER, INTENT(in)::ns, nesp
  DOUBLE PRECISION, DIMENSION(ns), INTENT(in) :: X, logdiam
  DOUBLE PRECISION, DIMENSION(ns), INTENT(in) :: d , diam
  DOUBLE PRECISION, DIMENSION(ns+1), INTENT(in) ::dbound
  INTEGER, DIMENSION(ns), INTENT(in) :: grand
  INTEGER, DIMENSION(ns), INTENT(in) :: kloc
  DOUBLE PRECISION, DIMENSION(nesp), INTENT(in) :: LMD
  ! ------ Input/Output
  DOUBLE PRECISION, DIMENSION(ns, nesp), INTENT(inout) :: Qesp
  DOUBLE PRECISION, DIMENSION(ns), INTENT(inout) :: N
  ! ------ 
  INTEGER k, iesp
  DOUBLE PRECISION, DIMENSION(ns) :: rho
  DOUBLE PRECISION, DIMENSION(ns,nesp) :: Qdonne_esp
  DOUBLE PRECISION, DIMENSION(ns) :: Q
  DOUBLE PRECISION, DIMENSION(nesp) :: Q_ancien_esp, Q_nouveau_esp
  DOUBLE PRECISION Qd, frac
  DOUBLE PRECISION Qnouveau, Qancien


  DO k = 1, ns
     DO iesp=1,nesp
        Qdonne_esp(k,iesp) = 0D0
     ENDDO
  ENDDO


  DO k = 1, ns
     Q(k) =  0d0
     DO iesp = 1, nesp
        Q(k) = Q(k) + Qesp(k,iesp)
     ENDDO
  ENDDO
  !***** test

  Qnouveau = 0.d0
  Qancien = 0.d0

  DO k = 1, ns
     Qancien = Qancien + Q(k)
  ENDDO

  DO k = 1,ns 

     IF (grand(k) == 0) THEN

        IF (kloc(k) .NE. 1) THEN
           frac = (logdiam(k) - X(k))/&
                (logdiam(k) - DLOG10(d(kloc(k)-1))) 
        ELSE
           frac = (logdiam(k) - X(k))/&
                (logdiam(k) - DLOG10(dbound(1)))/2.D0
        ENDIF

        DO iesp = 1, nesp 
           Qd = Qesp(k,iesp) * frac 
           IF (kloc(k).NE.1) THEN 
              Qdonne_esp(kloc(k)-1, iesp) = &
                   Qdonne_esp(kloc(k)-1, iesp) + Qd
              Qdonne_esp(kloc(k), iesp) = &
                   Qdonne_esp(kloc(k), iesp) + Qesp(k, iesp) - Qd 
           ELSE              
              Qdonne_esp(kloc(k), iesp) = &
                   Qdonne_esp(kloc(k), iesp) + Qesp(k, iesp) 
           ENDIF
           Qesp(k, iesp) = 0.d0
        Enddo
     ELSE 
	IF (kloc(k) .NE. ns) THEN
           frac = (X(k) - logdiam(k))/&
                (DLOG10(d(kloc(k)+1)) - logdiam(k)) 
        ELSE
           frac = (X(k) - logdiam(k))/&
                (DLOG10(dbound(ns+1)) - logdiam(k))/2.D0
        ENDIF

        DO iesp = 1, nesp  
           Qd = Qesp(k, iesp) * frac
	  if(kloc(k).eq.1.and.frac.gt.2.d-1) then
	   endif
           IF (kloc(k).NE.ns) THEN 
              Qdonne_esp(kloc(k)+1, iesp) = &
                   Qdonne_esp(kloc(k)+1, iesp) + Qd
              Qdonne_esp(kloc(k), iesp) = &
                   Qdonne_esp(kloc(k), iesp) + Qesp(k, iesp) - Qd
           ELSE              
              Qdonne_esp(kloc(k), iesp) = &
                   Qdonne_esp(kloc(k), iesp) + Qesp(k, iesp)
           ENDIF
           Qesp(k, iesp) = 0.d0
        ENDDO
     ENDIF

  ENDDO

  !***** Recalculation of number concentration from mass concentration
  Q = 0.D0
  DO k = 1,ns
     DO iesp = 1,nesp
        Qesp(k, iesp) = Qesp(k, iesp) + Qdonne_esp(k, iesp) 
        Q(k) = Q(k) + Qesp(k, iesp)
     ENDDO
     CALL COMPUTE_DENSITY(ns,nesp,Qesp,LMD,k,rho(k))
     N(k) = (Q(k) * 6.D0)/(PI * rho(k) *(d(k)*d(k)*d(k))) 
  ENDDO

  !***** tests


  DO k = 1, ns
     Qnouveau = Qnouveau + Q(k)
  ENDDO


  IF (DABS (1D0 - (Qnouveau/Qancien)) .GE. Eps_machine) then
     PRINT *, "1 - Qnew/Qold  =", 1D0 - (Qnouveau/Qancien)
     PRINT *, "Too much mass lost, please use more size bin"
     STOP
  ENDIF

  CALL TEST_MASS_NB(ns,nesp,rho,dbound,Q,N,Qesp)

END SUBROUTINE EULER_MASS



