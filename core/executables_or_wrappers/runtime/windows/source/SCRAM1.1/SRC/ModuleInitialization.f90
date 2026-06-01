!!-----------------------------------------------------------------------
!!     Copyright (C) 2003-2014, ENPC - INRIA - EDF R&D
!!     Author(s): Shupeng Zhu
!!
!!     This file is part of the Size Composition Resolved Aerosol Model (SCRAM), a
!!     component of the air quality modeling system Polyphemus.
!!
!!     Polyphemus is developed in the INRIA - ENPC joint project-team
!!     CLIME and in the ENPC - EDF R&D joint laboratory CEREA.
!!
!!     Polyphemus is free software; you can redistribute it and/or modify
!!     it under the terms of the GNU General Public License as published
!!     by the Free Software Foundation; either version 2 of the License,
!!     or (at your option) any later version.
!!
!!     Polyphemus is distributed in the hope that it will be useful, but
!!     WITHOUT ANY WARRANTY; without even the implied warranty of
!!     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
!!     General Public License for more details.
!!
!!     For more information, visit the Polyphemus web site:
!!     http://cerea.enpc.fr/polyphemus/
!!-----------------------------------------------------------------------
!!
!!     -- DESCRIPTION
!!    This module read configuration file and initialize all global variables
!!-----------------------------------------------------------------------

