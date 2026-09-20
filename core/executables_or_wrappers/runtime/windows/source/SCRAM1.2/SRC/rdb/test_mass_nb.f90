SUBROUTINE TEST_MASS_NB(ns,Nesp,rho,dbound,Q,N,Qesp)

  IMPLICIT NONE

  INCLUDE '../INC/parameuler.inc'

  INTEGER k, jesp

  INTEGER, INTENT(in) :: ns, Nesp
  DOUBLE PRECISION, DIMENSION(ns), INTENT(in) :: rho
  DOUBLE PRECISION, DIMENSION(ns), INTENT(in) :: dbound
  DOUBLE PRECISION, DIMENSION(ns), INTENT(inout) :: Q, N 
  DOUBLE PRECISION :: Qmin,Qav
  DOUBLE PRECISION, DIMENSION(ns, Nesp), INTENT(inout) :: Qesp
  
 
  DO k = 1, ns

     !Qmin = rho(k) * (PI/6D0) * (dbound(k) ** 3D0)
     !Qav = rho(k) * (PI/6D0) * (sqrt(dbound(k)*dbound(k+1)) ** 3D0)
     IF (N(k) .LT. 0D0)THEN
        PRINT*, k,"stop, N negatif after redistribution"
        PRINT*, "N",N
        STOP
     ENDIF

     IF (Q(k) .LT. 0D0)THEN
        PRINT*, k,"stop, Q negatif after redistribution"
        PRINT*, "Q",Q
        STOP
     ENDIF

     !IF(Q(k) .LT. 1.D-19) THEN!we should conserve the mass
        !N(k) = Q(k)/Qav
     !ENDIF
  ENDDO

END SUBROUTINE TEST_MASS_NB
