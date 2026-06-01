#include <stdio.h>
#include "glodef.h"
#include <math.h>

/* global variables */
extern double PAOM;
extern double cb[NBSP+1];
extern int Newtflag, bnrerrflag;
extern int aidxb[NBSP+1];
extern double VPB[NBSP+1];
extern double VPCrit;
extern double temperature;
extern double xaom[NBSP+1];
extern double MWB[NBSP+1];
extern double K0B[NBSP+1];
extern double HVAPB[NBSP+1];

#ifdef POLYPHEMUS_PARALLEL_WITH_OPENMP
#pragma omp threadprivate(PAOM, cb, Newtflag, bnrerrflag, aidxb, VPB)
#endif

extern void thermob (double xx[], double gamma[], int n);


/**************************************************************************
Purpose:  Compute gas phase concentrations at local equilibrium for 
          hydrophobic compounds

*************************************************************************/
void bmain_loc (float gas[], float aero[], float MWaom, float MO, float cPOA, int* ioligo)
{
  int i;                           /* dummy counter */
  float Kpart[NBSP+1];
  double ac[NBSP+NBSPAOM];
  double x[NBSP+NBSPAOM];
  double totx;
  
  if (MO>0.0)
    {
      totx=cPOA;
      for (i = 0; i < NBSPAOM; i ++) x[i]=cPOA*xaom[i];

      for (i = 0; i < NBSP; i ++) {
        x[i+NBSPAOM]=aero[i+1]/MWB[i+1];
        totx+=x[i+NBSPAOM];
      }
      
      for (i = 0; i < NBSPAOM+NBSP; i ++)
        x[i]=x[i]/totx;

      thermob (x, ac, (NBSPAOM + NBSP));

      for (i = 1; i <= NBSP; i ++) {
        Kpart[i]=760.0*8.202e-5*temperature/(MWaom*1.0e6*VPB[i]*ac[i-1+NBSPAOM])*exp(HVAPB[i]*1000.0/8.314*(1.0/temperature-1.0/298.0));
        if (*ioligo == 1) Kpart[i]=Kpart[i]*(1.0+K0B[i]);
        gas[i]=aero[i]/(Kpart[i]*MO);
      }
    }
  else
    for (i = 1; i <= NBSP; i ++) gas[i]=0.0;

  return;
}