module Initialization
    implicit none
    INCLUDE 'CONST.INC'
    INCLUDE 'CONST_A.INC'
    INCLUDE 'pointer.inc'

    !!part 1: parameters of system dimension
    integer :: N_size   ! total number of size and composition sections
    integer :: N_species!number of specise
    integer :: N_groups!Number of groups
    integer :: N_fracmax! maximum number of composition sections per size section
    integer :: N_frac!the Number of fraction sections
    integer :: N_aerosol !Number of aerosol species
    integer :: N_sizebin!number of  size sections
    integer :: N_organics !Number of organics aerosol species
    integer :: N_inorganic!Number of inorganic aerosol species
    integer :: N_inert!number of inert aerosol species
    integer :: N_liquid!Number of liquid internal species
    integer :: N_solid!Number of solid internal species
    integer :: N_inside_aer!Number of internal species
    integer :: N_hydrophilic!Number of hydrophilic organics aerosol species
    parameter (N_organics=23,N_inorganic=5,N_inert=2,N_liquid=12)
    parameter (N_solid=9,N_inside_aer=21, N_aerosol=31)
    parameter(N_hydrophilic=9)

    !!part 2: parameters of system option
    integer :: tag_thrm!method for wet diameter computation0 h2o 1 isorropia
    integer :: dynamic_solver  !KDSLV Tag type of solver
    integer :: sulfate_computation !ISULFCOND tag of sulfate condensation method
    integer :: redistribution_method !tag of redistribution method
    integer :: with_coag !Tag gCoagulation
    integer :: with_cond !Tag fCondensation
    integer :: with_nucl !Tag nucleation
    Integer :: aqueous_module!ICLD
    Integer :: with_incloud_scav!IINCLD
    Integer :: with_kelvin_effect!IKELV
    Integer :: with_fixed_density!IDENS
    integer :: ICUT!cutting_bin
    Integer :: nucl_model!ITERN
    Integer :: wet_diam_estimation!ITHRM
    Integer :: with_oligomerization!IOLIGO
    Integer :: thermodynamic_model!ITHERMO
    Integer :: with_number!INUM

    integer NITER_PKW,NITER_AEC_AQ
    integer NITER_POA,NITER_AEC_DRY
    double precision ::  ALFHP! percentage of H+ allowed to c/e(0.1)
    double precision ::  EPSER
    double precision ::  TINYM,TINYN,MTSBL
    double precision ::  DTMAX,DTAEROMIN
    double precision ::  DMIN,DMAX

    parameter(EPSER = 1.D-2)
    parameter(ALFHP = 0.1D0)
    parameter(TINYM = 1.D-20)
    parameter(TINYN = 1.D-15)
    parameter(DTMAX =10.D0)
    parameter(DTAEROMIN =1.D0)
    parameter(NITER_AEC_AQ = 1)
    parameter(NITER_AEC_DRY = 1)
    parameter(NITER_PKW = 5)
    parameter(NITER_POA = 10)
    parameter(MTSBL = 1.0D0)

    !!part 3: System pointers
    Integer :: E1,E2,G1,G2!Mark the begin and end of dynamic aerosol (except EH2O)
    Integer :: nesp, nesp_isorropia, nesp_aec, nesp_pankow, nesp_pom!Number of different species group
    Integer, dimension(:), allocatable :: isorropia_species
    Integer, dimension(:), allocatable :: aec_species
    Integer, dimension(:), allocatable :: pankow_species
    Integer, dimension(:), allocatable :: poa_species

    !!part 4: System state parameters
    integer :: tagrho
    integer :: tag_coag,tag_cond,tag_nucl
    double precision :: timestep_splitting,sub_timestep_splitting
    double precision :: final_time,dtmin! Time step and finnal time
    double precision :: initial_time_splitting,current_sub_time,final_sub_time!current time=initial_time_splitting+current_sub_time
    double precision :: Temperature,Relative_Humidity,Pressure,Humidity
    double precision :: fixed_density,fixed_density_l!density of overall partical
    double precision :: Cut_dim!cuting diameter between equi/dynamic
    double precision :: viscosity!Dynamic viscosity ([kg/m/s]).
    double precision :: air_free_mean_path
    double precision :: total_water!total mass of water
    double precision :: total_IH!total mass of H+
    double precision :: total_PH!overall PH value
    double precision :: n_grow_nucl,n_grow_coag,n_emis
    double precision :: m_grow_cond,m_emis
    double precision :: total_number,o_total_mass,total_mass_t
    double precision :: record_time

    !!part5: 1 dimension data array
    integer, dimension(:), allocatable :: Index_groups!index of which group the species belongs to
    integer, dimension(:), allocatable :: List_species!read species defined in cfg files
    Integer, dimension(:), allocatable :: aerosol_species_interact
    Double precision,dimension(:), allocatable :: density_aer_bin !density of each grid bins
    Double precision,dimension(:), allocatable :: density_aer_size !density of each size section
    Double precision,dimension(:), allocatable :: diam_bound! DBF diameter bounds of each size section
    Double precision,dimension(:), allocatable :: mass_bound! MBF
    Double precision,dimension(:), allocatable :: log_bound!XBF
    Double precision,dimension(:), allocatable :: frac_bound!fraction bounds of each size section
    Double precision,dimension(:), allocatable :: total_bin_mass!total mass of each size section
    Double precision,dimension(:), allocatable :: size_sect!HSF log size of each section
    Double precision,dimension(:), allocatable :: size_diam_av!DSF average diameter of each size section
    Double precision,dimension(:), allocatable :: size_mass_av!MSF average mass of each size section
    Double precision,dimension(:), allocatable :: size_log_av!XSF
    Double precision,dimension(:), allocatable :: cell_diam_av!!DSF average diameter of each grid cell
    Double precision,dimension(:), allocatable :: cell_mass_av!!MSF average mass of each grid cell
    Double precision,dimension(:), allocatable :: cell_log_av!XSF
    Double precision,dimension(:), allocatable :: total_mass!total mass of each species
    Double precision,dimension(:), allocatable :: mass_total_grid!total mass of each grid cell
    Double precision,dimension(:), allocatable :: total_aero_mass!total aerosol mass of each species
    Double precision,dimension(:), allocatable :: bin_mass!mass concentration of each size section
    Double precision,dimension(:), allocatable :: bin_number!number concentration of each size section
    Double precision,dimension(:), allocatable :: concentration_number_tmp!first order approximation of number
    Double precision,dimension(:), allocatable :: discretization_mass! vector storing discretization of size, µg
    Double precision,dimension(:), allocatable :: concentration_number!number concentration of each grid cell
    Double precision,dimension(:), allocatable :: concentration_gas! gas concentration of each species
    Double precision,dimension(:), allocatable :: wet_diameter!Aerosol wet diameter (µm). of each grid cell
    Double precision,dimension(:), allocatable :: wet_mass!Aerosol wet mass (µg). of each grid cell
    Double precision,dimension(:), allocatable :: wet_volume!Aerosol wet volume (µm^3). of each grid cell
    double precision , dimension(:), allocatable :: rho_wet_cell
    double precision , dimension(:), allocatable :: addm

    !!part6: 2+ dimension data array
    integer, dimension(:,:), allocatable :: concentration_index !matrix from grid index to size and composition index
    integer, dimension(:,:), allocatable :: concentration_index_iv !matrix from size and composition to grid index
    double precision , dimension(:,:), allocatable :: kernel_coagulation
    double precision , dimension(:,:), allocatable :: ce_kernal_coef!c/e kernal
    double precision , dimension(:,:), allocatable :: Kelvin_effect_ext!kelvin effect
    double precision , dimension(:,:), allocatable :: concentration_tmp1
    double precision , dimension(:,:), allocatable :: frac_grid !excat fraction of each species in each grid
    double precision , dimension(:,:), allocatable :: concentration_mass
    double precision , dimension(:,:), allocatable :: concentration_mass_tmp!first order apporximation
    double precision , dimension(:,:), allocatable :: concentration_inti!internal inorganic aerosol concentration ([ï¿½g.m-3]).
    double precision , dimension(:,:), allocatable :: dqdt
    double precision , dimension(:,:,:,:), allocatable :: discretization_composition! multi-array storing discretization of composition

    !! part 7: basic physical and chemical parameters
    double precision diffusion_coef(N_aerosol)
    double precision quadratic_speed(N_aerosol)
    double precision partition_coefficient(N_aerosol)
    double precision soa_sat_conc(N_aerosol)
    double precision soa_part_coef(N_aerosol)
    double precision accomodation_coefficient(N_aerosol)
    double precision surface_tension(N_aerosol)
    double precision vaporization_enthalpy(N_aerosol)!vaporization enthalpy (J.mol-1) !C
    double precision saturation_pressure(N_aerosol)! soa sat Pressure (Pascals)          !C
    double precision saturation_pressure_mass(N_aerosol),deliquescence_relative_humidity(N_aerosol)
    double precision saturation_pressure_torr(N_aerosol)
    double precision molecular_diameter(N_aerosol),collision_factor_aer(N_aerosol)
    double precision molecular_weight_aer(N_aerosol)!molar weight of external species
    double precision mass_density_solid(SNaNO3:SLC)!molar weight of internal solids species
    double precision mass_density_aer(N_aerosol)!liquid mass density µg*µm-3
    double precision molecular_weight_inside(N_liquid)!molar weight of inorganic species in aqueous_phase
    double precision molecular_weight_solid(SNaNO3:SLC)!molar weight of solids

 contains
 
  subroutine pointer_initial()
