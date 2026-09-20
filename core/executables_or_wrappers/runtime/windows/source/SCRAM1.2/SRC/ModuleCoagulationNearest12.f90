! SCRAM1.2 (2026-09-17): production dynamic coagulation repartition port.
! Source: CESM-SCRAM cesm-scram-optics-20260915-r2, CAM e6ef92321df7.
! Adaptations: original 4-D composition bands, N_species dry-species list,
! standalone density units, local actual-step budget, and CSV audit counters.
! This mode recomputes product placement from state; no weighted-cache reuse.
! Coagulation conserves species mass but loses one particle per pair event.
!!-----------------------------------------------------------------------
!!     Analytical deterministic coagulation repartition module.
!!     Ported from boxapp ModuleCoeffRepartitionBoxmodel.f90 to CESM/SCRAM.
!!
!!     This module provides coefficient-free coagulation product placement
!!     by analytically computing the merged product particle state (diameter,
!!     composition) and locating the target cell from the size/composition
!!     band definitions.
!!
!!     Eliminates the need for pre-computed repartition coefficient files.
!!
!!     Optimizations H+I:
!!       H: active cell index + cell_total_mass cache
!!       I: per-particle mass cache (eliminates inner-loop divisions)
!!-----------------------------------------------------------------------
Module CoagulationNearest12
  use Initialization
  implicit none

  private
  public :: nearest_rate, scram_coag_flux_dt, nearest_event_rate_sum
  double precision :: scram_coag_flux_dt = 0.d0
  double precision :: nearest_event_rate_sum = 0.d0

