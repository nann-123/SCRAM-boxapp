SUBROUTINE redist_euler(ns, naer, scheme, dt, dbound, d_before, section_pass, LMD, Qesp, N)

!!$------------------------------------------------------------------------
!!$     
!!$     -- INPUT VARIABLES
!!$     
!!$     
!!$     ns             : number of sections
!!$     naer           : number of species
!!$     dbound         : list of limit bound diameter [\mu m]
!!$     d_before              : list of mean diameter before condensation/evaporation
!!$     scheme         : redistribution scheme
!!$                      3 = euler_mass
!!$                      4 = euler_number
!!$                      5 = hemen 
!!$                      6 = euler_coupled
!!$     dt              : time integration
!!$     section_pass   : bin include 100nm  
!!$     LMD            : list of liquid mass density of each species
!!$ 
!!$     -- VARIABLES
!!$     
!!$     Q              : Mass concentration
!!$     rho            : density per bin
!!$     
!!$     Eps_diam       : tolerance to the diameter which may be slightly above 
!!$                      the edge of the section
!!$     Eps_dbl_prec   : tolerance lower in the case where the diameter so little 
!!$                      increases or decreases as one considers that it is 
!!$                      not happening 
!!$                    : it can not work with a time not too restrictive 
!!$     grand          : list of 0 or 1
!!$                      1 = cutting with the upper box
!!$                      0 = cutting with the lower box
!!$     d_after           : list of mean diameter after condensation/evaporation
!!$     re_loc_bin           : list of bin where is d_after
!!$     log_rld_before        : log(d_before)
!!$     log_d_after              : log(re_loc_bin(d_after))
!!$     alpha          : list of fraction of each species in Q
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
  INCLUDE 'paraero.inc'
  INCLUDE 'CONST.INC'

  ! ------ Input
  INTEGER, INTENT(in) :: ns, naer, section_pass, scheme
  DOUBLE PRECISION, INTENT(in) :: dt
  DOUBLE PRECISION, DIMENSION(ns+1), INTENT(in) :: dbound
  DOUBLE PRECISION, DIMENSION(ns), INTENT(in) :: d_before
  DOUBLE PRECISION, DIMENSION(naer), INTENT(in) :: LMD

  ! ------ Input/Output
  DOUBLE PRECISION, DIMENSION(ns), INTENT(inout) :: N
  DOUBLE PRECISION, DIMENSION(ns, naer), INTENT(inout) :: Qesp

  ! ------ 
  INTEGER k, js, jaer, loc
  DOUBLE PRECISION, DIMENSION(ns) :: rho
  DOUBLE PRECISION, DIMENSION(ns) :: Q
  INTEGER, DIMENSION(ns) :: grand
  INTEGER, DIMENSION(ns) :: re_loc_bin
  DOUBLE PRECISION :: d_current
  DOUBLE PRECISION , DIMENSION(ns) :: log_d_after, log_rld_before,d_after
  DOUBLE PRECISION, DIMENSION(ns,naer) :: alpha
  DOUBLE PRECISION :: total_vol
  !DOUBLE PRECISION :: QLM,NLM

  !! Calcul of d_before(k) = dsqrt(dbound(k)*dbound(k+1))
  !! Reestimate d_before(k) from number and mass concentration BEFORE condensation/evaporation
  !TINYM=1D-9
  !NLM=1D-3
  !***** Calcul total mass per bin
  Q=0.D0
  DO js = 1, ns
     DO jaer = 1, naer
	IF(Qesp(js, jaer).GT. 0.D0) THEN
        Q(js)= Q(js) + Qesp(js, jaer)
	ELSE
	Qesp(js, jaer)=0.d0
	ENDIF
     ENDDO
  ENDDO
  !***** Calcul fraction of each composant of mass
  DO js = 1, ns!size bins
     DO jaer = 1, naer!species
        IF (Q(js) .NE. 0.D0) THEN
           alpha(js,jaer) = Qesp(js, jaer)/Q(js)
        ELSE
           alpha(js, jaer) = 1.D0
        ENDIF
     ENDDO
  ENDDO

  !print*,'n1',N(1)
  !print*,'m1',Q(1)
  !****** Calcul of new mean diameter after c/e
  DO k = 1, ns
     !CALL compute_density(ns,naer,Qesp,LMD, k, rho(k))
     total_vol=0.D0
     IF ( N(k) .GE. TINYN .AND. Q(k) .GE. naer*TINYM) THEN
	DO jaer = 1, naer
	  total_vol=total_vol+Qesp(k, jaer)/LMD(jaer)!SZ
	ENDDO
	d_current=((total_vol* 6D0)/(PI *N(k)))**(1D0/3D0)
        !d_current = ((Q(k) * 6D0)/(PI * rho(k) * N(k)))**(1D0/3D0)
        !print*,k,Q(k),N(k),d_current
        !IF (d_current.ne.d_before(k)) then
        !print*,'d_current',d_current,'d_before(',k,')',d_before(k)
        !endif
        IF (d_current .LT. dbound(1)) THEN
           d_current = d_before(1)
           re_loc_bin(k) = 1 
        ELSEIF (d_current .GT. dbound(ns+1)) THEN
           d_current = dbound(ns+1)
           re_loc_bin(k)= ns 
        ELSE
           loc = 1
           DO WHILE(d_current .GT. dbound(loc+1))
              loc=loc+1
           ENDDO
           re_loc_bin(k) = loc
        ENDIF
     ELSE
        d_current = d_before(k)
        re_loc_bin(k)=k
     ENDIF

     d_after(k) = d_current!d_current diam_after
     log_d_after(k) = DLOG10(d_current)

     IF(d_current .GT. d_before(re_loc_bin(k))) THEN
     !print*,'d_current',d_current,'d_before',d_before(re_loc_bin(k)),'k',k,'n',re_loc_bin(k)
        grand(k) = 1 
     ELSE
        grand(k) = 0 
     ENDIF
   
     IF (d_current .LT. dbound(re_loc_bin(k)) .AND. &
          DABS(d_current/dbound(re_loc_bin(k)) - 1D0) .GT. Eps_diam) THEN
        PRINT*,dt,k,'Time step is too big'
        PRINT*,dt,k,"d_current",d_current
        PRINT*,dt,k,"dbound(k)     ",dbound(re_loc_bin(k))
        PRINT*,dt,k,"N(k)",N(k)
        PRINT*,dt,k,"Q(k)",Q(k)
        PRINT*,dt,k,"d_before(k)",d_before(k)
        STOP 
     ENDIF
     
     IF (d_current .GT. dbound(re_loc_bin(k)+1) .AND. &
          DABS(dbound(re_loc_bin(k)+1)/d_current - 1D0) .GT. Eps_diam) THEN
        PRINT*,dt,k,'Time step is too big'
        PRINT*,dt,k,"d_current",d_current
        PRINT*,dt,k,"dbound(k+1)     ",dbound(re_loc_bin(k)+1)
        PRINT*,dt,k,"N(k)",N(k)
        PRINT*,dt,k,"Q(k)",Q(k)
        PRINT*,dt,k,"d_before(k)",d_before(k)
        STOP 
     ENDIF


     IF(DABS(d_current - d_before(re_loc_bin(k))) .LT. Eps_dbl_prec) THEN
        d_current = d_before(re_loc_bin(k))   
        d_after(k) = d_before(re_loc_bin(k))  
     ENDIF

     log_rld_before(k) = DLOG10(d_before(re_loc_bin(k)))

  ENDDO

    !print*,'d_after',d_after
  !****** Select the redistribution method

  SELECT CASE (scheme)
  CASE (2)
     CALL MOVING_DIAM(ns, naer, d_before, dbound, &
     d_after, LMD, rho, Qesp, N)  
  
  CASE (3)
     CALL EULER_MASS(ns, naer, dbound, grand, &
          log_d_after, d_after, d_before, log_rld_before, re_loc_bin, LMD, Qesp, N)

  CASE (4)
     CALL EULER_NUMBER(ns, naer, dbound, grand, alpha, &
          d_before, d_after, log_d_after, log_rld_before, re_loc_bin, LMD, rho, Qesp, N)

  CASE (5)
     CALL HEMEN(ns, naer, grand, section_pass, d_before, &
          dbound, log_d_after, d_after, log_rld_before, re_loc_bin, alpha, LMD, &
          rho, Qesp, N)

  CASE (6)
     CALL EULER_COUPLED(ns, naer,dbound, grand, d_before, d_after, &
          dt, re_loc_bin, alpha, LMD, Qesp, N)

  CASE DEFAULT
     PRINT*, "Please choose from the following redistribution methods : ", &
          "number-conserving, interpolation, euler-mass, euler-number, ",&
          "hemen, euler-coupled."
  END SELECT
! Total mass
  Q=0.D0
  DO js = 1, ns
     DO jaer = 1, naer
        Q(js)= Q(js) + Qesp(js, jaer) 
     ENDDO
  ENDDO
END SUBROUTINE REDIST_EULER