!------------------------------------------------------------------------
!
!     -- DESCRIPTION
!     This subroutine initialize system pointers
!
!------------------------------------------------------------------------
!
!     -- INPUT VARIABLES
!
!------------------------------------------------------------------------   
    implicit none

    integer jesp
    G1=ESO4
    G2=ECl
    E1=EMD
    E2=EPOAhP

    nesp_aec=16!number of H2O species
    nesp_pankow=1 !number of pankow species AnClP
    nesp_pom=6!number of primary SVOC species (including their oxydation products)
    nesp_isorropia=5
			    ! POAlP,POAmP,POAhP,SOAlP,SOAmP,SOAhP
    allocate(isorropia_species(nesp_isorropia))
    allocate(aec_species(nesp_aec))
    allocate(pankow_species(nesp_pankow))
    allocate(poa_species(nesp_pom))
    isorropia_species(1)=ENa
    isorropia_species(2)=ESO4
    isorropia_species(3)=ENH4
    isorropia_species(4)=ENO3
    isorropia_species(5)=ECl

    aec_species(1)=EBiA2D
    aec_species(2)=EBiA1D
    aec_species(3)=EBiA0D
    aec_species(4)=EAGLY
    aec_species(5)=EAMGLY
    aec_species(6)=EBiMT
    aec_species(7)=EBiPER
    aec_species(8)=EBiDER
    aec_species(9)=EBiMGA
    aec_species(10)=EAnBlP
    aec_species(11)=EAnBmP
    aec_species(12)=EBiBlP
    aec_species(13)=EBiBmP
    aec_species(14)=EBiNGA
    aec_species(15)=ENIT3
    aec_species(16)=EBiNIT

    pankow_species(1)=EAnCLP

    poa_species(1)=ESOAlP
    poa_species(2)=ESOAmP
    poa_species(3)=ESOAhP
    poa_species(4)=EPOAlP
    poa_species(5)=EPOAmP
    poa_species(6)=EPOAhP

    !relation between Aerosol and GAS
    allocate(aerosol_species_interact(N_aerosol))
    aerosol_species_interact(4)=10!SULF
    aerosol_species_interact(5)=1!NH3
    aerosol_species_interact(6)=83!HNO3
    aerosol_species_interact(7)=2!HCl
    aerosol_species_interact(8)=40!BiA2D
    aerosol_species_interact(9)=38!BiA1D
    aerosol_species_interact(10)=41!BiA0D
    aerosol_species_interact(12)=85!MGLY
    aerosol_species_interact(13)=21!BiMT
    aerosol_species_interact(14)=24!BiPER
    aerosol_species_interact(15)=25!BiDER
    aerosol_species_interact(16)=22!BiMGA
    aerosol_species_interact(17)=42!AnBlP
    aerosol_species_interact(18)=48!AnBmP
    aerosol_species_interact(19)=12!BiBlP
    aerosol_species_interact(20)=13!BiBmP
    aerosol_species_interact(21)=23!BiNGA
    aerosol_species_interact(22)=26!NIT3
    aerosol_species_interact(23)=34!BiNIT
    aerosol_species_interact(24)=50!AnClP
    aerosol_species_interact(25)=17!SOAlP
    aerosol_species_interact(26)=18!SOAmP
    aerosol_species_interact(27)=19!SOAhP
    aerosol_species_interact(28)=14!POAlP
    aerosol_species_interact(29)=15!POAmP
    aerosol_species_interact(30)=16!POAhP

   !INIT physical parameters
    do jesp=EMD,ENa
      diffusion_coef(jesp)=0.D0
      accomodation_coefficient(jesp)=0.D0
      collision_factor_aer(jesp)=1.000D10
      surface_tension(jesp)=0.D0
      molecular_diameter(jesp)=1.000D10
      saturation_pressure_mass(jesp)=0.D0
      saturation_pressure_torr(jesp)=0.D0
      deliquescence_relative_humidity(jesp)=0.D0
      partition_coefficient(jesp)=0.D0
      soa_part_coef(jesp)=0.d0
  enddo

    saturation_pressure_mass(EBiA2D)=1.43d0
    saturation_pressure_mass(EBiA1D)=1.98d0
    saturation_pressure_mass(EBiA0D)=2.44d3
    saturation_pressure_mass(EAGLY)=6.86d8
    saturation_pressure_mass(EAMGLY)=8.51d8
    saturation_pressure_mass(EBiMT)=10.7d0
    saturation_pressure_mass(EBiPER)=30.4d0
    saturation_pressure_mass(EBiDER)=3.80d0
    saturation_pressure_mass(EBiMGA)=90.4d0

    saturation_pressure_torr(EBiA2D)=1.43d-7
    saturation_pressure_torr(EBiA1D)= 2.17d-7
    saturation_pressure_torr(EBiA0D)=2.7d-4
    saturation_pressure_torr(EAGLY)=219.8d0
    saturation_pressure_torr(EAMGLY)=219.8d0
    saturation_pressure_torr(EBiMT)=1.46d-6
    saturation_pressure_torr(EBiPER)=2.61d-6
    saturation_pressure_torr(EBiDER)=4.10d-7
    saturation_pressure_torr(EBiMGA)=1.4d-5
    saturation_pressure_torr(EAnBlP)=6.8d-8
    saturation_pressure_torr(EAnBmP)=8.4d-6
    saturation_pressure_torr(EBiBlP)=6.0d-10
    saturation_pressure_torr(EBiBmP)=3.0d-7
    saturation_pressure_torr(EBiNGA)=1.39d-5
    saturation_pressure_torr(ENIT3)=1.45d-6
    saturation_pressure_torr(EBiNIT)=2.5d-6

    partition_coefficient(EBiA2D)=6.25d-3
    partition_coefficient(EBiA1D)= 2.73d-3
    partition_coefficient(EBiA0D)=4.82d-5
    partition_coefficient(EAGLY)=6.56d-4
    partition_coefficient(EAMGLY)=5.78d-12
    partition_coefficient(EBiMT)=0.8052d0
    partition_coefficient(EBiPER)=0.1109d0
    partition_coefficient(EBiDER)=2.8d0
    partition_coefficient(EBiMGA)=1.1281d-2
    partition_coefficient(EAnClP)=55.56d0
    partition_coefficient(EPOAlP)=1.1d0
    partition_coefficient(EPOAmP)=0.0116d0
    partition_coefficient(EPOAhP)=0.00031d0
    partition_coefficient(ESOAlP)=110.0d0
    partition_coefficient(ESOAmP)=1.16d0
    partition_coefficient(ESOAhP)=0.031d0

    deliquescence_relative_humidity(EBiA2D)=0.79d0

    collision_factor_aer(4)=77.3d0
    collision_factor_aer(5)=558.3d0
    collision_factor_aer(6)=475.9d0
    collision_factor_aer(7)=344.7d0
    molecular_diameter(4)=5.5d0
    molecular_diameter(5)=2.9d0
    molecular_diameter(6)=3.3d0
    molecular_diameter(7)=3.339d0
    do jesp=ESO4,ECl
	surface_tension(jesp)=80.D-03!ero fixed surf tension (N.m-1)
    enddo
    do jesp=G1,E2
	accomodation_coefficient(jesp)=0.5D0
    enddo
    do jesp=EBiA2D,EPOAhP
      collision_factor_aer(jesp)=687.d0
      molecular_diameter(jesp)=8.39d0
      surface_tension(jesp)=30.D-03
    enddo
    collision_factor_aer(EH2O)=1.000D10
    molecular_diameter(EH2O)=1.000D10
    accomodation_coefficient(EH2O)=0.D0
     
