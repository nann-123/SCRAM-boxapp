#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "glodef.h"
#include <math.h>

/* global variables */
extern double RH, LWC, temperature;
extern double totA[NAMOL+1], acHP, Critsol, LWCTOL;
extern int naero, zsrflag, anrerrflag, saturationflag;
extern double g[NAMOL+1];
extern int NK[NAMOL+1] , aidx[NAAERO+1];
extern double VP[NAMOL+1] , MW[NAAERO+1], K[NAAERO+1], DRH[NAMOL+1];
extern double Keff[NAAERO+1], Koeffref[NAAERO+1], pHoref;
extern double GAMMAinf[NAMOL];
extern double HVAPA[NAMOL+1];
extern double VPAtorr[NAMOL+1];
extern double K0A[NAMOL+1];

/* global functions */
extern void thermoa (double xx[], double gamma[], int n);

/*#ifdef POLYPHEMUS_PARALLEL_WITH_OPENMP
#pragma omp threadprivate(RH, LWC, temperature, totA, acHP, Critsol, \
                          LWCTOL, naero, zsrflag, anrerrflag, \
			  saturationflag, g, NK, aidx, VP, MW, \
                          K, DRH, Keff, Koeffref, pHoref)
						  #endif*/

/*********************************************************************** 
Purpose: Compute gas phase concentrations at local equilibrium for hydrophilic
         compounds

****************************************************************************/
/* double amain (double *aero, double *aeros) */
void amain_loc(float gasa[], float aeroa[], int* ioligo)
{
  /* external subroutines */
  extern double pow(double x, double y);

  /* need to allocate space for check to avoid overwriting x[1] */
  int i, j;              /* dummy counter reused in several places */
  int ieq;               /* ieq counts the selected equations */
  int jeq;               /* jeq loops through all equations */     

  /*
   * oligomerization correction on H & K partition parameters
   */
  
  double cHP = 1. * acHP;
  double cHPref = pow(10.0, -pHoref);
  /* H+ concentration in mol/L, needed to correct oligomerization constant */

  double correcHP = pow(cHP / cHPref, 1.91);
  /* Koeffref correction due to pH */
  double x[NAMOL+1],gammar[NAMOL+1];
  double Kpart[NAMOL+1];
  double tmol;

  /* if oligomerization, modifies Keff */
  if (LWC>LWC_ZERO)
    {
      if (*ioligo == 1)
        {
          for (i = 1; i <= NAAERO; i ++)
            {
              Keff[i] = K[i] * (1.0 + Koeffref[i] * correcHP);
            }
          /* only A0D is affected */
        }
      else
        for (i = 1; i <= NAAERO; i ++) Keff[i] = K[i];
  
      tmol=0.0;
      ieq=1;
      for (i = 0; i < NAMOL; i ++)
        {
          x[i] = aeroa[i+1]/MW[ieq];
          ieq+=NK[i];
          tmol+=x[i];
        }

      x[NAMOL] = LWC / MW[0];
      tmol+=x[NAMOL];
      if (tmol>0.0)
        {
          for (i = 0; i < NAMOL; i ++)
            {
              x[i]=x[i]/tmol;
            }
  
          thermoa (x, gammar, NAMOL+1);
          for ( i = 0; i < NAMOL; i ++) gammar[i]=gammar[i]/GAMMAinf[i];
      
          jeq=1;
          for (i = 1; i <= NAMOL; i ++) {
            if (NK[i] >= 2) {
              if (NK[i] == 3)
                Kpart[i]=Keff[jeq]*(1.0+Keff[jeq+1]/acHP+Keff[jeq+1]*Keff[jeq+2]/acHP/acHP)/gammar[i-1];
              if (NK[i] == 2)
                {
                  Kpart[i]=Keff[jeq]*(1.0+Keff[jeq+1]/acHP)/gammar[i-1];
                }
            }
            else
              Kpart[i]=Keff[jeq]/gammar[i-1];
            Kpart[i]=Kpart[i]*298.0/temperature*exp(HVAPA[i]*1000.0/8.314*(1.0/temperature-1.0/298.0));
            jeq+=NK[i];
          }
      
          for (i = 1; i <= NAMOL; i ++) {
            gasa[i]=aeroa[i]/(Kpart[i]*LWC);
          }
        }
      else
        for (i = 1; i <= NAMOL; i ++) gasa[i]=0.0;
    }
  else
    {
      tmol=0.0;
      ieq=1;
      float MO=0.0;
      for (i = 0; i < NAMOL; i ++)
        {
          x[i] = aeroa[i+1]/MW[ieq];
          MO+=aeroa[i+1];
          ieq+=NK[i];
          tmol+=x[i];
        }

      x[NAMOL] = 0.0;
      if (tmol>0.0)
        {
          for (i = 0; i < NAMOL; i ++)
            {
              x[i]=x[i]/tmol;
            }
  
          thermoa (x, gammar, NAMOL+1);

          float MWaom=0.0;
          ieq=1;
          for (i = 0; i < NAMOL; i ++) 
            {
              MWaom+=x[i]*MW[ieq];
              ieq+=NK[i+1];
            }
        

          for (i = 1; i <= NAMOL; i ++) {
            Kpart[i]=760.0*8.202e-5*temperature/(MWaom*1.0e6*VPAtorr[i]*gammar[i-1])*exp(HVAPA[i]*1000.0/8.314*(1.0/temperature-1.0/298.0));
            if (*ioligo == 1) Kpart[i]=Kpart[i]*(1.0+K0A[i]);
            gasa[i]=aeroa[i]/(Kpart[i]*MO);
          }

        }
      else
        for (i = 1; i <= NAMOL; i ++) {
          gasa[i]=0.0;
      }
    }

  return;
}
