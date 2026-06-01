module CoeffRepartitionBoxmodel
  use Initialization
  implicit none

  integer, parameter :: COEFF_REPARTITION_LEGACY = 0
  integer, parameter :: COEFF_REPARTITION_DETERMINISTIC_NEAREST = 1
  integer, parameter :: COEFF_REPARTITION_WEIGHTED_CURRENT = 2
  integer, parameter :: COEFF_REPARTITION_WEIGHTED_SOFT = 3
  integer, parameter :: COEFF_REPARTITION_LCP = 4
  integer, parameter :: COEFF_CACHE_ALWAYS_REBUILD = 0
  integer, parameter :: COEFF_CACHE_REUSE_IF_SIGNATURE_MATCH = 1
  integer, parameter :: COEFF_CACHE_STATUS_NA = 0
  integer, parameter :: COEFF_CACHE_STATUS_HIT = 1
  integer, parameter :: COEFF_CACHE_STATUS_MISS = 2
  integer, parameter :: COEFF_IO_UNIT = 97
  integer, parameter :: COEFF_MAX_CANDIDATES = 4
  integer, parameter :: COEFF_MAX_COMP_CANDIDATES_PER_SIZE = 1
  double precision, parameter :: COEFF_SIGNATURE_DIAM_REL_TOL = 2.d-2
  double precision, parameter :: COEFF_SIGNATURE_GROUP_ABS_TOL = 5.d-3
  double precision, parameter :: COEFF_COMP_EPS = 1.d-10
  double precision, parameter :: COEFF_WEIGHTED_MIN_SPLIT = 0.15d0
  double precision, parameter :: COEFF_SOFT_TAU = 0.35d0
  double precision, parameter :: COEFF_LCP_LAMBDA_D = 4.d0
  double precision, parameter :: COEFF_LCP_LAMBDA_F = 1.d0

  integer :: coeff_repartition_mode = COEFF_REPARTITION_LEGACY
  integer :: coeff_cache_mode = COEFF_CACHE_ALWAYS_REBUILD
  integer :: coeff_step_index = 0
  integer :: coeff_active_bins = 0
  integer :: coeff_active_pairs = 0
  integer :: coeff_skipped_pairs = 0
  integer :: coeff_cache_hits = 0
  integer :: coeff_cache_misses = 0
  integer :: coeff_last_cache_status = COEFF_CACHE_STATUS_NA
  integer :: coeff_pair_count = 0
  integer :: coeff_mapping_build_count = 0
  integer :: coeff_total_mapping_calls = 0
  integer :: coeff_last_mapping_calls_step = 0
  integer :: coeff_total_fallback_mappings = 0
  integer :: coeff_last_fallback_count_step = 0

  logical :: coeff_csv_initialized = .false.
  logical :: coeff_pair_mapping_valid = .false.
  logical :: coeff_step_audit_initialized = .false.

  character(len=64) :: coeff_repartition_mode_name = 'LEGACY'
  character(len=64) :: coeff_cache_mode_name = 'ALWAYS_REBUILD'
  character(len=128) :: coeff_scheme_name = 'legacy'
  character(len=128) :: coeff_testcase = 'default'
  character(len=128) :: coeff_process_combo = 'unknown'
  character(len=256) :: coeff_results_dir = 'results/coag_lcp_weighted/default'

  double precision :: coeff_last_mapping_build_seconds = 0.d0
  double precision :: coeff_total_mapping_build_seconds = 0.d0
  double precision :: coeff_last_step_runtime = 0.d0
  double precision :: coeff_previous_total_number = -1.d0
  double precision :: coeff_last_objective_mean_step = 0.d0
  double precision :: coeff_step_total_mass_before = 0.d0
  double precision :: coeff_step_total_number_before = 0.d0
  double precision :: coeff_last_coag_mass_before = 0.d0
  double precision :: coeff_last_coag_mass_after = 0.d0
  double precision :: coeff_last_coag_mass_residual = 0.d0
  double precision :: coeff_last_coag_number_before = 0.d0
  double precision :: coeff_last_coag_number_after = 0.d0
  double precision :: coeff_last_coag_number_residual = 0.d0
  double precision :: coeff_last_coag_event_rate_sum = 0.d0
  double precision :: coeff_last_min_mass = 0.d0
  double precision :: coeff_last_min_number = 0.d0
  double precision :: coeff_last_min_gas = 0.d0
  double precision :: coeff_last_step_total_mass_after = 0.d0
  double precision :: coeff_last_step_total_number_after = 0.d0
  double precision :: coeff_last_step_time_seconds = 0.d0

  integer, allocatable :: coeff_pair_src1(:)
  integer, allocatable :: coeff_pair_src2(:)
  integer, allocatable :: coeff_pair_candidate_count(:)
  integer, allocatable :: coeff_pair_candidate_cells(:,:)
  double precision, allocatable :: coeff_pair_candidate_weights(:,:)
  double precision, allocatable :: coeff_pair_target_mass(:)
  double precision, allocatable :: coeff_pair_target_diameter(:)
  double precision, allocatable :: coeff_pair_target_density(:)
  double precision, allocatable :: coeff_pair_target_groupfrac(:,:)
  double precision, allocatable :: coeff_pair_objective_value(:)
  integer, allocatable :: coeff_pair_fallback_flag(:)
  integer, allocatable :: coeff_signature_active(:)
  double precision, allocatable :: coeff_signature_diameter(:)
  double precision, allocatable :: coeff_signature_groupfrac(:,:)
  double precision, allocatable :: coeff_last_delta_number(:)
  double precision, allocatable :: coeff_last_delta_mass(:,:)