!molecular_weight_aer(!C)   molar weight of external species  µg.mol-1
    molecular_weight_aer(EMD)=28.0D06
    molecular_weight_aer(EBC)=12.0D06
    molecular_weight_aer(ENa)=23.0D06
    molecular_weight_aer(ESO4)=96.0D06
    molecular_weight_aer(ENH4)=18.0D06
    molecular_weight_aer(ENO3)=63.0D06
    molecular_weight_aer(ECl)=35.5D06
    molecular_weight_aer(EBiA2D)=186.0D06
    molecular_weight_aer(EBiA1D)=170.0D06
    molecular_weight_aer(EBiA0D)=168.0D06
    molecular_weight_aer(EAGLY)=58.0D06
    molecular_weight_aer(EAMGLY)=72.0D06
    molecular_weight_aer(EBiMT)=136.0D06
    molecular_weight_aer(EBiPER)=168.0D06
    molecular_weight_aer(EBiDER)=136.0D06
    molecular_weight_aer(EBiMGA)=120.0D06
    molecular_weight_aer(EAnBlP)=167.0D06
    molecular_weight_aer(EAnBmP)=152.0D06
    molecular_weight_aer(EBiBlP)=298.0D06
    molecular_weight_aer(EBiBmP)=236.0D06
    molecular_weight_aer(EBiNGA)=165.0D06
    molecular_weight_aer(ENIT3)=272.0D06
    molecular_weight_aer(EBiNIT)=215.0D06
    molecular_weight_aer(EAnCLP)=167.0D06
    molecular_weight_aer(ESOAlP)=392.0D06
    molecular_weight_aer(ESOAmP)=392.0D06
    molecular_weight_aer(ESOAhP)=392.0D06
    molecular_weight_aer(EPOAlP)=280.0D06
    molecular_weight_aer(EPOAmP)=280.0D06
    molecular_weight_aer(EPOAhP)=280.0D06
    molecular_weight_aer(EH2O)= 18.0D06
