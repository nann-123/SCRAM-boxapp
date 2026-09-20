      SUBROUTINE COMPUTE_DENSITY(nbin, nesp, Qesp, rho_esp, k, rho)

C------------------------------------------------------------------------
C     
C     -- DESCRIPTION 
C     
C     This is the main subroutine compute the density for a bin k
C     
C------------------------------------------------------------------------
C     
C     -- INPUT VARIABLES
C
C     nbin : number of bin
C     nesp : number of species
C     Qesp : concentration
C     rho_esp : list of density of each species
C     masstot : total mass
C     k : bin where is the calcul of rho
C
C     -- INPUT/OUTPUT VARIABLES
C
C     rho : density of bin k
C
C------------------------------------------------------------------------
C
C     -- REMARKS
C
C     rho = sum_j(Q(k,j)) / sum_j(Q(k,j)/rho_esp(j))
C
C------------------------------------------------------------------------      

      IMPLICIT NONE
      INCLUDE 'paraero.inc'
      
      INTEGER j,k
      
      INTEGER nbin, nesp 
      DOUBLE PRECISION  Qesp(nbin, nesp) 
      DOUBLE PRECISION  rho_esp(nesp)
      
      DOUBLE PRECISION rho
      DOUBLE PRECISION subrho, masstot
      

      rho = 0.d0
      subrho = 0.d0
      masstot = 0.d0
      
      do j = 1, nesp
       IF (Qesp(k,j).GT. 0.d0) THEN
         subrho = subrho + Qesp(k,j)/rho_esp(j)
         masstot = masstot + Qesp(k,j)
	ENDIF
	 !print*,'rho_esp',rho_esp(j)
      enddo

      if (masstot.EQ.0d0 .OR. subrho.EQ.0d0) then
         rho = 1.d0
      else
         rho = masstot/subrho
      endif
      


      
      END
