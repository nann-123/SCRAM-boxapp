!!-----------------------------------------------------------------------
!!     SCRAM ML Surrogate — Condensation Snapshot I/O Module
!!
!!     Records per-sub-step before/after snapshots for condensation only.
!!     Enabled by environment variable SCRAM_COND_SURR_IO=1.
!!     Output binary path controlled by SCRAM_COND_SURR_OUT.
!!
!!     Binary format (native stream, native doubles):
!!       Header:   magic(12 chars)  N_size(i4)  N_aerosol(i4)
!!       Records:  N pairs of [B, A] records per condensation sub-step.
!!                 'B' = before record:
!!                   tag(1 char), sub_dt(f64), t_now(f64),
!!                   Temperature(f64), Pressure(f64), RH(f64),
!!                   concentration_number(N_size), concentration_gas(N_aerosol),
!!                   concentration_mass(N_size, N_aerosol), wet_diameter(N_size)
!!                 'A' = after record:
!!                   tag(1 char), sub_dt(f64), t_now(f64),
!!                   delta_mass(N_size, N_aerosol), delta_number(N_size),
!!                   concentration_gas(N_aerosol), wet_diameter(N_size),
!!                   conservation_residual(f64)
!!-----------------------------------------------------------------------
MODULE CondSurrIO

  use Initialization

  implicit none

  private
  public :: cond_surr_open, cond_surr_close
  public :: cond_surr_record_before, cond_surr_record_after

  integer, parameter :: SURR_UNIT = 47
  logical            :: surr_enabled  = .false.
  logical            :: surr_opened   = .false.
  character(len=256) :: surr_filepath = ''

  !! Saved before-snapshot for computing delta in the after record
  double precision, allocatable :: snap_mass(:,:)
  double precision, allocatable :: snap_number(:)
  double precision, allocatable :: snap_gas(:)
  double precision, allocatable :: snap_diam(:)
  double precision               :: snap_dt   = 0.d0
  double precision               :: snap_t    = 0.d0

CONTAINS

  !!---------------------------------------------------------------------
  !! cond_surr_open: init from env vars, write file header.
  !! Call once after Init_distribution().
  !!---------------------------------------------------------------------
  subroutine cond_surr_open()
    character(len=256) :: env_val
    integer            :: ios
    character(len=12)  :: magic

    call get_environment_variable('SCRAM_COND_SURR_IO', env_val, status=ios)
    if (ios /= 0 .or. trim(env_val) /= '1') then
      surr_enabled = .false.
      return
    end if

    call get_environment_variable('SCRAM_COND_SURR_OUT', surr_filepath, status=ios)
    if (ios /= 0 .or. len_trim(surr_filepath) == 0) then
      surr_filepath = 'cond_surrogate_dataset.bin'
    end if

    open(unit=SURR_UNIT, file=trim(surr_filepath), &
         form='unformatted', access='stream', status='replace', iostat=ios)
    if (ios /= 0) then
      write(*,*) '[CondSurrIO] ERROR: cannot open output file: ', trim(surr_filepath)
      surr_enabled = .false.
      return
    end if

    !! Write header
    magic = 'COND_SURR_v1'
    write(SURR_UNIT) magic
    write(SURR_UNIT) int(N_size, 4)
    write(SURR_UNIT) int(N_aerosol, 4)

    !! Allocate workspace
    allocate(snap_mass(N_size, N_aerosol))
    allocate(snap_number(N_size))
    allocate(snap_gas(N_aerosol))
    allocate(snap_diam(N_size))

    surr_enabled = .true.
    surr_opened  = .true.
    write(*,*) '[CondSurrIO] Condensation surrogate I/O enabled -> ', trim(surr_filepath)
  end subroutine cond_surr_open

  !!---------------------------------------------------------------------
  !! cond_surr_close: flush and close. Call at program end.
  !!---------------------------------------------------------------------
  subroutine cond_surr_close()
    if (.not. surr_opened) return
    close(SURR_UNIT)
    if (allocated(snap_mass))   deallocate(snap_mass)
    if (allocated(snap_number)) deallocate(snap_number)
    if (allocated(snap_gas))    deallocate(snap_gas)
    if (allocated(snap_diam))   deallocate(snap_diam)
    surr_opened  = .false.
    surr_enabled = .false.
  end subroutine cond_surr_close

  !!---------------------------------------------------------------------
  !! cond_surr_record_before: save state snapshot before a condensation
  !! sub-step.  Only records when tag_cond == 1.
  !!---------------------------------------------------------------------
  subroutine cond_surr_record_before(dt, t_now)
    double precision, intent(in) :: dt, t_now
    character(len=1), parameter  :: TAG = 'B'

    if (.not. surr_enabled) return
    if (tag_cond /= 1) return

    !! Cache snapshot for delta computation in record_after
    snap_mass   = concentration_mass
    snap_number = concentration_number
    snap_gas    = concentration_gas
    snap_diam   = wet_diameter
    snap_dt     = dt
    snap_t      = t_now

    write(SURR_UNIT) TAG
    write(SURR_UNIT) dt
    write(SURR_UNIT) t_now
    write(SURR_UNIT) Temperature
    write(SURR_UNIT) Pressure
    write(SURR_UNIT) Relative_Humidity
    write(SURR_UNIT) concentration_number(1:N_size)
    write(SURR_UNIT) concentration_gas(1:N_aerosol)
    write(SURR_UNIT) concentration_mass(1:N_size, 1:N_aerosol)
    write(SURR_UNIT) wet_diameter(1:N_size)
  end subroutine cond_surr_record_before

  !!---------------------------------------------------------------------
  !! cond_surr_record_after: write the after-record with state delta.
  !! Call after solver + wet_diameter update, before mass_conservation().
  !!---------------------------------------------------------------------
  subroutine cond_surr_record_after()
    character(len=1), parameter  :: TAG = 'A'
    double precision :: delta_mass(N_size, N_aerosol)
    double precision :: delta_number(N_size)
    double precision :: cons_residual

    if (.not. surr_enabled) return
    if (tag_cond /= 1) return

    delta_mass   = concentration_mass   - snap_mass
    delta_number = concentration_number - snap_number

    !! max |sum_j delta_mass(j,jesp) + delta_gas(jesp)| should be ~0
    cons_residual = maxval( abs( &
      sum(delta_mass, dim=1) + (concentration_gas(1:N_aerosol) - snap_gas(1:N_aerosol)) ) )

    write(SURR_UNIT) TAG
    write(SURR_UNIT) snap_dt
    write(SURR_UNIT) snap_t
    write(SURR_UNIT) delta_mass(1:N_size, 1:N_aerosol)
    write(SURR_UNIT) delta_number(1:N_size)
    write(SURR_UNIT) concentration_gas(1:N_aerosol)
    write(SURR_UNIT) wet_diameter(1:N_size)
    write(SURR_UNIT) cons_residual
  end subroutine cond_surr_record_after

END MODULE CondSurrIO
