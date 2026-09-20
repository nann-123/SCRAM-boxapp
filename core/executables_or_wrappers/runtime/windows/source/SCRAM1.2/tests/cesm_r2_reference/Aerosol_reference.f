      subroutine ref_compute_condensation_transfer_rate(diffusivity,
     $     velocity, accomodation, wet_diameter, rate)

      double precision diffusivity, velocity, accomodation
      double precision wet_diameter, rate, diameter_m, knudsen

c     Existing diameter API is micrometers; retain the 1 nm floor.
      diameter_m = 1.d-6 * dmax1(wet_diameter, 1.d-3)

c     velocity is the MEAN molecular thermal speed sqrt(8RT/pi/M),
c     despite the legacy name compute_quadratic_mean_velocity.
c     For the Fuchs-Sutugin mass-transfer correction lambda=3D/velocity,
c     so Kn=lambda/r=6D/(velocity*d). Modal and sectional descriptions
c     integrate/evaluate the SAME single-particle kernel.
      knudsen = 6.d0 * diffusivity / (velocity * diameter_m)

c     Zero accommodation is a reflecting surface, including D=0.
      if (accomodation.eq.0.d0) then
         rate = 0.d0
         return
      endif

c     Continuous Fuchs-Sutugin expression in every transport regime.
c     Do not switch to asymptotic formulas at finite Kn: that introduced
c     a discontinuity and an inconsistent transition-regime mass sink.
c     Limits: Kn->0 rate=2*pi*D*d; Kn->infinity rate=alpha*v*pi*d*d/4.
c     No Kelvin or thermodynamic surface-vapor-pressure term is added.
      rate = 6.283185307178d0 * diffusivity * diameter_m
     $     * (7.5d-1*accomodation*(1.d0 + knudsen))
     $     / (knudsen*knudsen + knudsen
     $     + 2.83d-1*knudsen*accomodation
     $     + 7.5d-1*accomodation)

      end



      subroutine ref_compute_kelvin_coefficient(temperature, weight,
     $     surface_tension, wet_diameter, density, coefficient)

      double precision temperature
      double precision weight
      double precision surface_tension
      double precision wet_diameter
      double precision density

      double precision coefficient

      double precision kelvin_arg, denom

      denom = 8.314d0 * temperature * density * wet_diameter
      if (denom .le. 0.d0) then
        coefficient = 1.d0
        return
      endif
      kelvin_arg = 4.d3 * surface_tension * weight / denom
c     Cap exponent to prevent dexp overflow (709 ~ ln(HUGE));
c     physically, Kelvin_effect > ~3 is already unrealistic.
      if (kelvin_arg .gt. 500.d0) kelvin_arg = 500.d0
      coefficient = dexp(kelvin_arg)

      end