contains

  subroutine coeff_boxmodel_init()
    implicit none
    character(len=256) :: env_value
    integer :: stat

    call get_environment_variable('SCRAM_COEFF_REPARTITION_MODE', env_value, status=stat)
    if (stat == 0) then
      call coeff_parse_repartition_mode(trim(env_value))
    else
      coeff_repartition_mode = COEFF_REPARTITION_LEGACY
    endif

    call get_environment_variable('SCRAM_COEFF_CACHE_MODE', env_value, status=stat)
    if (stat == 0) then
      call coeff_parse_cache_mode(trim(env_value))
    else
      coeff_cache_mode = COEFF_CACHE_ALWAYS_REBUILD
    endif

    call get_environment_variable('SCRAM_RESULTS_DIR', env_value, status=stat)
    if (stat == 0 .and. len_trim(env_value) > 0) then
      coeff_results_dir = trim(env_value)
    endif

    call get_environment_variable('SCRAM_TESTCASE', env_value, status=stat)
    if (stat == 0 .and. len_trim(env_value) > 0) then
      coeff_testcase = trim(env_value)
    endif

    call get_environment_variable('SCRAM_PROCESS_COMBO', env_value, status=stat)
    if (stat == 0 .and. len_trim(env_value) > 0) then
      coeff_process_combo = trim(env_value)
    endif

    call get_environment_variable('SCRAM_SCHEME_NAME', env_value, status=stat)
    if (stat == 0 .and. len_trim(env_value) > 0) then
      coeff_scheme_name = trim(env_value)
    else
      coeff_scheme_name = trim(coeff_repartition_mode_name)
      if (coeff_repartition_mode /= COEFF_REPARTITION_LEGACY) then
        coeff_scheme_name = trim(coeff_scheme_name) // '+' // trim(coeff_cache_mode_name)
      endif
    endif

    call coeff_make_dir(trim(coeff_results_dir) // '/csv')
    call coeff_make_dir(trim(coeff_results_dir) // '/figures')
    call coeff_make_dir(trim(coeff_results_dir) // '/logs')

    coeff_step_index = 0
    coeff_active_bins = 0
    coeff_active_pairs = 0
    coeff_skipped_pairs = 0
    coeff_cache_hits = 0
    coeff_cache_misses = 0
    coeff_last_cache_status = COEFF_CACHE_STATUS_NA
    coeff_last_mapping_build_seconds = 0.d0
    coeff_total_mapping_build_seconds = 0.d0
    coeff_last_step_runtime = 0.d0
    coeff_previous_total_number = -1.d0
    coeff_pair_mapping_valid = .false.
    coeff_pair_count = 0
    coeff_mapping_build_count = 0
    coeff_total_mapping_calls = 0
    coeff_last_mapping_calls_step = 0
    coeff_total_fallback_mappings = 0
    coeff_last_fallback_count_step = 0
    coeff_last_objective_mean_step = 0.d0
    coeff_step_total_mass_before = 0.d0
    coeff_step_total_number_before = 0.d0
    coeff_step_audit_initialized = .false.
    coeff_last_coag_mass_before = 0.d0
    coeff_last_coag_mass_after = 0.d0
    coeff_last_coag_mass_residual = 0.d0
    coeff_last_coag_number_before = 0.d0
    coeff_last_coag_number_after = 0.d0
    coeff_last_coag_number_residual = 0.d0
    coeff_last_coag_event_rate_sum = 0.d0
    coeff_last_min_mass = 0.d0
    coeff_last_min_number = 0.d0
    coeff_last_min_gas = 0.d0
    coeff_last_step_total_mass_after = 0.d0
    coeff_last_step_total_number_after = 0.d0
    coeff_last_step_time_seconds = 0.d0

    call coeff_allocate_delta_arrays()
    call coeff_init_csv_files()
  end subroutine coeff_boxmodel_init

  subroutine coeff_make_dir(path)
    implicit none
    character(len=*), intent(in) :: path
    character(len=512) :: path_win
    character(len=1100) :: command
    integer :: i

    path_win = trim(path)
    do i = 1, len_trim(path_win)
      if (path_win(i:i) == '/') path_win(i:i) = '\'
    enddo
    command = 'cmd /c if not exist "' // trim(path_win) // '" mkdir "' // trim(path_win) // '"'
    call execute_command_line(trim(command))
  end subroutine coeff_make_dir

  subroutine coeff_allocate_delta_arrays()
    implicit none
    if (allocated(coeff_last_delta_number)) deallocate(coeff_last_delta_number)
    if (allocated(coeff_last_delta_mass)) deallocate(coeff_last_delta_mass)
    allocate(coeff_last_delta_number(N_size))
    allocate(coeff_last_delta_mass(N_size, N_aerosol))
    coeff_last_delta_number = 0.d0
    coeff_last_delta_mass = 0.d0
  end subroutine coeff_allocate_delta_arrays

  subroutine coeff_init_csv_files()
    implicit none
    character(len=512) :: file_name

    file_name = trim(coeff_results_dir) // '/csv/timestep_summary.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,total_mass,total_number,active_bins,active_pairs,skipped_pairs,mapping_mode,cache_status,runtime_step,testcase,process_combo,scheme'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/species_mass_timeseries.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,species_index,species_name,total_mass,testcase,process_combo,scheme'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/size_distribution_number.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,size_bin,representative_diameter,number,dN_dlogD,testcase,process_combo,scheme'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/size_distribution_mass.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,size_bin,representative_diameter,total_mass,dM_dlogD,testcase,process_combo,scheme'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/size_composition_mass.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,size_bin,composition_bin,mass,testcase,process_combo,scheme'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/size_composition_number.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,size_bin,composition_bin,number,testcase,process_combo,scheme'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/composition_diversity.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,size_bin,diversity,testcase,process_combo,scheme'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/coag_delta_number.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,cell_index,size_bin,composition_bin,delta_number,testcase,process_combo,scheme'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/coag_delta_mass.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,cell_index,size_bin,composition_bin,species_index,species_name,delta_mass,testcase,process_combo,scheme'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/anomaly_flags.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,anomaly_type,size_bin,composition_bin,value,threshold,testcase,process_combo,scheme'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/mapping_events.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,src_cell1,src_cell2,src_sizebin1,src_sizebin2,target_mass,target_diameter,target_density,target_group_fractions,candidate_cells,candidate_weights,scheme,fallback_flag,objective_value'
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/conservation_audit.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='replace', action='write')
    write(COEFF_IO_UNIT,'(A)') 'timestep,time_seconds,total_mass_before,total_mass_after,total_number_before,total_number_after,coag_mass_before,coag_mass_after,coag_mass_residual,coag_number_before,coag_number_after,coag_number_residual,coag_event_rate_sum,min_mass,min_number,min_gas,has_nan,has_inf,mapping_calls_step,mapping_build_time,mean_objective,fallback_mappings,scheme,testcase,process_combo'
    close(COEFF_IO_UNIT)

    coeff_csv_initialized = .true.
  end subroutine coeff_init_csv_files

  subroutine coeff_set_step_runtime(runtime_step)
    implicit none
    double precision, intent(in) :: runtime_step
    coeff_last_step_runtime = runtime_step
  end subroutine coeff_set_step_runtime

  subroutine coeff_mark_step_start()
    implicit none
    integer :: s, jesp

    coeff_step_total_mass_before = 0.d0
    do s = 1, N_species
      jesp = List_species(s)
      coeff_step_total_mass_before = coeff_step_total_mass_before + sum(concentration_mass(:,jesp))
    enddo
    coeff_step_total_number_before = sum(concentration_number)
    coeff_step_audit_initialized = .true.
  end subroutine coeff_mark_step_start

  logical function coeff_use_legacy_mode()
    implicit none
    coeff_use_legacy_mode = (coeff_repartition_mode == COEFF_REPARTITION_LEGACY)
  end function coeff_use_legacy_mode

  subroutine coeff_parse_repartition_mode(mode_text)
    implicit none
    character(len=*), intent(in) :: mode_text
    character(len=256) :: upper_text

    upper_text = coeff_upper(mode_text)
    select case (trim(upper_text))
    case ('LEGACY')
      coeff_repartition_mode = COEFF_REPARTITION_LEGACY
      coeff_repartition_mode_name = 'LEGACY'
    case ('DETERMINISTIC_NEAREST', 'DETERMINISTIC_BOX', 'DETERMINISTIC_BOX_NEAREST', 'COAG_TARGET_NEAREST')
      coeff_repartition_mode = COEFF_REPARTITION_DETERMINISTIC_NEAREST
      coeff_repartition_mode_name = 'COAG_TARGET_NEAREST'
    case ('DETERMINISTIC_WEIGHTED', 'DETERMINISTIC_CONSERVATIVE_WEIGHTED', 'COAG_TARGET_WEIGHTED_CURRENT')
      coeff_repartition_mode = COEFF_REPARTITION_WEIGHTED_CURRENT
      coeff_repartition_mode_name = 'COAG_TARGET_WEIGHTED_CURRENT'
    case ('DETERMINISTIC_WEIGHTED_SOFT', 'COAG_TARGET_WEIGHTED_SOFT')
      coeff_repartition_mode = COEFF_REPARTITION_WEIGHTED_SOFT
      coeff_repartition_mode_name = 'COAG_TARGET_WEIGHTED_SOFT'
    case ('DETERMINISTIC_LCP', 'COAG_TARGET_LCP', 'LCP')
      coeff_repartition_mode = COEFF_REPARTITION_LCP
      coeff_repartition_mode_name = 'COAG_TARGET_LCP'
    case default
      coeff_repartition_mode = COEFF_REPARTITION_LEGACY
      coeff_repartition_mode_name = 'LEGACY'
    end select
  end subroutine coeff_parse_repartition_mode

  subroutine coeff_parse_cache_mode(mode_text)
    implicit none
    character(len=*), intent(in) :: mode_text
    character(len=256) :: upper_text

    upper_text = coeff_upper(mode_text)
    select case (trim(upper_text))
    case ('ALWAYS_REBUILD')
      coeff_cache_mode = COEFF_CACHE_ALWAYS_REBUILD
      coeff_cache_mode_name = 'ALWAYS_REBUILD'
    case ('REUSE_IF_SIGNATURE_MATCH', 'REUSE')
      coeff_cache_mode = COEFF_CACHE_REUSE_IF_SIGNATURE_MATCH
      coeff_cache_mode_name = 'REUSE_IF_SIGNATURE_MATCH'
    case default
      coeff_cache_mode = COEFF_CACHE_ALWAYS_REBUILD
      coeff_cache_mode_name = 'ALWAYS_REBUILD'
    end select
  end subroutine coeff_parse_cache_mode

  function coeff_upper(input_text) result(output_text)
    implicit none
    character(len=*), intent(in) :: input_text
    character(len=len(input_text)) :: output_text
    integer :: i, icode

    output_text = input_text
    do i = 1, len_trim(input_text)
      icode = iachar(input_text(i:i))
      if (icode >= iachar('a') .and. icode <= iachar('z')) then
        output_text(i:i) = achar(icode - 32)
      endif
    enddo
  end function coeff_upper

  subroutine coeff_prepare_pair_mapping(c_number, c_mass)
    implicit none
    double precision, intent(in) :: c_number(N_size)
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    double precision :: t_start, t_end
    logical :: reuse_mapping

    if (coeff_use_legacy_mode()) then
      coeff_last_cache_status = COEFF_CACHE_STATUS_NA
      call coeff_count_active_state(c_number, c_mass)
      return
    endif

    call cpu_time(t_start)
    reuse_mapping = .false.

    if (coeff_cache_mode == COEFF_CACHE_REUSE_IF_SIGNATURE_MATCH .and. coeff_pair_mapping_valid) then
      reuse_mapping = coeff_signature_matches(c_number, c_mass)
    endif

    if (reuse_mapping) then
      coeff_cache_hits = coeff_cache_hits + 1
      coeff_last_cache_status = COEFF_CACHE_STATUS_HIT
      coeff_last_mapping_build_seconds = 0.d0
      call coeff_count_active_state(c_number, c_mass)
      return
    endif

    call coeff_build_pair_mapping(c_number, c_mass)
    coeff_pair_mapping_valid = .true.
    coeff_cache_misses = coeff_cache_misses + 1
    coeff_last_cache_status = COEFF_CACHE_STATUS_MISS

    call cpu_time(t_end)
    coeff_last_mapping_build_seconds = t_end - t_start
    coeff_total_mapping_build_seconds = coeff_total_mapping_build_seconds + coeff_last_mapping_build_seconds
  end subroutine coeff_prepare_pair_mapping

  subroutine coeff_count_active_state(c_number, c_mass)
    implicit none
    double precision, intent(in) :: c_number(N_size)
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    integer :: i, j
    double precision :: cell_mass

    coeff_active_bins = 0
    coeff_active_pairs = 0
    do i = 1, N_size
      cell_mass = coeff_cell_total_mass(i, c_mass)
      if (c_number(i) > TINYN .and. cell_mass > dble(N_species) * TINYM) then
        coeff_active_bins = coeff_active_bins + 1
      endif
    enddo
    do i = 1, N_size
      if (c_number(i) <= TINYN) cycle
      do j = 1, i
        if (c_number(j) <= TINYN) cycle
        coeff_active_pairs = coeff_active_pairs + 1
      enddo
    enddo
    coeff_skipped_pairs = (N_size * (N_size + 1) / 2) - coeff_active_pairs
  end subroutine coeff_count_active_state

  logical function coeff_signature_matches(c_number, c_mass)
    implicit none
    double precision, intent(in) :: c_number(N_size)
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    integer :: i, g
    double precision :: cell_mass, group_mass(N_groups), frac

    coeff_signature_matches = .false.
    if (.not. allocated(coeff_signature_active)) return
    if (.not. allocated(coeff_signature_diameter)) return
    if (.not. allocated(coeff_signature_groupfrac)) return

    do i = 1, N_size
      cell_mass = coeff_cell_total_mass(i, c_mass)
      if (coeff_active_cell(c_number(i), cell_mass) /= coeff_signature_active(i)) return
      if (coeff_signature_active(i) == 0) cycle
      if (.not. coeff_close_rel(cell_diam_av(i), coeff_signature_diameter(i), COEFF_SIGNATURE_DIAM_REL_TOL)) return
      call coeff_group_mass_for_cell(i, c_mass, group_mass)
      do g = 1, N_groups
        frac = 0.d0
        if (cell_mass > 0.d0) frac = group_mass(g) / cell_mass
        if (.not. coeff_close_abs(frac, coeff_signature_groupfrac(i,g), COEFF_SIGNATURE_GROUP_ABS_TOL)) return
      enddo
    enddo

    coeff_signature_matches = .true.
  end function coeff_signature_matches

  logical function coeff_close_rel(a_value, b_value, tolerance)
    implicit none
    double precision, intent(in) :: a_value, b_value, tolerance
    double precision :: scale

    scale = max(1.d0, abs(a_value), abs(b_value))
    coeff_close_rel = (abs(a_value - b_value) <= tolerance * scale)
  end function coeff_close_rel

  logical function coeff_close_abs(a_value, b_value, tolerance)
    implicit none
    double precision, intent(in) :: a_value, b_value, tolerance
    coeff_close_abs = (abs(a_value - b_value) <= tolerance)
  end function coeff_close_abs

  subroutine coeff_store_signature(c_number, c_mass)
    implicit none
    double precision, intent(in) :: c_number(N_size)
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    integer :: i, g
    double precision :: cell_mass, group_mass(N_groups)

    if (allocated(coeff_signature_active)) deallocate(coeff_signature_active)
    if (allocated(coeff_signature_diameter)) deallocate(coeff_signature_diameter)
    if (allocated(coeff_signature_groupfrac)) deallocate(coeff_signature_groupfrac)

    allocate(coeff_signature_active(N_size))
    allocate(coeff_signature_diameter(N_size))
    allocate(coeff_signature_groupfrac(N_size, N_groups))

    do i = 1, N_size
      coeff_signature_active(i) = coeff_active_cell(c_number(i), coeff_cell_total_mass(i, c_mass))
      coeff_signature_diameter(i) = cell_diam_av(i)
      coeff_signature_groupfrac(i,:) = 0.d0
      cell_mass = coeff_cell_total_mass(i, c_mass)
      call coeff_group_mass_for_cell(i, c_mass, group_mass)
      if (cell_mass > 0.d0) then
        do g = 1, N_groups
          coeff_signature_groupfrac(i,g) = group_mass(g) / cell_mass
        enddo
      endif
    enddo
  end subroutine coeff_store_signature

  integer function coeff_active_cell(cell_number, cell_mass)
    implicit none
    double precision, intent(in) :: cell_number, cell_mass
    coeff_active_cell = 0
    if (cell_number > TINYN .and. cell_mass > dble(N_species) * TINYM) coeff_active_cell = 1
  end function coeff_active_cell

  subroutine coeff_build_pair_mapping(c_number, c_mass)
    implicit none
    double precision, intent(in) :: c_number(N_size)
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    integer :: i, j, pair_index, total_pairs
    integer :: candidate_count, fallback_flag
    integer :: candidate_cells(COEFF_MAX_CANDIDATES)
    double precision :: candidate_weights(COEFF_MAX_CANDIDATES)
    double precision :: target_mass, target_diameter, target_density
    double precision :: target_groupfrac(N_groups)
    double precision :: objective_value

    total_pairs = N_size * (N_size + 1) / 2
    if (allocated(coeff_pair_src1)) deallocate(coeff_pair_src1)
    if (allocated(coeff_pair_src2)) deallocate(coeff_pair_src2)
    if (allocated(coeff_pair_candidate_count)) deallocate(coeff_pair_candidate_count)
    if (allocated(coeff_pair_candidate_cells)) deallocate(coeff_pair_candidate_cells)
    if (allocated(coeff_pair_candidate_weights)) deallocate(coeff_pair_candidate_weights)
    if (allocated(coeff_pair_target_mass)) deallocate(coeff_pair_target_mass)
    if (allocated(coeff_pair_target_diameter)) deallocate(coeff_pair_target_diameter)
    if (allocated(coeff_pair_target_density)) deallocate(coeff_pair_target_density)
    if (allocated(coeff_pair_target_groupfrac)) deallocate(coeff_pair_target_groupfrac)
    if (allocated(coeff_pair_objective_value)) deallocate(coeff_pair_objective_value)
    if (allocated(coeff_pair_fallback_flag)) deallocate(coeff_pair_fallback_flag)

    allocate(coeff_pair_src1(total_pairs))
    allocate(coeff_pair_src2(total_pairs))
    allocate(coeff_pair_candidate_count(total_pairs))
    allocate(coeff_pair_candidate_cells(COEFF_MAX_CANDIDATES, total_pairs))
    allocate(coeff_pair_candidate_weights(COEFF_MAX_CANDIDATES, total_pairs))
    allocate(coeff_pair_target_mass(total_pairs))
    allocate(coeff_pair_target_diameter(total_pairs))
    allocate(coeff_pair_target_density(total_pairs))
    allocate(coeff_pair_target_groupfrac(N_groups, total_pairs))
    allocate(coeff_pair_objective_value(total_pairs))
    allocate(coeff_pair_fallback_flag(total_pairs))

    coeff_pair_count = 0
    coeff_active_bins = 0
    coeff_active_pairs = 0
    coeff_last_mapping_calls_step = 0
    coeff_last_fallback_count_step = 0
    coeff_last_objective_mean_step = 0.d0

    do i = 1, N_size
      if (c_number(i) > TINYN .and. coeff_cell_total_mass(i, c_mass) > dble(N_species) * TINYM) then
        coeff_active_bins = coeff_active_bins + 1
      endif
    enddo

    do i = 1, N_size
      if (c_number(i) <= TINYN) cycle
      if (coeff_cell_total_mass(i, c_mass) <= dble(N_species) * TINYM) cycle
      do j = 1, i
        if (c_number(j) <= TINYN) cycle
        if (coeff_cell_total_mass(j, c_mass) <= dble(N_species) * TINYM) cycle
        coeff_active_pairs = coeff_active_pairs + 1
        call coeff_pair_target_mapping(i, j, c_number, c_mass, candidate_count, candidate_cells, candidate_weights, &
          target_mass, target_diameter, target_density, target_groupfrac, fallback_flag, objective_value)
        coeff_pair_count = coeff_pair_count + 1
        pair_index = coeff_pair_count
        coeff_pair_src1(pair_index) = i
        coeff_pair_src2(pair_index) = j
        coeff_pair_candidate_count(pair_index) = candidate_count
        coeff_pair_candidate_cells(:,pair_index) = 0
        coeff_pair_candidate_weights(:,pair_index) = 0.d0
        if (candidate_count > 0) then
          coeff_pair_candidate_cells(1:candidate_count,pair_index) = candidate_cells(1:candidate_count)
          coeff_pair_candidate_weights(1:candidate_count,pair_index) = candidate_weights(1:candidate_count)
        endif
        coeff_pair_target_mass(pair_index) = target_mass
        coeff_pair_target_diameter(pair_index) = target_diameter
        coeff_pair_target_density(pair_index) = target_density
        coeff_pair_target_groupfrac(:,pair_index) = target_groupfrac(:)
        coeff_pair_objective_value(pair_index) = objective_value
        coeff_pair_fallback_flag(pair_index) = fallback_flag
        coeff_last_fallback_count_step = coeff_last_fallback_count_step + fallback_flag
        coeff_last_objective_mean_step = coeff_last_objective_mean_step + objective_value
      enddo
    enddo

    coeff_skipped_pairs = total_pairs - coeff_active_pairs
    coeff_last_mapping_calls_step = coeff_pair_count
    coeff_total_mapping_calls = coeff_total_mapping_calls + coeff_pair_count
    coeff_mapping_build_count = coeff_mapping_build_count + 1
    if (coeff_pair_count > 0) coeff_last_objective_mean_step = coeff_last_objective_mean_step / dble(coeff_pair_count)
    coeff_total_fallback_mappings = coeff_total_fallback_mappings + coeff_last_fallback_count_step
    call coeff_store_signature(c_number, c_mass)
  end subroutine coeff_build_pair_mapping

  subroutine coeff_pair_target_mapping(src1, src2, c_number, c_mass, candidate_count, candidate_cells, candidate_weights, &
    target_mass, target_diameter, target_density, target_groupfrac, fallback_flag, objective_value)
    implicit none
    integer, intent(in) :: src1, src2
    double precision, intent(in) :: c_number(N_size)
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    integer, intent(out) :: candidate_count
    integer, intent(out) :: candidate_cells(COEFF_MAX_CANDIDATES)
    double precision, intent(out) :: candidate_weights(COEFF_MAX_CANDIDATES)
    double precision, intent(out) :: target_mass, target_diameter, target_density
    double precision, intent(out) :: target_groupfrac(N_groups)
    integer, intent(out) :: fallback_flag
    double precision, intent(out) :: objective_value

    candidate_count = 0
    candidate_cells = 0
    candidate_weights = 0.d0
    target_groupfrac = 0.d0
    fallback_flag = 0
    objective_value = 0.d0

    call coeff_compute_product_state(src1, src2, c_number, c_mass, target_mass, target_diameter, target_density, target_groupfrac)
    if (.not. coeff_target_state_is_valid(target_mass, target_diameter, target_density, target_groupfrac)) then
      candidate_count = 1
      candidate_cells(1) = coeff_source_fallback_cell(src1, src2, c_mass)
      candidate_weights(1) = 1.d0
      fallback_flag = 1
      objective_value = 0.d0
      return
    endif

    select case (coeff_repartition_mode)
    case (COEFF_REPARTITION_DETERMINISTIC_NEAREST)
      candidate_count = 1
      candidate_cells(1) = coeff_find_nearest_cell(target_diameter, target_groupfrac)
      candidate_weights(1) = 1.d0
    case (COEFF_REPARTITION_WEIGHTED_CURRENT)
      call coeff_map_weighted_current(target_diameter, target_groupfrac, candidate_count, candidate_cells, candidate_weights, fallback_flag)
    case (COEFF_REPARTITION_WEIGHTED_SOFT)
      call coeff_map_weighted_soft(target_diameter, target_groupfrac, candidate_count, candidate_cells, candidate_weights, fallback_flag)
    case (COEFF_REPARTITION_LCP)
      call coeff_map_lcp(target_diameter, target_groupfrac, candidate_count, candidate_cells, candidate_weights, fallback_flag, objective_value)
    case default
      candidate_count = 1
      candidate_cells(1) = coeff_find_nearest_cell(target_diameter, target_groupfrac)
      candidate_weights(1) = 1.d0
    end select

    if (candidate_count <= 0) then
      candidate_count = 1
      candidate_cells(1) = coeff_find_nearest_cell(target_diameter, target_groupfrac)
      candidate_weights(1) = 1.d0
      fallback_flag = 1
    endif

    call coeff_normalize_weights(candidate_count, candidate_weights)
    if (candidate_count > 1 .and. .not. coeff_projection_is_valid(target_diameter, target_groupfrac, candidate_count, candidate_cells, candidate_weights)) then
      candidate_count = 1
      candidate_cells(1) = coeff_find_nearest_cell(target_diameter, target_groupfrac)
      candidate_weights = 0.d0
      candidate_weights(1) = 1.d0
      fallback_flag = 1
    endif
    objective_value = coeff_mapping_objective(target_diameter, target_groupfrac, candidate_count, candidate_cells, candidate_weights)
  end subroutine coeff_pair_target_mapping

  subroutine coeff_compute_product_state(src1, src2, c_number, c_mass, total_mass, diameter, effective_density, group_frac)
    implicit none
    integer, intent(in) :: src1, src2
    double precision, intent(in) :: c_number(N_size)
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    double precision, intent(out) :: total_mass, diameter, effective_density
    double precision, intent(out) :: group_frac(N_groups)
    integer :: s, jesp
    double precision :: per_particle_mass(N_aerosol), total_volume, group_mass(N_groups)

    per_particle_mass = 0.d0
    group_mass = 0.d0
    total_mass = 0.d0
    total_volume = 0.d0

    do s = 1, N_species
      jesp = List_species(s)
      per_particle_mass(jesp) = c_mass(src1,jesp) / max(c_number(src1), TINYN) &
        + c_mass(src2,jesp) / max(c_number(src2), TINYN)
      total_mass = total_mass + per_particle_mass(jesp)
      total_volume = total_volume + per_particle_mass(jesp) / max(mass_density_aer(jesp), fixed_density)
      group_mass(Index_groups(s)) = group_mass(Index_groups(s)) + per_particle_mass(jesp)
    enddo

    if (total_volume > 0.d0) then
      diameter = (6.d0 * total_volume / pi) ** (1.d0 / 3.d0)
      effective_density = total_mass / total_volume
    else
      diameter = max(cell_diam_av(src1), cell_diam_av(src2))
      effective_density = fixed_density
    endif

    group_frac = 0.d0
    if (total_mass > 0.d0) group_frac = group_mass / total_mass
  end subroutine coeff_compute_product_state

  logical function coeff_target_state_is_valid(total_mass, diameter, effective_density, group_frac)
    implicit none
    double precision, intent(in) :: total_mass, diameter, effective_density
    double precision, intent(in) :: group_frac(N_groups)
    double precision :: sum_group

    coeff_target_state_is_valid = .false.
    if (.not. coeff_scalar_is_finite(total_mass)) return
    if (.not. coeff_scalar_is_finite(diameter)) return
    if (.not. coeff_scalar_is_finite(effective_density)) return
    if (total_mass <= TINYM) return
    if (diameter <= diam_bound(1) * 1.d-6) return
    if (effective_density <= TINYM) return
    if (any(group_frac /= group_frac)) return
    if (any(group_frac < -1.d-8)) return
    if (any(group_frac > 1.d0 + 1.d-8)) return
    sum_group = sum(group_frac)
    if (.not. coeff_scalar_is_finite(sum_group)) return
    if (abs(sum_group - 1.d0) > 1.d-4) return
    coeff_target_state_is_valid = .true.
  end function coeff_target_state_is_valid

  integer function coeff_source_fallback_cell(src1, src2, c_mass)
    implicit none
    integer, intent(in) :: src1, src2
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    double precision :: mass1, mass2

    mass1 = coeff_cell_total_mass(src1, c_mass)
    mass2 = coeff_cell_total_mass(src2, c_mass)
    if (mass2 > mass1) then
      coeff_source_fallback_cell = src2
    else
      coeff_source_fallback_cell = src1
    endif
  end function coeff_source_fallback_cell

  logical function coeff_projection_is_valid(diameter, group_frac, candidate_count, candidate_cells, candidate_weights)
    implicit none
    double precision, intent(in) :: diameter
    double precision, intent(in) :: group_frac(N_groups)
    integer, intent(in) :: candidate_count
    integer, intent(in) :: candidate_cells(COEFF_MAX_CANDIDATES)
    double precision, intent(in) :: candidate_weights(COEFF_MAX_CANDIDATES)
    integer :: idx, used_count, size_a, size_b
    logical :: has_low, has_high

    coeff_projection_is_valid = .false.
    if (candidate_count <= 0) return
    if (any(candidate_weights(1:candidate_count) < -COEFF_COMP_EPS)) return
    if (.not. coeff_scalar_is_finite(sum(candidate_weights(1:candidate_count)))) return

    used_count = 0
    has_low = .false.
    has_high = .false.
    size_a = 0
    size_b = 0
    do idx = 1, candidate_count
      if (candidate_weights(idx) <= 1.d-8) cycle
      used_count = used_count + 1
      if (coeff_comp_distance_to_cell(candidate_cells(idx), group_frac) > 0.20d0) return
      if (size_a == 0) then
        size_a = concentration_index(candidate_cells(idx),1)
      elseif (concentration_index(candidate_cells(idx),1) /= size_a .and. size_b == 0) then
        size_b = concentration_index(candidate_cells(idx),1)
      elseif (concentration_index(candidate_cells(idx),1) /= size_a .and. concentration_index(candidate_cells(idx),1) /= size_b) then
        return
      endif
    enddo
    if (used_count <= 1) then
      coeff_projection_is_valid = .true.
      return
    endif
    if (size_b /= 0 .and. abs(size_b - size_a) > 1) return
    coeff_projection_is_valid = coeff_mapping_objective(diameter, group_frac, candidate_count, candidate_cells, candidate_weights) <= 0.5d0
  end function coeff_projection_is_valid

  logical function coeff_scalar_is_finite(value)
    implicit none
    double precision, intent(in) :: value

    coeff_scalar_is_finite = (value == value) .and. (abs(value) < huge(1.d0) * 1.d-2)
  end function coeff_scalar_is_finite

  subroutine coeff_map_weighted_current(diameter, group_frac, candidate_count, candidate_cells, candidate_weights, fallback_flag)
    implicit none
    double precision, intent(in) :: diameter
    double precision, intent(in) :: group_frac(N_groups)
    integer, intent(out) :: candidate_count
    integer, intent(out) :: candidate_cells(COEFF_MAX_CANDIDATES)
    double precision, intent(out) :: candidate_weights(COEFF_MAX_CANDIDATES)
    integer, intent(out) :: fallback_flag
    integer :: k_low, k_high
    double precision :: log_d, log_low, log_high, size_weight_high, size_weight_low

    candidate_count = 0
    candidate_cells = 0
    candidate_weights = 0.d0
    fallback_flag = 0

    call coeff_find_bracketing_size_bins(diameter, k_low, k_high)
    candidate_cells(1) = coeff_find_nearest_comp_cell(k_low, group_frac)
    candidate_count = 1

    if (k_high == k_low) then
      candidate_weights(1) = 1.d0
      fallback_flag = 1
      return
    endif

    candidate_cells(2) = coeff_find_nearest_comp_cell(k_high, group_frac)
    if (candidate_cells(2) == candidate_cells(1)) then
      candidate_weights(1) = 1.d0
      fallback_flag = 1
      return
    endif

    candidate_count = 2
    log_d = log10(max(diameter, diam_bound(1)))
    log_low = log10(max(size_diam_av(k_low), diam_bound(1)))
    log_high = log10(max(size_diam_av(k_high), diam_bound(1)))
    if (abs(log_high - log_low) <= COEFF_COMP_EPS) then
      candidate_weights(1) = 1.d0
      candidate_count = 1
      fallback_flag = 1
      return
    endif

    size_weight_high = (log_d - log_low) / (log_high - log_low)
    size_weight_high = min(1.d0, max(0.d0, size_weight_high))
    size_weight_low = 1.d0 - size_weight_high

    if (min(size_weight_low, size_weight_high) < COEFF_WEIGHTED_MIN_SPLIT) then
      if (size_weight_high > size_weight_low) then
        candidate_cells(1) = candidate_cells(2)
      endif
      candidate_weights(1) = 1.d0
      candidate_count = 1
      fallback_flag = 1
      return
    endif

    candidate_weights(1) = size_weight_low
    candidate_weights(2) = size_weight_high
  end subroutine coeff_map_weighted_current

  subroutine coeff_map_weighted_soft(diameter, group_frac, candidate_count, candidate_cells, candidate_weights, fallback_flag)
    implicit none
    double precision, intent(in) :: diameter
    double precision, intent(in) :: group_frac(N_groups)
    integer, intent(out) :: candidate_count
    integer, intent(out) :: candidate_cells(COEFF_MAX_CANDIDATES)
    double precision, intent(out) :: candidate_weights(COEFF_MAX_CANDIDATES)
    integer, intent(out) :: fallback_flag
    integer :: candidate_size_bins(COEFF_MAX_CANDIDATES)
    integer :: idx, k_low, k_high, current_size, start_pos, end_pos
    double precision :: size_weight_low, size_weight_high
    double precision :: comp_scores(COEFF_MAX_CANDIDATES), soft_sum

    candidate_cells = 0
    candidate_weights = 0.d0
    candidate_size_bins = 0
    fallback_flag = 0

    call coeff_build_candidate_set(diameter, group_frac, candidate_count, candidate_cells)
    if (candidate_count <= 0) then
      fallback_flag = 1
      candidate_count = 1
      candidate_cells(1) = coeff_find_nearest_cell(diameter, group_frac)
      candidate_weights(1) = 1.d0
      return
    endif

    call coeff_find_bracketing_size_bins(diameter, k_low, k_high)
    call coeff_size_barycentric_weights(diameter, k_low, k_high, size_weight_low, size_weight_high)
    do idx = 1, candidate_count
      candidate_size_bins(idx) = concentration_index(candidate_cells(idx),1)
    enddo

    do current_size = 1, 2
      if (current_size == 1) then
        start_pos = 1
        end_pos = candidate_count
        soft_sum = 0.d0
        do idx = 1, candidate_count
          if (candidate_size_bins(idx) /= k_low) cycle
          comp_scores(idx) = exp(-coeff_comp_distance_to_cell(candidate_cells(idx), group_frac) / COEFF_SOFT_TAU)
          soft_sum = soft_sum + comp_scores(idx)
        enddo
        if (soft_sum > 0.d0) then
          do idx = 1, candidate_count
            if (candidate_size_bins(idx) /= k_low) cycle
            candidate_weights(idx) = size_weight_low * comp_scores(idx) / soft_sum
          enddo
        endif
      else
        if (k_high == k_low) cycle
        soft_sum = 0.d0
        do idx = 1, candidate_count
          if (candidate_size_bins(idx) /= k_high) cycle
          comp_scores(idx) = exp(-coeff_comp_distance_to_cell(candidate_cells(idx), group_frac) / COEFF_SOFT_TAU)
          soft_sum = soft_sum + comp_scores(idx)
        enddo
        if (soft_sum > 0.d0) then
          do idx = 1, candidate_count
            if (candidate_size_bins(idx) /= k_high) cycle
            candidate_weights(idx) = candidate_weights(idx) + size_weight_high * comp_scores(idx) / soft_sum
          enddo
        endif
      endif
    enddo

    call coeff_normalize_weights(candidate_count, candidate_weights)
  end subroutine coeff_map_weighted_soft

  subroutine coeff_map_lcp(diameter, group_frac, candidate_count, candidate_cells, candidate_weights, fallback_flag, objective_value)
    implicit none
    double precision, intent(in) :: diameter
    double precision, intent(in) :: group_frac(N_groups)
    integer, intent(out) :: candidate_count
    integer, intent(out) :: candidate_cells(COEFF_MAX_CANDIDATES)
    double precision, intent(out) :: candidate_weights(COEFF_MAX_CANDIDATES)
    integer, intent(out) :: fallback_flag
    double precision, intent(out) :: objective_value
    logical :: solved

    candidate_cells = 0
    candidate_weights = 0.d0
    fallback_flag = 0
    objective_value = 0.d0

    call coeff_build_candidate_set(diameter, group_frac, candidate_count, candidate_cells)
    if (candidate_count <= 0) then
      fallback_flag = 1
      candidate_count = 1
      candidate_cells(1) = coeff_find_nearest_cell(diameter, group_frac)
      candidate_weights(1) = 1.d0
      objective_value = 0.d0
      return
    endif

    if (candidate_count == 1) then
      candidate_weights(1) = 1.d0
      objective_value = 0.d0
      return
    endif

    call coeff_solve_lcp_simplex(diameter, group_frac, candidate_count, candidate_cells, candidate_weights, solved, objective_value)
    if (.not. solved) then
      fallback_flag = 1
      candidate_count = 1
      candidate_cells(1) = coeff_find_nearest_cell(diameter, group_frac)
      candidate_weights = 0.d0
      candidate_weights(1) = 1.d0
      objective_value = 0.d0
    endif
  end subroutine coeff_map_lcp

  subroutine coeff_build_candidate_set(diameter, group_frac, candidate_count, candidate_cells)
    implicit none
    double precision, intent(in) :: diameter
    double precision, intent(in) :: group_frac(N_groups)
    integer, intent(out) :: candidate_count
    integer, intent(out) :: candidate_cells(COEFF_MAX_CANDIDATES)
    integer :: k_low, k_high
    integer :: local_cells(COEFF_MAX_COMP_CANDIDATES_PER_SIZE), n_local, idx

    candidate_count = 0
    candidate_cells = 0

    call coeff_find_bracketing_size_bins(diameter, k_low, k_high)
    call coeff_collect_best_comp_cells(k_low, group_frac, n_local, local_cells)
    do idx = 1, n_local
      candidate_count = candidate_count + 1
      candidate_cells(candidate_count) = local_cells(idx)
    enddo

    if (k_high /= k_low) then
      call coeff_collect_best_comp_cells(k_high, group_frac, n_local, local_cells)
      do idx = 1, n_local
        if (any(candidate_cells(1:candidate_count) == local_cells(idx))) cycle
        candidate_count = candidate_count + 1
        candidate_cells(candidate_count) = local_cells(idx)
      enddo
    endif
  end subroutine coeff_build_candidate_set

  subroutine coeff_collect_best_comp_cells(size_bin, group_frac, count_out, cells_out)
    implicit none
    integer, intent(in) :: size_bin
    double precision, intent(in) :: group_frac(N_groups)
    integer, intent(out) :: count_out
    integer, intent(out) :: cells_out(COEFF_MAX_COMP_CANDIDATES_PER_SIZE)
    integer :: f, idx, pos
    double precision :: score
    double precision :: best_scores(COEFF_MAX_COMP_CANDIDATES_PER_SIZE)

    cells_out = 0
    best_scores = huge(1.d0)

    do f = 1, N_fracmax
      idx = concentration_index_iv(size_bin,f)
      score = coeff_comp_distance_to_cell(idx, group_frac)
      do pos = 1, COEFF_MAX_COMP_CANDIDATES_PER_SIZE
        if (score < best_scores(pos)) then
          if (pos < COEFF_MAX_COMP_CANDIDATES_PER_SIZE) then
            best_scores(pos+1:COEFF_MAX_COMP_CANDIDATES_PER_SIZE) = best_scores(pos:COEFF_MAX_COMP_CANDIDATES_PER_SIZE-1)
            cells_out(pos+1:COEFF_MAX_COMP_CANDIDATES_PER_SIZE) = cells_out(pos:COEFF_MAX_COMP_CANDIDATES_PER_SIZE-1)
          endif
          best_scores(pos) = score
          cells_out(pos) = idx
          exit
        endif
      enddo
    enddo

    count_out = 0
    do pos = 1, COEFF_MAX_COMP_CANDIDATES_PER_SIZE
      if (cells_out(pos) > 0) count_out = count_out + 1
    enddo
  end subroutine coeff_collect_best_comp_cells

  subroutine coeff_size_barycentric_weights(diameter, k_low, k_high, weight_low, weight_high)
    implicit none
    double precision, intent(in) :: diameter
    integer, intent(in) :: k_low, k_high
    double precision, intent(out) :: weight_low, weight_high
    double precision :: log_d, log_low, log_high

    if (k_low == k_high) then
      weight_low = 1.d0
      weight_high = 0.d0
      return
    endif

    log_d = log10(max(diameter, diam_bound(1)))
    log_low = log10(max(size_diam_av(k_low), diam_bound(1)))
    log_high = log10(max(size_diam_av(k_high), diam_bound(1)))
    if (abs(log_high - log_low) <= COEFF_COMP_EPS) then
      weight_low = 1.d0
      weight_high = 0.d0
      return
    endif

    weight_high = (log_d - log_low) / (log_high - log_low)
    weight_high = min(1.d0, max(0.d0, weight_high))
    weight_low = 1.d0 - weight_high
  end subroutine coeff_size_barycentric_weights

  subroutine coeff_normalize_weights(candidate_count, candidate_weights)
    implicit none
    integer, intent(in) :: candidate_count
    double precision, intent(inout) :: candidate_weights(COEFF_MAX_CANDIDATES)
    double precision :: total_weight

    if (candidate_count <= 0) return
    candidate_weights(1:candidate_count) = max(candidate_weights(1:candidate_count), 0.d0)
    total_weight = sum(candidate_weights(1:candidate_count))
    if (total_weight <= COEFF_COMP_EPS) then
      candidate_weights = 0.d0
      candidate_weights(1) = 1.d0
      return
    endif
    candidate_weights(1:candidate_count) = candidate_weights(1:candidate_count) / total_weight
  end subroutine coeff_normalize_weights

  double precision function coeff_comp_distance_to_cell(cell_index, group_frac)
    implicit none
    integer, intent(in) :: cell_index
    double precision, intent(in) :: group_frac(N_groups)
    integer :: g

    coeff_comp_distance_to_cell = 0.d0
    do g = 1, N_groups
      coeff_comp_distance_to_cell = coeff_comp_distance_to_cell + &
        (group_frac(g) - coeff_cell_group_center(cell_index, g)) ** 2
    enddo
    coeff_comp_distance_to_cell = sqrt(max(coeff_comp_distance_to_cell, 0.d0))
  end function coeff_comp_distance_to_cell

  double precision function coeff_cell_group_center(cell_index, group_index)
    implicit none
    integer, intent(in) :: cell_index, group_index
    integer :: k, f

    k = concentration_index(cell_index,1)
    f = concentration_index(cell_index,2)
    coeff_cell_group_center = 0.5d0 * (discretization_composition(k,f,group_index,1) + discretization_composition(k,f,group_index,2))
  end function coeff_cell_group_center

  double precision function coeff_mapping_objective(diameter, group_frac, candidate_count, candidate_cells, candidate_weights)
    implicit none
    double precision, intent(in) :: diameter
    double precision, intent(in) :: group_frac(N_groups)
    integer, intent(in) :: candidate_count
    integer, intent(in) :: candidate_cells(COEFF_MAX_CANDIDATES)
    double precision, intent(in) :: candidate_weights(COEFF_MAX_CANDIDATES)
    integer :: idx, g, size_bin
    double precision :: log_target, log_mix, frac_mix(N_groups)

    log_target = log10(max(diameter, diam_bound(1)))
    log_mix = 0.d0
    frac_mix = 0.d0
    do idx = 1, candidate_count
      size_bin = concentration_index(candidate_cells(idx),1)
      log_mix = log_mix + candidate_weights(idx) * log10(max(size_diam_av(size_bin), diam_bound(1)))
      do g = 1, N_groups
        frac_mix(g) = frac_mix(g) + candidate_weights(idx) * coeff_cell_group_center(candidate_cells(idx), g)
      enddo
    enddo

    coeff_mapping_objective = COEFF_LCP_LAMBDA_D * (log_mix - log_target) ** 2
    do g = 1, N_groups
      coeff_mapping_objective = coeff_mapping_objective + COEFF_LCP_LAMBDA_F * (frac_mix(g) - group_frac(g)) ** 2
    enddo
  end function coeff_mapping_objective

  subroutine coeff_solve_lcp_simplex(diameter, group_frac, candidate_count, candidate_cells, candidate_weights, solved, best_objective)
    implicit none
    double precision, intent(in) :: diameter
    double precision, intent(in) :: group_frac(N_groups)
    integer, intent(in) :: candidate_count
    integer, intent(in) :: candidate_cells(COEFF_MAX_CANDIDATES)
    double precision, intent(out) :: candidate_weights(COEFF_MAX_CANDIDATES)
    logical, intent(out) :: solved
    double precision, intent(out) :: best_objective
    integer :: mask, idx, active_count, active_indices(COEFF_MAX_CANDIDATES), g, size_bin
    double precision :: target_features(1 + N_groups)
    double precision :: feature_matrix(1 + N_groups, COEFF_MAX_CANDIDATES)
    double precision :: full_weights(COEFF_MAX_CANDIDATES), trial_weights(COEFF_MAX_CANDIDATES)
    double precision :: system_matrix(COEFF_MAX_CANDIDATES + 1, COEFF_MAX_CANDIDATES + 1)
    double precision :: rhs(COEFF_MAX_CANDIDATES + 1), solution(COEFF_MAX_CANDIDATES + 1)
    double precision :: objective_value
    logical :: ok

    solved = .false.
    candidate_weights = 0.d0
    best_objective = huge(1.d0)

    target_features(1) = sqrt(COEFF_LCP_LAMBDA_D) * log10(max(diameter, diam_bound(1)))
    do g = 1, N_groups
      target_features(1 + g) = sqrt(COEFF_LCP_LAMBDA_F) * group_frac(g)
    enddo

    do idx = 1, candidate_count
      size_bin = concentration_index(candidate_cells(idx),1)
      feature_matrix(1,idx) = sqrt(COEFF_LCP_LAMBDA_D) * log10(max(size_diam_av(size_bin), diam_bound(1)))
      do g = 1, N_groups
        feature_matrix(1 + g, idx) = sqrt(COEFF_LCP_LAMBDA_F) * coeff_cell_group_center(candidate_cells(idx), g)
      enddo
    enddo

    do mask = 1, 2 ** candidate_count - 1
      active_count = 0
      do idx = 1, candidate_count
        if (btest(mask, idx - 1)) then
          active_count = active_count + 1
          active_indices(active_count) = idx
        endif
      enddo

      system_matrix = 0.d0
      rhs = 0.d0
      do idx = 1, active_count
        do g = 1, active_count
          system_matrix(idx,g) = sum(feature_matrix(:,active_indices(idx)) * feature_matrix(:,active_indices(g)))
        enddo
        system_matrix(idx,active_count + 1) = 1.d0
        system_matrix(active_count + 1,idx) = 1.d0
        rhs(idx) = sum(feature_matrix(:,active_indices(idx)) * target_features(:))
      enddo
      rhs(active_count + 1) = 1.d0

      ok = coeff_solve_linear_system(active_count + 1, system_matrix, rhs, solution)
      if (.not. ok) cycle
      if (minval(solution(1:active_count)) < -1.d-10) cycle

      trial_weights = 0.d0
      do idx = 1, active_count
        trial_weights(active_indices(idx)) = max(solution(idx), 0.d0)
      enddo
      call coeff_normalize_weights(candidate_count, trial_weights)
      objective_value = coeff_mapping_objective(diameter, group_frac, candidate_count, candidate_cells, trial_weights)
      if (objective_value < best_objective) then
        best_objective = objective_value
        candidate_weights = trial_weights
        solved = .true.
      endif
    enddo
  end subroutine coeff_solve_lcp_simplex

  logical function coeff_solve_linear_system(system_size, system_matrix, rhs, solution)
    implicit none
    integer, intent(in) :: system_size
    double precision, intent(in) :: system_matrix(COEFF_MAX_CANDIDATES + 1, COEFF_MAX_CANDIDATES + 1)
    double precision, intent(in) :: rhs(COEFF_MAX_CANDIDATES + 1)
    double precision, intent(out) :: solution(COEFF_MAX_CANDIDATES + 1)
    double precision :: a(COEFF_MAX_CANDIDATES + 1, COEFF_MAX_CANDIDATES + 1)
    double precision :: b(COEFF_MAX_CANDIDATES + 1)
    double precision :: factor, pivot_abs, tmp
    integer :: i, j, k, pivot_row

    a = 0.d0
    b = 0.d0
    solution = 0.d0
    a(1:system_size,1:system_size) = system_matrix(1:system_size,1:system_size)
    b(1:system_size) = rhs(1:system_size)

    coeff_solve_linear_system = .true.
    do k = 1, system_size
      pivot_row = k
      pivot_abs = abs(a(k,k))
      do i = k + 1, system_size
        if (abs(a(i,k)) > pivot_abs) then
          pivot_abs = abs(a(i,k))
          pivot_row = i
        endif
      enddo
      if (pivot_abs <= COEFF_COMP_EPS) then
        coeff_solve_linear_system = .false.
        return
      endif
      if (pivot_row /= k) then
        do j = k, system_size
          tmp = a(k,j)
          a(k,j) = a(pivot_row,j)
          a(pivot_row,j) = tmp
        enddo
        tmp = b(k)
        b(k) = b(pivot_row)
        b(pivot_row) = tmp
      endif
      do i = k + 1, system_size
        factor = a(i,k) / a(k,k)
        do j = k, system_size
          a(i,j) = a(i,j) - factor * a(k,j)
        enddo
        b(i) = b(i) - factor * b(k)
      enddo
    enddo

    do i = system_size, 1, -1
      solution(i) = b(i)
      do j = i + 1, system_size
        solution(i) = solution(i) - a(i,j) * solution(j)
      enddo
      solution(i) = solution(i) / a(i,i)
    enddo
  end function coeff_solve_linear_system

  subroutine coeff_find_bracketing_size_bins(diameter, k_low, k_high)
    implicit none
    double precision, intent(in) :: diameter
    integer, intent(out) :: k_low, k_high
    integer :: k

    if (diameter <= size_diam_av(1)) then
      k_low = 1
      k_high = 1
      return
    endif
    if (diameter >= size_diam_av(N_sizebin)) then
      k_low = N_sizebin
      k_high = N_sizebin
      return
    endif

    do k = 1, N_sizebin - 1
      if (diameter >= size_diam_av(k) .and. diameter < size_diam_av(k+1)) then
        k_low = k
        k_high = k + 1
        return
      endif
    enddo

    k_low = N_sizebin
    k_high = N_sizebin
  end subroutine coeff_find_bracketing_size_bins

  integer function coeff_find_nearest_cell(diameter, group_frac)
    implicit none
    double precision, intent(in) :: diameter
    double precision, intent(in) :: group_frac(N_groups)
    integer :: idx, k, f, g
    double precision :: score, best_score, group_score, d_score

    coeff_find_nearest_cell = 1
    best_score = huge(1.d0)
    do idx = 1, N_size
      k = concentration_index(idx,1)
      f = concentration_index(idx,2)
      d_score = abs(log10(max(diameter, diam_bound(1))) - log10(max(size_diam_av(k), diam_bound(1))))
      group_score = 0.d0
      do g = 1, N_groups
        group_score = group_score + coeff_interval_distance(group_frac(g), discretization_composition(k,f,g,1), discretization_composition(k,f,g,2))
      enddo
      score = 4.d0 * d_score + group_score
      if (score < best_score) then
        best_score = score
        coeff_find_nearest_cell = idx
      endif
    enddo
  end function coeff_find_nearest_cell

  integer function coeff_find_nearest_comp_cell(size_bin, group_frac)
    implicit none
    integer, intent(in) :: size_bin
    double precision, intent(in) :: group_frac(N_groups)
    integer :: f, g, idx
    double precision :: score, best_score

    coeff_find_nearest_comp_cell = concentration_index_iv(size_bin,1)
    best_score = huge(1.d0)
    do f = 1, N_fracmax
      idx = concentration_index_iv(size_bin,f)
      score = 0.d0
      do g = 1, N_groups
        score = score + coeff_interval_distance(group_frac(g), discretization_composition(size_bin,f,g,1), discretization_composition(size_bin,f,g,2))
      enddo
      if (score < best_score) then
        best_score = score
        coeff_find_nearest_comp_cell = idx
      endif
    enddo
  end function coeff_find_nearest_comp_cell

  double precision function coeff_interval_distance(value, lower_bound, upper_bound)
    implicit none
    double precision, intent(in) :: value, lower_bound, upper_bound

    if (value < lower_bound) then
      coeff_interval_distance = lower_bound - value
    elseif (value > upper_bound) then
      coeff_interval_distance = value - upper_bound
    else
      coeff_interval_distance = 0.d0
    endif
  end function coeff_interval_distance

  double precision function coeff_cell_total_mass(cell_index, c_mass)
    implicit none
    integer, intent(in) :: cell_index
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    integer :: s, jesp

    coeff_cell_total_mass = 0.d0
    do s = 1, N_species
      jesp = List_species(s)
      coeff_cell_total_mass = coeff_cell_total_mass + c_mass(cell_index,jesp)
    enddo
  end function coeff_cell_total_mass

  subroutine coeff_group_mass_for_cell(cell_index, c_mass, group_mass)
    implicit none
    integer, intent(in) :: cell_index
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    double precision, intent(out) :: group_mass(N_groups)
    integer :: s, jesp

    group_mass = 0.d0
    do s = 1, N_species
      jesp = List_species(s)
      group_mass(Index_groups(s)) = group_mass(Index_groups(s)) + c_mass(cell_index,jesp)
    enddo
  end subroutine coeff_group_mass_for_cell

  subroutine coeff_reset_deltas()
    implicit none
    if (.not. allocated(coeff_last_delta_number)) call coeff_allocate_delta_arrays()
    coeff_last_delta_number = 0.d0
    coeff_last_delta_mass = 0.d0
  end subroutine coeff_reset_deltas

  subroutine coeff_record_timestep(time_seconds)
    implicit none
    double precision, intent(in) :: time_seconds
    integer :: k, f, idx, s, jesp
    double precision :: total_mass_sum, size_number, size_mass, diversity, comp_mass
    double precision :: size_comp_mass(N_sizebin, N_fracmax)
    double precision :: size_comp_number(N_sizebin, N_fracmax)
    character(len=512) :: file_name
    character(len=64) :: cache_status
    character(len=32) :: species_name

    if (.not. coeff_csv_initialized) return

    call coeff_count_active_state(concentration_number, concentration_mass)
    cache_status = coeff_cache_status_string()

    total_mass_sum = 0.d0
    do s = 1, N_species
      jesp = List_species(s)
      total_mass_sum = total_mass_sum + total_aero_mass(jesp)
    enddo
    coeff_last_step_total_mass_after = total_mass_sum
    coeff_last_step_total_number_after = total_number
    coeff_last_step_time_seconds = time_seconds
    call coeff_scan_minima_and_flags()

    file_name = trim(coeff_results_dir) // '/csv/timestep_summary.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",ES24.16,",",ES24.16,",",I0,",",I0,",",I0,",",A,",",A,",",ES24.16,",",A,",",A,",",A)') &
      coeff_step_index, time_seconds, total_mass_sum, total_number, coeff_active_bins, coeff_active_pairs, coeff_skipped_pairs, &
      trim(coeff_repartition_mode_name), trim(cache_status), coeff_last_step_runtime, trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/species_mass_timeseries.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    do s = 1, N_species
      jesp = List_species(s)
      species_name = coeff_species_name(jesp)
      write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",I0,",",A,",",ES24.16,",",A,",",A,",",A)') &
        coeff_step_index, time_seconds, jesp, trim(species_name), total_aero_mass(jesp), trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
    enddo
    close(COEFF_IO_UNIT)

    size_comp_mass = 0.d0
    size_comp_number = 0.d0
    do k = 1, N_sizebin
      do f = 1, N_fracmax
        idx = concentration_index_iv(k,f)
        size_comp_number(k,f) = concentration_number(idx)
        size_comp_mass(k,f) = coeff_cell_total_mass(idx, concentration_mass)
      enddo
    enddo

    file_name = trim(coeff_results_dir) // '/csv/size_distribution_number.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    do k = 1, N_sizebin
      size_number = sum(size_comp_number(k,:))
      write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",I0,",",ES24.16,",",ES24.16,",",ES24.16,",",A,",",A,",",A)') &
        coeff_step_index, time_seconds, k, size_diam_av(k), size_number, size_number / max(size_sect(k), COEFF_COMP_EPS), &
        trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
    enddo
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/size_distribution_mass.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    do k = 1, N_sizebin
      size_mass = sum(size_comp_mass(k,:))
      write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",I0,",",ES24.16,",",ES24.16,",",ES24.16,",",A,",",A,",",A)') &
        coeff_step_index, time_seconds, k, size_diam_av(k), size_mass, size_mass / max(size_sect(k), COEFF_COMP_EPS), &
        trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
    enddo
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/size_composition_mass.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    do k = 1, N_sizebin
      do f = 1, N_fracmax
        write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",I0,",",I0,",",ES24.16,",",A,",",A,",",A)') &
          coeff_step_index, time_seconds, k, f, size_comp_mass(k,f), trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
      enddo
    enddo
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/size_composition_number.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    do k = 1, N_sizebin
      do f = 1, N_fracmax
        write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",I0,",",I0,",",ES24.16,",",A,",",A,",",A)') &
          coeff_step_index, time_seconds, k, f, size_comp_number(k,f), trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
      enddo
    enddo
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/composition_diversity.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    do k = 1, N_sizebin
      diversity = coeff_composition_diversity(size_comp_mass(k,:))
      write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",I0,",",ES24.16,",",A,",",A,",",A)') &
        coeff_step_index, time_seconds, k, diversity, trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
    enddo
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/coag_delta_number.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    do idx = 1, N_size
      k = concentration_index(idx,1)
      f = concentration_index(idx,2)
      write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",I0,",",I0,",",I0,",",ES24.16,",",A,",",A,",",A)') &
        coeff_step_index, time_seconds, idx, k, f, coeff_last_delta_number(idx), trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
    enddo
    close(COEFF_IO_UNIT)

    file_name = trim(coeff_results_dir) // '/csv/coag_delta_mass.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    do idx = 1, N_size
      k = concentration_index(idx,1)
      f = concentration_index(idx,2)
      do s = 1, N_species
        jesp = List_species(s)
        species_name = coeff_species_name(jesp)
        write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",I0,",",I0,",",I0,",",I0,",",A,",",ES24.16,",",A,",",A,",",A)') &
          coeff_step_index, time_seconds, idx, k, f, jesp, trim(species_name), coeff_last_delta_mass(idx,jesp), &
          trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
      enddo
    enddo
    close(COEFF_IO_UNIT)

    call coeff_append_mapping_events(time_seconds)
    call coeff_append_conservation_audit(time_seconds)
    call coeff_append_anomalies(time_seconds, size_comp_mass)

    coeff_previous_total_number = total_number
    coeff_step_audit_initialized = .false.
    coeff_step_index = coeff_step_index + 1
  end subroutine coeff_record_timestep

  subroutine coeff_scan_minima_and_flags()
    implicit none
    integer :: s, jesp

    coeff_last_min_mass = minval(concentration_mass)
    coeff_last_min_number = minval(concentration_number)
    coeff_last_min_gas = 0.d0
    if (N_aerosol > 0) coeff_last_min_gas = minval(concentration_gas)
  end subroutine coeff_scan_minima_and_flags

  subroutine coeff_append_mapping_events(time_seconds)
    implicit none
    double precision, intent(in) :: time_seconds
    integer :: p, c
    integer :: src_size1, src_size2
    character(len=512) :: file_name
    character(len=512) :: group_text, candidate_text, weight_text

    file_name = trim(coeff_results_dir) // '/csv/mapping_events.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    do p = 1, coeff_pair_count
      src_size1 = concentration_index(coeff_pair_src1(p),1)
      src_size2 = concentration_index(coeff_pair_src2(p),1)
      call coeff_format_group_fractions(coeff_pair_target_groupfrac(:,p), group_text)
      call coeff_format_int_vector(coeff_pair_candidate_count(p), coeff_pair_candidate_cells(:,p), candidate_text)
      call coeff_format_real_vector(coeff_pair_candidate_count(p), coeff_pair_candidate_weights(:,p), weight_text)
      write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",I0,",",I0,",",I0,",",I0,",",ES24.16,",",ES24.16,",",ES24.16,",",A,",",A,",",A,",",A,",",I0,",",ES24.16)') &
        coeff_step_index, time_seconds, coeff_pair_src1(p), coeff_pair_src2(p), src_size1, src_size2, coeff_pair_target_mass(p), &
        coeff_pair_target_diameter(p), coeff_pair_target_density(p), trim(group_text), trim(candidate_text), trim(weight_text), &
        trim(coeff_repartition_mode_name), coeff_pair_fallback_flag(p), coeff_pair_objective_value(p)
    enddo
    close(COEFF_IO_UNIT)
  end subroutine coeff_append_mapping_events

  subroutine coeff_append_conservation_audit(time_seconds)
    implicit none
    double precision, intent(in) :: time_seconds
    character(len=512) :: file_name

    file_name = trim(coeff_results_dir) // '/csv/conservation_audit.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')
    write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",ES24.16,",",I0,",",I0,",",I0,",",ES24.16,",",ES24.16,",",I0,",",A,",",A,",",A)') &
      coeff_step_index, time_seconds, coeff_step_total_mass_before, coeff_last_step_total_mass_after, coeff_step_total_number_before, &
      coeff_last_step_total_number_after, coeff_last_coag_mass_before, coeff_last_coag_mass_after, coeff_last_coag_mass_residual, &
      coeff_last_coag_number_before, coeff_last_coag_number_after, coeff_last_coag_number_residual, coeff_last_coag_event_rate_sum, &
      coeff_last_min_mass, coeff_last_min_number, coeff_last_min_gas, merge(1,0,coeff_has_nan()), merge(1,0,coeff_has_inf()), &
      coeff_last_mapping_calls_step, coeff_last_mapping_build_seconds, coeff_last_objective_mean_step, coeff_last_fallback_count_step, &
      trim(coeff_scheme_name), trim(coeff_testcase), trim(coeff_process_combo)
    close(COEFF_IO_UNIT)
  end subroutine coeff_append_conservation_audit

  subroutine coeff_append_anomalies(time_seconds, size_comp_mass)
    implicit none
    double precision, intent(in) :: time_seconds
    double precision, intent(in) :: size_comp_mass(N_sizebin, N_fracmax)
    integer :: k, f
    double precision :: size_total_mass, size_total_number, value
    character(len=512) :: file_name

    file_name = trim(coeff_results_dir) // '/csv/anomaly_flags.csv'
    open(unit=COEFF_IO_UNIT, file=file_name, status='old', position='append', action='write')

    do k = 1, N_sizebin
      size_total_mass = sum(size_comp_mass(k,:))
      if (size_total_mass > 0.d0) then
        do f = 1, N_fracmax
          value = size_comp_mass(k,f) / size_total_mass
          if (value >= 0.95d0) then
            write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",A,",",I0,",",I0,",",ES24.16,",",ES24.16,",",A,",",A,",",A)') &
              coeff_step_index, time_seconds, 'composition_collapse', k, f, value, 0.95d0, trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
          endif
        enddo
      endif
    enddo

    do k = 1, N_sizebin
      size_total_mass = bin_mass(k)
      if (total_mass_t > 0.d0) then
        value = size_total_mass / total_mass_t
        if (value >= 0.90d0) then
          write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",A,",",I0,",",I0,",",ES24.16,",",ES24.16,",",A,",",A,",",A)') &
            coeff_step_index, time_seconds, 'single_bin_mass_dominance', k, 0, value, 0.90d0, trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
        endif
      endif
      size_total_number = bin_number(k)
      if (total_number > 0.d0) then
        value = size_total_number / total_number
        if (value >= 0.90d0) then
          write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",A,",",I0,",",I0,",",ES24.16,",",ES24.16,",",A,",",A,",",A)') &
            coeff_step_index, time_seconds, 'single_bin_number_dominance', k, 0, value, 0.90d0, trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
        endif
      endif
    enddo

    if (coeff_previous_total_number > 0.d0 .and. total_number > 0.d0) then
      value = total_number / coeff_previous_total_number
      if (value >= 2.d0 .or. value <= 0.5d0) then
        write(COEFF_IO_UNIT,'(I0,",",ES24.16,",",A,",",I0,",",I0,",",ES24.16,",",ES24.16,",",A,",",A,",",A)') &
          coeff_step_index, time_seconds, 'number_jump', 0, 0, value, 2.d0, trim(coeff_testcase), trim(coeff_process_combo), trim(coeff_scheme_name)
      endif
    endif

    close(COEFF_IO_UNIT)
  end subroutine coeff_append_anomalies

  double precision function coeff_composition_diversity(comp_mass)
    implicit none
    double precision, intent(in) :: comp_mass(N_fracmax)
    double precision :: total_mass_local, prob
    integer :: f

    total_mass_local = sum(comp_mass)
    coeff_composition_diversity = 0.d0
    if (total_mass_local <= 0.d0) return

    do f = 1, N_fracmax
      if (comp_mass(f) <= 0.d0) cycle
      prob = comp_mass(f) / total_mass_local
      coeff_composition_diversity = coeff_composition_diversity - prob * log(max(prob, COEFF_COMP_EPS))
    enddo
  end function coeff_composition_diversity

  subroutine coeff_format_group_fractions(values, text_out)
    implicit none
    double precision, intent(in) :: values(N_groups)
    character(len=*), intent(out) :: text_out
    integer :: g
    character(len=48) :: token

    text_out = ''
    do g = 1, N_groups
      write(token,'(ES12.5E3)') values(g)
      if (g > 1) text_out = trim(text_out) // '|'
      text_out = trim(text_out) // trim(adjustl(token))
    enddo
  end subroutine coeff_format_group_fractions

  subroutine coeff_format_int_vector(count_in, values, text_out)
    implicit none
    integer, intent(in) :: count_in
    integer, intent(in) :: values(COEFF_MAX_CANDIDATES)
    character(len=*), intent(out) :: text_out
    integer :: idx
    character(len=32) :: token

    text_out = ''
    do idx = 1, count_in
      write(token,'(I0)') values(idx)
      if (idx > 1) text_out = trim(text_out) // '|'
      text_out = trim(text_out) // trim(adjustl(token))
    enddo
  end subroutine coeff_format_int_vector

  subroutine coeff_format_real_vector(count_in, values, text_out)
    implicit none
    integer, intent(in) :: count_in
    double precision, intent(in) :: values(COEFF_MAX_CANDIDATES)
    character(len=*), intent(out) :: text_out
    integer :: idx
    character(len=48) :: token

    text_out = ''
    do idx = 1, count_in
      write(token,'(ES12.5E3)') values(idx)
      if (idx > 1) text_out = trim(text_out) // '|'
      text_out = trim(text_out) // trim(adjustl(token))
    enddo
  end subroutine coeff_format_real_vector

  logical function coeff_has_nan()
    implicit none
    coeff_has_nan = any(concentration_mass /= concentration_mass) .or. any(concentration_number /= concentration_number) .or. &
      any(concentration_gas /= concentration_gas)
  end function coeff_has_nan

  logical function coeff_has_inf()
    implicit none
    coeff_has_inf = any(abs(concentration_mass) > huge(1.d0) * 1.d-2) .or. any(abs(concentration_number) > huge(1.d0) * 1.d-2) .or. &
      any(abs(concentration_gas) > huge(1.d0) * 1.d-2)
  end function coeff_has_inf

  function coeff_cache_status_string() result(status_text)
    implicit none
    character(len=16) :: status_text

    select case (coeff_last_cache_status)
    case (COEFF_CACHE_STATUS_HIT)
      status_text = 'HIT'
    case (COEFF_CACHE_STATUS_MISS)
      status_text = 'MISS'
    case default
      status_text = 'NA'
    end select
  end function coeff_cache_status_string

  function coeff_species_name(jesp) result(name_text)
    implicit none
    integer, intent(in) :: jesp
    character(len=32) :: name_text

    select case (jesp)
    case (EMD); name_text = 'MD'
    case (EBC); name_text = 'BC'
    case (ENa); name_text = 'Na'
    case (ESO4); name_text = 'SO4'
    case (ENH4); name_text = 'NH4'
    case (ENO3); name_text = 'NO3'
    case (ECl); name_text = 'Cl'
    case (EBiA2D); name_text = 'BiA2D'
    case (EBiA1D); name_text = 'BiA1D'
    case (EBiA0D); name_text = 'BiA0D'
    case (EAGLY); name_text = 'AGLY'
    case (EAMGLY); name_text = 'AMGLY'
    case (EBiMT); name_text = 'BiMT'
    case (EBiPER); name_text = 'BiPER'
    case (EBiDER); name_text = 'BiDER'
    case (EBiMGA); name_text = 'BiMGA'
    case (EAnBlP); name_text = 'AnBlP'
    case (EAnBmP); name_text = 'AnBmP'
    case (EBiBlP); name_text = 'BiBlP'
    case (EBiBmP); name_text = 'BiBmP'
    case (EBiNGA); name_text = 'BiNGA'
    case (ENIT3); name_text = 'NIT3'
    case (EBiNIT); name_text = 'BiNIT'
    case (EAnCLP); name_text = 'AnCLP'
    case (ESOAlP); name_text = 'SOAlP'
    case (ESOAmP); name_text = 'SOAmP'
    case (ESOAhP); name_text = 'SOAhP'
    case (EPOAlP); name_text = 'POAlP'
    case (EPOAmP); name_text = 'POAmP'
    case (EPOAhP); name_text = 'POAhP'
    case (EH2O); name_text = 'H2O'
    case default
      write(name_text,'("SP",I0)') jesp
    end select
  end function coeff_species_name

end module CoeffRepartitionBoxmodel
