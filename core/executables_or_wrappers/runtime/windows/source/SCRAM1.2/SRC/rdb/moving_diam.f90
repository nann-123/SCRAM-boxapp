SUBROUTINE MOVING_DIAM(ns, nesp, d_before, dbound, &
     d_after, LMD, rho, Qesp, N)

!!$------------------------------------------------------------------------
!!$     
!!$     -- DESCRIPTION 
!!$     
!!$     This subroutine redistribute the concentrations after the GDE.
!!$     Moving Diameter
!!$     
!!$------------------------------------------------------------------------
!!$     
!!$     -- INPUT VARIABLES
!!$     
!!$     
!!$     ns             : number of sections
!!$     nesp           : number of species
!!$     dbound         : list of limit bound diameter [\mu m]
!!$     d_after           : list of mean diameter after condensation/evaporation
!!$     d_before              : list of mean diameter before condensation/evaporation
!!$     LMD            : list of liquid mass density of each species
!!$ 
!!$     -- VARIABLES
!!$     
!!$     rho            : density per bin
!!$     Q_tmp     : Temporary Mass concentration 
!!$     N_tmp     : Temporary number concentration 
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


!!! ------ Input 
  INTEGER, INTENT(in) :: ns, nesp
  DOUBLE PRECISION, DIMENSION(ns), INTENT(in) :: d_before, d_after
  DOUBLE PRECISION, DIMENSION(ns+1), INTENT(in) :: dbound
  DOUBLE PRECISION, DIMENSION(nesp), INTENT(in) :: LMD

!!! ------ Input/Output 
  DOUBLE PRECISION, DIMENSION(ns), INTENT(inout) :: N
  DOUBLE PRECISION, DIMENSION(ns, nesp), INTENT(inout) :: Qesp

!!! ------  
  INTEGER k, jesp, s, i
  DOUBLE PRECISION, DIMENSION(ns) :: rho
  DOUBLE PRECISION, DIMENSION(ns) :: N_tmp
  DOUBLE PRECISION, DIMENSION(ns) :: Q  
  DOUBLE PRECISION, DIMENSION(ns, nesp) :: Q_tmp
  DOUBLE PRECISION Q_tot, N_tot
!!! ~~~~~~ Distribution of number concentration by species
    
    Q_tot=0.d0
    N_tot=0.d0
    do k=1,ns
      N_tmp(k)=0.d0!transver vector of Number
      N_tot=N_tot+N(k)
      do s= 1, nesp      
	Q_tmp(k,s)=0.d0!transver vector of Mass
	Q_tot=Q_tot+Qesp(k,s)
      enddo
    enddo
    
    do k=1,ns
      do i=1,ns-1!from k to i    
	if(d_after(k).ge.dbound(i).and.d_after(k).lt.dbound(i+1)) then
	  N_tmp(i)=N_tmp(i)+N(k)!defined which bin it will located	  
	  do s= 1, nesp      
	    Q_tmp(i,s)=Q_tmp(i,s)+Qesp(k,s)!transver vector of Mass
	    !print*,'d_after(k)',d_after(k),i,k,Q_tmp(i,s),Qesp(k,s)	    
	  enddo
	endif
      enddo
      if(d_after(k).ge.dbound(ns).and.d_after(k).le.dbound(ns+1)) then
	N_tmp(ns)=N_tmp(ns)+N(k)!defined which bin it will located	  
	do s= 1, nesp      
	  Q_tmp(ns,s)=Q_tmp(ns,s)+Qesp(k,s)!transver vector of Mass
	enddo      
      endif
    enddo
    !update each bin    
    Q_tot=0.d0
    N_tot=0.d0    
    do k=1,ns
      N(k)=N_tmp(k)!transver vector of Number
      N_tot=N_tot+N(k)      
      do s= 1, nesp      
	Qesp(k,s)=Q_tmp(k,s)!transver vector of Mass	
	Q_tot=Q_tot+Qesp(k,s)	
      enddo
    enddo
    
  Q = 0
  DO k = 1,ns!size bins
     DO jesp = 1, nesp!species
        Q(k) = Q(k) + Qesp(k, jesp)
     ENDDO
  ENDDO        
    
  CALL TEST_MASS_NB(ns,nesp,rho,dbound,Q,N,Qesp)

END SUBROUTINE MOVING_DIAM