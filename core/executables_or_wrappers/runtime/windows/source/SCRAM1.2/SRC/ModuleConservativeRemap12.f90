! SCRAM1.2: CESM production moving-center two-pivot conservative remap.
! Source: cesm-scram-optics-20260915-r2 / RDB/moving_diam.f90.
! Water participates in transported mass but not dry geometry. Number and
! species mass use DIFFERENT weights; never reconstruct number from mass.
! Open end bins preserve out-of-range particles. Invalid orphan carriers
! are rejected by the standalone adapter before this kernel can remove them.
module ConservativeRemap12
  implicit none
contains
RECURSIVE SUBROUTINE MOVING_CENTER_DUALPIVOT(ns, naer, eh2o, dbound, fixed_diameter, &
                                  LMD, Qesp, N, Q)
  IMPLICIT NONE
  DOUBLE PRECISION, PARAMETER :: PI = 3.14159265358979323846D0

  INTEGER, INTENT(in) :: ns, naer, eh2o
  DOUBLE PRECISION, DIMENSION(ns+1), INTENT(in) :: dbound
  DOUBLE PRECISION, DIMENSION(ns), INTENT(in) :: fixed_diameter
  DOUBLE PRECISION, DIMENSION(naer), INTENT(in) :: LMD
  DOUBLE PRECISION, DIMENSION(ns,naer), INTENT(inout) :: Qesp
  DOUBLE PRECISION, DIMENSION(ns), INTENT(inout) :: N, Q

  INTEGER :: k, s, lo, hi
  DOUBLE PRECISION :: dry_mass, dry_volume, particle_volume, mean_diameter
  DOUBLE PRECISION :: wn_lo, wn_hi, wm_lo, wm_hi, denom, mass_weight_sum
  DOUBLE PRECISION :: n_before, n_after, n_discarded, tol_n, tol_m, bound_tol
  DOUBLE PRECISION :: out_mass, out_volume, out_diameter
  DOUBLE PRECISION, DIMENSION(ns) :: pivot_diameter, pivot_volume, Nout
  DOUBLE PRECISION, DIMENSION(ns,naer) :: Qout
  DOUBLE PRECISION, DIMENSION(naer) :: mass_before, mass_after, mass_discarded
  DOUBLE PRECISION, PARAMETER :: PI6_LOCAL = PI / 6.D0
  DOUBLE PRECISION, PARAMETER :: WEIGHT_EPS = 1.D-14
  DOUBLE PRECISION, PARAMETER :: CONS_REL_TOL = 5.D-12
  DOUBLE PRECISION, PARAMETER :: BOUND_REL_TOL = 5.D-10
  ! Do not inherit RDB/parameuler.inc TINYN=1e-6.  The coupled SCRAM core
  ! treats every positive prognostic number as a real particle population.
  ! Applying an absolute number cutoff here would delete dilute particles and
  ! recreate the exact mass-without-number state that moving-center removes.
  DOUBLE PRECISION, PARAMETER :: NUMBER_ZERO = 0.D0
  DOUBLE PRECISION, PARAMETER :: MASS_ZERO = 0.D0

  Nout = 0.D0
  Qout = 0.D0
  Q = 0.D0
  mass_before = 0.D0
  mass_after = 0.D0
  mass_discarded = 0.D0
  n_before = SUM(N)
  n_discarded = 0.D0

  DO s = 1, naer
     mass_before(s) = SUM(Qesp(:,s))
  END DO
  ! The legacy size_diam_av array is not a valid fixed-pivot grid for the
  ! explicit cfg boundaries: in the current 7-bin setup every legacy value is
  ! below its nominal bin lower bound.  Build legal logarithmic pivots directly
  ! from the actual fixed boundaries instead.  Keep fixed_diameter in the
  ! interface for backward ABI compatibility with the dispatcher.
  DO k = 1, ns
     IF (dbound(k) .LE. 0.D0 .OR. dbound(k+1) .LE. dbound(k)) &
        STOP 'MOVING_CENTER_DUALPIVOT: invalid fixed boundaries'
     pivot_diameter(k) = DSQRT(dbound(k) * dbound(k+1))
     pivot_volume(k) = PI6_LOCAL * pivot_diameter(k)**3
  END DO

  DO k = 1, ns
     dry_mass = 0.D0
     dry_volume = 0.D0
     DO s = 1, naer
        IF (s .NE. eh2o) THEN
           dry_mass = dry_mass + Qesp(k,s)
           IF (LMD(s) .GT. 0.D0) dry_volume = dry_volume + Qesp(k,s) / LMD(s)
        END IF
     END DO

     ! Number and dry mass form one physical carrier.  If either side is
     ! absent (or dry volume is invalid), discard the complete section and
     ! continue.  Track the intentional deletion separately so the conservative
     ! remap checks still apply to all retained sections.
     IF (N(k) .LE. NUMBER_ZERO .OR. dry_mass .LE. MASS_ZERO .OR. &
         dry_volume .LE. 0.D0) THEN
        n_discarded = n_discarded + MAX(N(k),0.D0)
        DO s = 1,naer
           mass_discarded(s) = mass_discarded(s) + MAX(Qesp(k,s),0.D0)
        END DO
        N(k)=0.D0
        Qesp(k,:)=0.D0
        CYCLE
     END IF

     particle_volume = dry_volume / N(k)
     IF (particle_volume .LE. 0.D0) THEN
        Nout(k) = Nout(k) + N(k)
        Qout(k,:) = Qout(k,:) + Qesp(k,:)
        CYCLE
     END IF
     mean_diameter = (particle_volume / PI6_LOCAL)**(1.D0/3.D0)
     bound_tol = BOUND_REL_TOL * MAX(dbound(k+1), 1.D-30)

     ! True moving center: do nothing while the section center remains in its
     ! own bin.  The first and last sections are open tails so particles below
     ! the first lower bound or above the last upper bound are retained without
     ! losing either moment.
     IF ((k .EQ. 1 .AND. mean_diameter .LE. dbound(2)+bound_tol) .OR. &
         (k .EQ. ns .AND. mean_diameter .GE. dbound(ns)-bound_tol) .OR. &
         (k .GT. 1 .AND. k .LT. ns .AND. &
          mean_diameter .GE. dbound(k)-bound_tol .AND. &
          mean_diameter .LE. dbound(k+1)+bound_tol)) THEN
        Nout(k) = Nout(k) + N(k)
        Qout(k,:) = Qout(k,:) + Qesp(k,:)
        CYCLE
     END IF

     ! Find the two fixed pivot volumes that bracket the escaped center.
     IF (particle_volume .LE. pivot_volume(1)) THEN
        lo = 1
        hi = 1
     ELSE IF (particle_volume .GE. pivot_volume(ns)) THEN
        lo = ns
        hi = ns
     ELSE
        lo = 1
        DO WHILE (lo .LT. ns .AND. particle_volume .GT. pivot_volume(lo+1))
           lo = lo + 1
        END DO
        hi = MIN(ns, lo+1)
     END IF

     IF (lo .EQ. hi) THEN
        Nout(lo) = Nout(lo) + N(k)
        Qout(lo,:) = Qout(lo,:) + Qesp(k,:)
        CYCLE
     END IF

     denom = pivot_volume(hi) - pivot_volume(lo)
     IF (denom .LE. 0.D0) STOP 'MOVING_CENTER_DUALPIVOT: invalid pivot volumes'

     wn_hi = (particle_volume - pivot_volume(lo)) / denom
     wn_hi = MAX(0.D0, MIN(1.D0, wn_hi))
     wn_lo = 1.D0 - wn_hi

     ! Collapse only a dimensionless machine-small interpolation weight.
     ! Never use an absolute number threshold here: doing so can move an entire
     ! low-concentration cohort to one pivot and violate its geometric support.
     IF (wn_lo .LE. WEIGHT_EPS) THEN
        Nout(hi) = Nout(hi) + N(k)
        Qout(hi,:) = Qout(hi,:) + Qesp(k,:)
        CYCLE
     ELSE IF (wn_hi .LE. WEIGHT_EPS) THEN
        Nout(lo) = Nout(lo) + N(k)
        Qout(lo,:) = Qout(lo,:) + Qesp(k,:)
        CYCLE
     END IF

     ! Species-mass weights differ from number weights.  They enforce
     ! V_lo/N_lo = pivot_volume(lo) and V_hi/N_hi = pivot_volume(hi), while
     ! preserving every species mass exactly.
     wm_lo = wn_lo * pivot_volume(lo) / particle_volume
     wm_hi = wn_hi * pivot_volume(hi) / particle_volume
     mass_weight_sum = wm_lo + wm_hi
     IF (mass_weight_sum .LE. 0.D0) STOP 'MOVING_CENTER_DUALPIVOT: invalid mass weights'
     wm_lo = wm_lo / mass_weight_sum
     wm_hi = 1.D0 - wm_lo

     Nout(lo) = Nout(lo) + N(k)*wn_lo
     Nout(hi) = Nout(hi) + N(k)*wn_hi
     DO s = 1, naer
        Qout(lo,s) = Qout(lo,s) + Qesp(k,s)*wm_lo
        Qout(hi,s) = Qout(hi,s) + Qesp(k,s)*wm_hi
     END DO
  END DO

  n_after = SUM(Nout)
  tol_n = CONS_REL_TOL * MAX(ABS(n_before-n_discarded), 1.D0)
  IF (ABS(n_after-(n_before-n_discarded)) .GT. tol_n) &
     STOP 'MOVING_CENTER_DUALPIVOT: number conservation failure'

  DO s = 1, naer
     mass_after(s) = SUM(Qout(:,s))
     tol_m = CONS_REL_TOL * MAX(ABS(mass_before(s)-mass_discarded(s)), 1.D-30)
     IF (ABS(mass_after(s)-(mass_before(s)-mass_discarded(s))) .GT. tol_m) &
        STOP 'MOVING_CENTER_DUALPIVOT: species mass conservation failure'
  END DO

  ! Validate that every populated output section has a moving center inside
  ! its fixed boundaries.  This is the invariant that makes all later
  ! mass->number reconstruction unnecessary.
  DO k = 1, ns
     out_mass = 0.D0
     out_volume = 0.D0
     DO s = 1, naer
        IF (s .NE. eh2o) THEN
           out_mass = out_mass + Qout(k,s)
           IF (LMD(s) .GT. 0.D0) out_volume = out_volume + Qout(k,s) / LMD(s)
        END IF
     END DO
     IF (Nout(k) .GT. NUMBER_ZERO .AND. out_mass .GT. MASS_ZERO .AND. &
         out_volume .GT. 0.D0) THEN
        out_diameter = (out_volume / Nout(k) / PI6_LOCAL)**(1.D0/3.D0)
        bound_tol = BOUND_REL_TOL * MAX(dbound(k+1), 1.D-30)
        IF ((k .EQ. 1 .AND. out_diameter .GT. dbound(2)+bound_tol) .OR. &
            (k .EQ. ns .AND. out_diameter .LT. dbound(ns)-bound_tol) .OR. &
            (k .GT. 1 .AND. k .LT. ns .AND. &
             (out_diameter .LT. dbound(k)-bound_tol .OR. &
              out_diameter .GT. dbound(k+1)+bound_tol))) THEN
           WRITE(*,'(A,I4,7ES18.9)') 'MOVING_CENTER_DUALPIVOT out-bin k=',k, &
             out_diameter,dbound(k),dbound(k+1),pivot_diameter(k), &
             Nout(k),out_volume,out_mass
           STOP 'MOVING_CENTER_DUALPIVOT: output center outside bin'
        END IF
     END IF
  END DO

  N = Nout
  Qesp = Qout
  DO k = 1, ns
     DO s = 1, naer
        IF (s .NE. eh2o) Q(k) = Q(k) + Qesp(k,s)
     END DO
  END DO
END SUBROUTINE MOVING_CENTER_DUALPIVOT
end module ConservativeRemap12