contains

  !-----------------------------------------------------------------------
  ! Main entry: compute coagulation rates using analytical band-based
  ! target selection. Replaces the legacy Gain/Loss coefficient-based Rate.
  !-----------------------------------------------------------------------
  subroutine nearest_rate(rate_number, rate_mass, c_number, c_mass)
    implicit none
    double precision, intent(out) :: rate_number(N_size)
    double precision, intent(out) :: rate_mass(N_size, N_aerosol)
    double precision, intent(in)  :: c_number(N_size)
    double precision, intent(in)  :: c_mass(N_size, N_aerosol)

    integer :: i, j, s, jesp, tgt, ia, ja, n_active
    double precision :: event_rate, src_mass_i, src_mass_j
    double precision :: prod_diameter, prod_density, prod_total_mass
    double precision :: prod_groupfrac(N_groups)
    integer :: N_dry_species
    double precision :: mass_threshold
    ! Positivity-preserving cumulative net-flux budget.
    double precision :: event_rate_lim, er_tmp, loss_per_event
    double precision :: dt_lim    ! alias for scram_coag_flux_dt; 0 = disabled
    double precision, parameter :: COAG_BUDGET_SAFETY = 1.d0 - 1.d-12
    integer :: c, src_count, tgt_count

    ! Pre-computed arrays (H+I: active cell list, mass caches)
    integer :: active_cells(N_size)
    double precision :: cell_mass_cache(N_size)
    double precision :: ppm_cache(N_size, N_aerosol)
    double precision :: number_loss_budget(N_size)
    double precision :: mass_loss_budget(N_size, N_aerosol)

    N_dry_species = N_species   ! exclude water (last in List_species)
    nearest_event_rate_sum = 0.d0
    rate_number = 0.d0
    rate_mass   = 0.d0

    ! Read sub-timestep for cumulative positivity limiting (0 = disabled).
    ! Budgets are net loss rates and are decremented after each accepted pair.
    dt_lim = scram_coag_flux_dt
    number_loss_budget = huge(1.d0)
    mass_loss_budget = huge(1.d0)
    if (dt_lim > 0.d0) then
      do i = 1, N_size
        number_loss_budget(i) = COAG_BUDGET_SAFETY * max(c_number(i),0.d0) / dt_lim
        do s = 1, N_species
          jesp = List_species(s)
          mass_loss_budget(i,jesp) = COAG_BUDGET_SAFETY * max(c_mass(i,jesp),0.d0) / dt_lim
        end do
      end do
    end if

    ! --- H+I: scan all cells, build active list, cache masses ---
    mass_threshold = dble(N_dry_species) * TINYM
    n_active = 0
    do i = 1, N_size
      if (c_number(i) <= TINYN) cycle
      cell_mass_cache(i) = 0.d0
      do s = 1, N_dry_species
        jesp = List_species(s)
        cell_mass_cache(i) = cell_mass_cache(i) + c_mass(i, jesp)
        ppm_cache(i, jesp) = c_mass(i, jesp) / max(c_number(i), TINYN)
      end do
      if (cell_mass_cache(i) <= mass_threshold) cycle
      n_active = n_active + 1
      active_cells(n_active) = i
    end do

    ! --- Main pair loop over active cells only (H) ---
    do ia = 1, n_active
      i = active_cells(ia)

      do ja = 1, ia
        j = active_cells(ja)

        ! Compute event rate: K(i,j) * N_i * N_j, with 0.5 for self-coagulation
        if (i == j) then
          event_rate = 0.5d0 * kernel_coagulation(i, j) * c_number(i) * c_number(j)
        else
          event_rate = kernel_coagulation(i, j) * c_number(i) * c_number(j)
        end if
        if (event_rate <= 0.d0) cycle

        ! Compute product state using cached per-particle masses (I)
        call compute_product_state_cached(i, j, ppm_cache, N_dry_species, &
             prod_total_mass, prod_diameter, prod_density, prod_groupfrac)

        if (.not. target_state_is_valid(prod_total_mass, prod_diameter, &
             prod_density, prod_groupfrac)) then
          tgt = fallback_target_cell(i, j, cell_mass_cache)
        else
          tgt = find_target_cell_by_band(prod_diameter, prod_groupfrac)
          if (tgt <= 0) then
            tgt = fallback_target_cell(i, j, cell_mass_cache)
          end if
        end if

        ! Cumulative net-flux limiter.  Account for source/target coincidence
        ! before applying a budget: i=j=tgt has one net number loss per event
        ! and zero net mass loss, while i/=j,tgt=i depletes only source j.
        if (dt_lim > 0.d0) then
          event_rate_lim = event_rate
          do c = 1, N_size
            src_count = 0
            if (c == i) src_count = src_count + 1
            if (c == j) src_count = src_count + 1
            if (src_count == 0) cycle
            tgt_count = 0
            if (c == tgt) tgt_count = 1
            if (src_count > tgt_count) then
              er_tmp = number_loss_budget(c) / dble(src_count - tgt_count)
              event_rate_lim = min(event_rate_lim, er_tmp)
            end if
            do s = 1, N_dry_species
              jesp = List_species(s)
              loss_per_event = 0.d0
              if (c == i) loss_per_event = loss_per_event + ppm_cache(i,jesp)
              if (c == j) loss_per_event = loss_per_event + ppm_cache(j,jesp)
              if (c == tgt) loss_per_event = loss_per_event - &
                   (ppm_cache(i,jesp) + ppm_cache(j,jesp))
              if (loss_per_event > 0.d0) then
                er_tmp = mass_loss_budget(c,jesp) / loss_per_event
                event_rate_lim = min(event_rate_lim, er_tmp)
              end if
            end do
          end do
          if (event_rate_lim <= 0.d0) cycle
          event_rate = event_rate_lim

          ! Consume cumulative budgets using the same net stoichiometry.
          do c = 1, N_size
            src_count = 0
            if (c == i) src_count = src_count + 1
            if (c == j) src_count = src_count + 1
            if (src_count == 0) cycle
            tgt_count = 0
            if (c == tgt) tgt_count = 1
            if (src_count > tgt_count) then
              number_loss_budget(c) = max(0.d0, number_loss_budget(c) - &
                   event_rate * dble(src_count - tgt_count))
            end if
            do s = 1, N_dry_species
              jesp = List_species(s)
              loss_per_event = 0.d0
              if (c == i) loss_per_event = loss_per_event + ppm_cache(i,jesp)
              if (c == j) loss_per_event = loss_per_event + ppm_cache(j,jesp)
              if (c == tgt) loss_per_event = loss_per_event - &
                   (ppm_cache(i,jesp) + ppm_cache(j,jesp))
              if (loss_per_event > 0.d0) then
                mass_loss_budget(c,jesp) = max(0.d0, mass_loss_budget(c,jesp) - &
                     event_rate * loss_per_event)
              end if
            end do
          end do
        end if

        nearest_event_rate_sum = nearest_event_rate_sum + event_rate

        ! Source number loss: both parent cells lose particles
        rate_number(i) = rate_number(i) - event_rate
        rate_number(j) = rate_number(j) - event_rate
        ! Product number gain: target gains the same number of new particles
        rate_number(tgt) = rate_number(tgt) + event_rate

        ! Mass transfer using cached per-particle mass (I: no divisions here)
        do s = 1, N_dry_species
          jesp = List_species(s)
          src_mass_i = event_rate * ppm_cache(i, jesp)
          src_mass_j = event_rate * ppm_cache(j, jesp)
          ! Source losses
          rate_mass(i, jesp) = rate_mass(i, jesp) - src_mass_i
          rate_mass(j, jesp) = rate_mass(j, jesp) - src_mass_j
          ! Product gain at target (conserves total mass)
          rate_mass(tgt, jesp) = rate_mass(tgt, jesp) + src_mass_i + src_mass_j
        end do

      end do
    end do

  end subroutine nearest_rate

  !-----------------------------------------------------------------------
  ! Compute product state using pre-computed per-particle mass cache (I).
  ! Identical to compute_product_state but avoids division in the hot loop.
  !-----------------------------------------------------------------------
  subroutine compute_product_state_cached(src1, src2, ppm_cache, N_dry_species, &
       total_mass, diameter, effective_density, group_frac)
    implicit none
    integer, intent(in) :: src1, src2, N_dry_species
    double precision, intent(in) :: ppm_cache(N_size, N_aerosol)
    double precision, intent(out) :: total_mass, diameter, effective_density
    double precision, intent(out) :: group_frac(N_groups)

    integer :: s, jesp
    double precision :: ppm, total_volume, group_mass(N_groups)
    double precision, parameter :: PI_LOCAL = 3.14159265358979323846d0

    total_mass = 0.d0
    total_volume = 0.d0
    group_mass = 0.d0

    ! Sum per-particle mass from both source cells (dry species)
    do s = 1, N_dry_species
      jesp = List_species(s)
      ppm = ppm_cache(src1, jesp) + ppm_cache(src2, jesp)
      total_mass = total_mass + ppm
      total_volume = total_volume + ppm / merge(mass_density_aer(jesp), fixed_density, mass_density_aer(jesp) > 0.d0)
      group_mass(Index_groups(s)) = group_mass(Index_groups(s)) + ppm
    end do

    ! Diameter from total volume (sphere equivalent)
    if (total_volume > 0.d0) then
      diameter = (6.d0 * total_volume / PI_LOCAL) ** (1.d0 / 3.d0)
      effective_density = total_mass / total_volume
      ! Physical floor (Fix F): coagulation strictly conserves volume, so
      ! the product must be at least as large as the larger source particle.
      ! When ppm_cache is unphysically small (mass-number mismatch in cells),
      ! the computed diameter may violate this. Enforce cell_diam_av floor to
      ! prevent coagulation products from spuriously landing in bin1.
      diameter = max(diameter, max(cell_diam_av(src1), cell_diam_av(src2)))
    else
      diameter = max(cell_diam_av(src1), cell_diam_av(src2))
      effective_density = fixed_density
    end if

    ! Group fractions from dry mass
    group_frac = 0.d0
    if (total_mass > 0.d0) group_frac = group_mass / total_mass

  end subroutine compute_product_state_cached

  !-----------------------------------------------------------------------
  ! Validate the computed product state.
  !-----------------------------------------------------------------------
  logical function target_state_is_valid(total_mass, diameter, eff_density, group_frac)
    implicit none
    double precision, intent(in) :: total_mass, diameter, eff_density
    double precision, intent(in) :: group_frac(N_groups)
    double precision :: sg

    target_state_is_valid = .false.
    if (total_mass /= total_mass) return          ! NaN check
    if (diameter /= diameter) return
    if (eff_density /= eff_density) return
    if (total_mass <= TINYM) return
    if (diameter <= diam_bound(1) * 1.d-6) return
    if (eff_density <= TINYM) return
    if (any(group_frac /= group_frac)) return     ! NaN in fractions
    if (any(group_frac < -1.d-8)) return
    if (any(group_frac > 1.d0 + 1.d-8)) return
    sg = sum(group_frac)
    if (sg /= sg) return
    if (abs(sg - 1.d0) > 1.d-4) return
    target_state_is_valid = .true.
  end function target_state_is_valid

  !-----------------------------------------------------------------------
  ! Locate the target cell from the configured size and composition bands.
  ! Size bins use [b1,b2], (b2,b3], ..., (bN,bN+1] to avoid overlaps while
  ! keeping exact boundary ownership deterministic. Fraction bands use the
  ! same lower/upper-bound rules as redistribution_fraction().
  !-----------------------------------------------------------------------
  integer function find_target_cell_by_band(diameter, group_frac)
    implicit none
    double precision, intent(in) :: diameter
    double precision, intent(in) :: group_frac(N_groups)

    integer :: size_bin, frac_bin

    size_bin = find_size_bin_by_band(diameter)
    if (size_bin <= 0) then
      find_target_cell_by_band = 0
      return
    end if

    frac_bin = find_fraction_bin_by_band(group_frac)
    if (frac_bin <= 0) then
      find_target_cell_by_band = 0
      return
    end if

    find_target_cell_by_band = concentration_index_iv(size_bin, frac_bin)

  end function find_target_cell_by_band

  !-----------------------------------------------------------------------
  ! Locate the size bin from bin boundaries instead of nearest size center.
  ! Products above the configured top bound are saturated into the last bin.
  !-----------------------------------------------------------------------
  integer function find_size_bin_by_band(diameter)
    implicit none
    double precision, intent(in) :: diameter

    integer :: k
    double precision :: diameter_limited

    diameter_limited = max(diameter, diam_bound(1))
    find_size_bin_by_band = N_sizebin

    do k = 1, N_sizebin
      if (k == 1) then
        if (diameter_limited <= diam_bound(k + 1)) then
          find_size_bin_by_band = k
          return
        end if
      else
        if (diameter_limited > diam_bound(k) .and. diameter_limited <= diam_bound(k + 1)) then
          find_size_bin_by_band = k
          return
        end if
      end if
    end do

  end function find_size_bin_by_band

  !-----------------------------------------------------------------------
  ! Locate the composition cell from the configured fraction bands.
  ! Uses the same boundary semantics as redistribution_fraction().
  !-----------------------------------------------------------------------
  integer function find_fraction_bin_by_band(group_frac)
    implicit none
    double precision, intent(in) :: group_frac(N_groups)

    integer :: f, g
    double precision :: flo, fhi
    logical :: matches_band

    if (N_fracmax <= 1 .or. N_groups <= 1) then
      find_fraction_bin_by_band = 1
      return
    end if

    find_fraction_bin_by_band = 0
    do f = 1, N_fracmax
      matches_band = .true.
      do g = 1, N_groups - 1
        flo = discretization_composition(1, f, g, 1)
        fhi = discretization_composition(1, f, g, 2)
        if (.not. fraction_in_band(group_frac(g), flo, fhi)) then
          matches_band = .false.
          exit
        end if
      end do
      if (matches_band) then
        find_fraction_bin_by_band = f
        return
      end if
    end do

  end function find_fraction_bin_by_band

  !-----------------------------------------------------------------------
  ! Boundary semantics shared with redistribution_fraction().
  !-----------------------------------------------------------------------
  logical function fraction_in_band(val, lo, hi)
    implicit none
    double precision, intent(in) :: val, lo, hi

    if (lo == 0.d0) then
      fraction_in_band = (val >= lo .and. val <= hi)
    else
      fraction_in_band = (val > lo .and. val <= hi)
    end if

  end function fraction_in_band

  !-----------------------------------------------------------------------
  ! Fallback for invalid/unclassifiable product states.
  !-----------------------------------------------------------------------
  integer function fallback_target_cell(src1, src2, cell_mass_cache)
    implicit none
    integer, intent(in) :: src1, src2
    double precision, intent(in) :: cell_mass_cache(N_size)
    integer :: sbin_1, sbin_2

    sbin_1 = concentration_index(src1, 1)
    sbin_2 = concentration_index(src2, 1)

    if (sbin_2 > sbin_1) then
      fallback_target_cell = src2
    elseif (sbin_1 > sbin_2) then
      fallback_target_cell = src1
    elseif (cell_mass_cache(src2) > cell_mass_cache(src1)) then
      fallback_target_cell = src2
    else
      fallback_target_cell = src1
    end if

  end function fallback_target_cell

  !-----------------------------------------------------------------------
  ! Total (dry) mass in a cell, summing over dry species.
  !-----------------------------------------------------------------------
  double precision function cell_total_mass(cell_idx, c_mass, N_dry_species)
    implicit none
    integer, intent(in) :: cell_idx, N_dry_species
    double precision, intent(in) :: c_mass(N_size, N_aerosol)
    integer :: s, jesp

    cell_total_mass = 0.d0
    do s = 1, N_dry_species
      jesp = List_species(s)
      cell_total_mass = cell_total_mass + c_mass(cell_idx, jesp)
    end do
  end function cell_total_mass

end module CoagulationNearest12