!*       molecular_weight_inside(*)   molar weight of inorganic species *
!*       in aqueous_phase           µg.mol-1                *
    molecular_weight_inside(IH)=1.0D06
    molecular_weight_inside(INa)=23.0D06
    molecular_weight_inside(INH4)=18.0D06
    molecular_weight_inside(ICl)=35.5D06
    molecular_weight_inside(ISO4)=96.0D06
    molecular_weight_inside(IHSO4)=97.0D06
    molecular_weight_inside(INO3)=63.0D06
    molecular_weight_inside(IH2O)=18.0D06
    molecular_weight_inside(INH3)=17.0D06
    molecular_weight_inside(IHCl)=36.5D06
    molecular_weight_inside(IHNO3)=63.0D06
    molecular_weight_inside(IOH)=17.0D06
!      molar weight of solids
    molecular_weight_solid(SNaNO3)=85.0D06
    molecular_weight_solid(SNH4NO3)=80.0D06
    molecular_weight_solid(SNACl)=58.5D06
    molecular_weight_solid(SNH4Cl)=53.5D06
    molecular_weight_solid(SNa2SO4)=142.0D06
    molecular_weight_solid(SNH42S4)=132.0D06
    molecular_weight_solid(SNaHSO4)=120.0D06
    molecular_weight_solid(SNH4HS4)=115.0D06
    molecular_weight_solid(SLC)=247.0D06
