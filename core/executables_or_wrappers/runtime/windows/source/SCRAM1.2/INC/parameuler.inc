!!$ ---------------------------------------------------------
!!$ Eps_machine		: Tolerance due to the lack of 
!!$	  				precision of the machine
!!$
!!$	Eps_dbl_prec 	: Lower tolerance if the variation 
!!$	  			   	of diameter after cond/evap is too small, 
!!$ 			   	i.e. has no effect on the redistribution
!!$  
!!$ Eps_diam		: Tolerance for the diameter 
!!$  
!!$  
!!$
!!$ PI				: PI number
!!$
!!$
!!$   TINYM     threshold mass conc (µg.m-3)     
!!$   TINYN     threshold num conc (#part.m-3)   
!!$
!!$ ---------------------------------------------------------  

	double precision Eps_machine, Eps_dbl_prec, Eps_diam

	  parameter(Eps_machine = 1.d-11)
	  parameter(Eps_dbl_prec = 1D-15)
	  parameter(Eps_diam = 1.d-11)


! 	DOUBLE PRECISION PI
!      		 PARAMETER(PI = 3.14159265358979323846D0)

!!$ diam_pass est aussi defini dans paraero.inc	  
	double precision diam_pass   
	  parameter(diam_pass = 1.D-02)

!!	double precision TINYM, TINYN
!!      PARAMETER(TINYM = 1.D-20)
!!      PARAMETER(TINYN = 1.D-03) 