!      DENSITIES of solids
    mass_density_solid(SNaNO3)=2.260D-06
    mass_density_solid(SNH4NO3)=1.725D-06
    mass_density_solid(SNACl)=2.165D-06
    mass_density_solid(SNH4Cl)=1.530D-06
    mass_density_solid(SNa2SO4)=2.700D-06
    mass_density_solid(SNH42S4)=1.770D-06
    mass_density_solid(SNaHSO4)=2.740D-06
    mass_density_solid(SNH4HS4)=1.780D-06
    mass_density_solid(SLC)=1.770D-06

!LIQUID MASS DENSITIES EXPRESSED IN µg.µm-3
    mass_density_aer(EMD)=2.33D-06
    mass_density_aer(EBC)=2.25D-06
    mass_density_aer(ENa)=0.97D-06
    mass_density_aer(ESO4)=1.80D-06
    mass_density_aer(ENH4)=0.91D-06
    mass_density_aer(ENO3)=1.50D-06
    mass_density_aer(ECl)=1.15D-06
    do jesp=EBiA2D,EPOAhP
      mass_density_aer(jesp)=1.30D-06
    enddo
    mass_density_aer(EH2O)=1.00D-06

    do jesp=1,ECl
      saturation_pressure(jesp)=0.d0
    enddo
    saturation_pressure(EBiA2D)=1.9D-5
    saturation_pressure(EBiA1D)=2.89D-5
    saturation_pressure(EBiA0D)=3.6D-2
    saturation_pressure(EAGLY)=29.3D3
    saturation_pressure(EAMGLY)=29.3D3
    saturation_pressure(EBiMT)=1.93D-4
    saturation_pressure(EBiPER)=3.48D-4
    saturation_pressure(EBiDER)=5.46D-5
    saturation_pressure(EBiMGA)=1.86D-3
    saturation_pressure(EAnBlP)=9.06D-6
    saturation_pressure(EAnBmP)=1.12D-3
    saturation_pressure(EBiBlP)=8.0D-8
    saturation_pressure(EBiBmP)=4.0D-5
    saturation_pressure(EBiNGA)=1.86D-3
    saturation_pressure(ENIT3)=1.93D-4
    saturation_pressure(EBiNIT)=3.33D-4
    saturation_pressure(EAnCLP)=2.67D-7
    saturation_pressure(ESOAlP)=8.98D-7
    saturation_pressure(ESOAmP)=8.52D-5
    saturation_pressure(ESOAhP)=3.19D-3
    saturation_pressure(EPOAlP)=8.98D-6
    saturation_pressure(EPOAmP)=8.52D-4
    saturation_pressure(EPOAhP)=3.19D-2
    saturation_pressure(EH2O)= 0.0D0

    do jesp=1,ECl
      vaporization_enthalpy(jesp)=0.d0
    enddo
    vaporization_enthalpy(EBiA2D)=109.0d3
    vaporization_enthalpy(EBiA1D)=50.0D3
    vaporization_enthalpy(EBiA0D)=50.0D3
    vaporization_enthalpy(EAGLY)=25.0D3
    vaporization_enthalpy(EAMGLY)=38.0D03
    vaporization_enthalpy(EBiMT)=38.4D03
    vaporization_enthalpy(EBiPER)=38.4D03
    vaporization_enthalpy(EBiDER)=38.4D03
    vaporization_enthalpy(EBiMGA)=43.2D03
    vaporization_enthalpy(EAnBlP)=50.0D03
    vaporization_enthalpy(EAnBmP)=50.0D03
    vaporization_enthalpy(EBiBlP)=175.0D3
    vaporization_enthalpy(EBiBmP)=175.0D3
    vaporization_enthalpy(EBiNGA)=43.2D3
    vaporization_enthalpy(ENIT3)=38.4D03
    vaporization_enthalpy(EBiNIT)=50.0D03
    vaporization_enthalpy(EAnCLP)=50.0D03
    vaporization_enthalpy(ESOAlP)=106.0D03
    vaporization_enthalpy(ESOAmP)=91.0D03
    vaporization_enthalpy(ESOAhP)=79.0D03
    vaporization_enthalpy(EPOAlP)=106.0D03
    vaporization_enthalpy(EPOAmP)=91.0D03
    vaporization_enthalpy(EPOAhP)=79.0D03
    vaporization_enthalpy(EH2O)= 0.0D0
    
   end subroutine pointer_initial


end module Initialization
