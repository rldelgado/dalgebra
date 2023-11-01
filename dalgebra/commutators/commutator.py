r'''    
    Computing non-trivial centralizers.

    This module contains the main functionality used for computng non-trivial centralizers of linear differential operators.

    This software has been used in the presentation in ISSAC'23 "Computing almost-commuting basis of Ordinary Differential
    Operators", by A. Jiménez-Pastor, S.L. Rueda and M.A. Zurro in Tromsø, Norway.

    
    **Theory explanation**
    -----------------------------------------

    Let us consider an algebraically closed field of characteristic zero `C` and the field of d-polynomials defined by `n-2` 
    differential variables `u_2,\ldots,u_{n}`. Let us consider the linear differential operator:


    .. MATH::

        L = \partial^n + u_{2}\partial^{n-2}  + \ldots + u_{n-1}\partial + u_n.

    This operator `L` can be written in terms of d-polynomials in the ring `K\{z\} = C\{u_2,\ldots,u_{n},z\}`. We say that 
    another operator `P \in K\{z\}` *commutes with `L`* if and only if the commutator of `L` with `P` (`[L,P]`) is zero. 
    
    In the ring of differential polynomials `K\{z\}`, every operator commutes since we are considering the multilpication
    as usual polynomials. However, if we consider the elements of `K\{z\}` as operators in `z`, we can see them acting via
    substitution in any differential extension of `K`. This action defines a new product operation in `K\{z\}`:

    .. MATH::

        A(z) \cdot B(z) = A(B(z))

    Since `z` is a differential variable, we can see that this multiplication is `C`-linear, which allows to define an 
    alternative `C`-algebra structure over `K\{z\}`. This `C`-algebra will be non-commutative, making sense to consider the
    commutator `[A,B] = A\cdot B - B\cdot A` and the concept of centralizer 
    
    .. MATH::
    
        \mathcal{C}(A) = \left\{B(z) \in K\{z\}\ :\ [A,B] = 0\right\}.

    This module provides methods to study the commutator of differential operators. As this is a difficult problem, we consider 
    operators in normal form. These operators are specializations of the operators `L` shown above. Hence, we can apply
    the theory of almost-commuting operators to guide in this search.

    For more information about *almost-commuting* operators and how to compute them, we refer to :mod:`almost_commuting`.

    **Examples of usage**
    -----------------------------------------
    
    TODO: Add examples of usage of the module that will serve as tests

    **Things remaining TODO**
    -----------------------------------------

    1. Fill the Examples on the documentation
    
    **Elements provided by the module**
    -----------------------------------------
'''
from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

from functools import reduce
from sage.all import diff, ideal, parent, QQ, ZZ
from sage.categories.pushout import pushout
from sage.rings.ideal import Ideal_generic as Ideal
from sage.rings.polynomial.polynomial_ring_constructor import PolynomialRing
from sage.rings.polynomial.polynomial_element_generic import Polynomial
from typing import Callable

from ..dring import DRings, DifferentialRing, DFractionField
from ..dpolynomial.dpolynomial_element import DPolynomial
from ..logging.logging import loglevel
from .almost_commuting import generic_normal, almost_commuting_wilson

_DRings = DRings.__classcall__(DRings)

#################################################################################################
###
### METHODS TO OBTAIN EQUATIONS FROM TEMPLATES
###
#################################################################################################
@loglevel(logger)
def GetEquationsForSolution(m : int, 
        L: DPolynomial = None, n: int = None, U: list | dict = None, *, 
        extract: Callable[[Polynomial], list[Polynomial]], 
        flag_name: str = "c", name_partial: str = "z") -> tuple[DPolynomial, DPolynomial, Ideal]:
    r'''
        Method to get the equations for a specific type of solutions for non-trivial commutator.

        This method computes the set of algebraic equations that need to be solved for obtaining 
        a non-trivial commutator for a given linear differential operator in normal form. Recall that
        an operator in normal form is of the form

        .. MATH::

            L = \partial^n + a_{n-2} \partial^{n-2} + \ldots + a_1 \partial + a_0,

        where `a_*` are differential elements in some **differential field**. Its generic version
        is studied by Wilson and we can compute its basis of almost commuting operators (see method
        :func:`.almost_commuting.almost_commuting_wilson`)

        This method uses the almost commuting basis to create a linear combination of its elements
        up to a fixed order (given by `m`) and then compute all the algebraic equations that need to
        be satisfied for obtaining a non-trivial element of the centralizer of `L`.

        Since the way the algebraic equations arises from the almost commuting basis and the operator 
        `L` depends on the differential field over which `L` is defined, we require a method
        ``extract`` that can obtain, for a given element in the differential field, a list of 
        equations that guarantee the element to vanish.

        INPUT:

        * ``m``: order bound for the commutator to be found.
        * ``L``: linear differential operator in normal form to be used as base operator.
        * ``n``: if `L` is not given directly, `n` provides the order of the operator `L` to be used.
          Then, the coefficients are given in the input ``U``, either as a list or as a dictionary.
        * ``extract``: a method to extract from the final set of values the equations for 
          the obtained operator to actually commute. These equations will include any variable 
          within the given functions ``U`` and the flag of constants created.
        * ``flag_name``: name use for the variables used in the flag of constants.

        OUTPUT:

        A pair `(P, H)` where `P` is an operator of order at most `m` such that it **commutes** with `L_n` (see method 
        :func:`generic_normal`) for the given set of ``U`` whenever the equations in `H` all vanish. The equations
        on `H` are only *algebraic* equations.
    '''
    ## If the operator `L` is given, we transform it into the inputs `U` and `n`
    if L != None:
        ## Checking we do not collide in arguments
        if U != None or n != None: raise ValueError(f"[GEFS] Too many arguments given. `L` provided together with `U` and `n`.")
        z = L.parent().gen(name_partial)
        if not L.is_linear(z): raise TypeError(f"[GEFS] The base operator is not linear.")
        elif not L.is_normal_form(z): raise TypeError(f"[GEFS] The base operator is not in normal form")
        n = L.order(z)
        U = [L.parent().base()(L.coefficient(z[i])) for i in range(n-1)]
    elif U == None or n == None:
        raise ValueError(f"[GEFS] Too few arguments given. Either `L` or (`U`,`n`) must be provided")
    
    ## Checking correctness of arguments
    if not n in ZZ or n < 2: raise ValueError(f"[GEFS] The value for `n` must be a integer greater than 1")
    if not m in ZZ or m < n: raise ValueError(f"[GEFS] The value for `m` must be a integer greater than `n`")
    if isinstance(U, (list,tuple)):
        if len(U) != n-1: raise ValueError(f"[GEFS] The size of the given functions ``U`` must be of length `n-1` ({n-1})")
        U = {i: U[i] for i in range(len(U))}
    elif not isinstance(U, dict):
        raise TypeError(f"[GEFS] The argument ``U`` must be a list or a dictionary")
    elif any(el not in ZZ for el in U.keys()) or min(U.keys()) < 0 or max(U.keys()) > n-2:
        raise KeyError(f"[GEFS] The argument ``U`` as dictionary must have integers as keys between 0 and `n-2` ({n-2})")
    
    if not callable(extract): raise TypeError(f"[GEFS] The argument ``extract`` must be a callable.")

    ## Analyzing the functions in ``U``
    logger.debug(f"[GEFS] Computing common parent for the ansatz functions")
    parent_us = reduce(lambda p, q: pushout(p,q), (parent(v) for v in U.values()))
    if not parent_us in _DRings:
        raise TypeError(f"[GEFS] We need the coefficient of `L` to be in a differential ring/field")
    
    ### Computing the generic `L` operator
    logger.debug(f"[GEFS] Computing the generic L_{n} operator...")
    L = generic_normal(n, name_partial=name_partial); z = L.parent().gen(name_partial)
    logger.debug(f"[GEFS] {L=}")

    ## Adding the appropriate number of flag constants
    logger.debug(f"[GEFS] Creating the ring for having the flag of constants...")
    C = [f"{flag_name}_{i}" for i in range(m+1)]
    diff_base = parent_us.add_constants(*C)
        
    logger.debug(f"[GEFS] Ring with flag-constants: {diff_base=}")
    u = [L.coefficient(z[i]).change_ring(diff_base) for i in range(n-1)]
    L = L.change_ring(diff_base)
    u = [L.parent().gen(el.infinite_variables()[0].variable_name()) for el in u]
    C = [diff_base(C[i]) for i in range(len(C))]
    print(u)
    U = {u[i]: diff_base(U.get(i, 0)) for i in range(n-1)}

    ### Computing the almost commuting basis up to order `m` and the hierarchy up to this point
    logger.debug(f"[GEFS] ++ Computing the basis of almost commuting and the hierarchies...")
    Ps = [L.parent().one()]; Hs = [(n-1)*[L.parent().zero()]]
    for i in range(1, m+1):
        ## TODO: should we remove the i with m%n = 0?
        nP, nH = almost_commuting_wilson(n, i, name_z=name_partial)
        Ps.append(nP.change_ring(diff_base)); Hs.append([h.change_ring(diff_base) for h in nH])
        logger.debug(f"[GEFS]    Computed for order {i}")
    
    logger.debug(f"[GEFS] -- Computed the basis of almost commuting and the hierarchies")
    
    logger.debug(f"[GEFS] Computing the guessed commutator...")
    P = sum(c*p(dic=U) for (c,p) in zip(C, Ps)) # this is the evaluated operator that will commute
    logger.debug(f"[GEFS] Computing the commuting equations...")
    H = [sum(C[i]*Hs[i][j](dic=U) for i in range(len(C))) for j in range(n-1)] # the equations that need to be 0
    logger.debug(f"[GEFS] Extracting the algebraic equation from the commuting equations...")
    H = sum([extract(h.numerator()) for h in H], []) # extract the true equations from 

    return L(dic=U), P, ideal(H)

@loglevel(logger)
def PolynomialCommutator(n: int, m: int, d: int) -> tuple[DPolynomial, DPolynomial, Ideal]:
    logger.debug(f"[PolyComm] Computing equations for polynomial commutators for L_{n} up to order {m} and degree {d}.")
    logger.debug(f"[PolyComm] --- Generating the ansatz polynomials...")
    U = generate_polynomial_ansatz(QQ, n, d)
    logger.debug(f"[PolyComm] --- Generated the ansatz functions:\n\t{U=}")
    logger.debug(f"[PolyComm] --- Computing the equations necessary for the ansatz to commute with L_{n}...")
    L, P, H = GetEquationsForSolution(m, n=n, U=U, extract=generate_polynomial_equations)
    return L,P,H 
#################################################################################################
###
### METHODS TO GENERATE TEMPLATES
###
#################################################################################################
def generate_polynomial_ansatz(base, n: int, d: int, var_name: str = "x", ansatz_var: str = "b") -> list[DPolynomial]:
    r'''
        Generate a list of ansatz for the generic `u` for a generic Schrödinger operator of order `n`

        INPUT:

        * ``base``: the base ring of constants to be used.
        * ``n``: the order of the Schrödinger operator to be considered.
        * ``d``: degree of the ansatz generated
        * ``var_name``: name of the variable to be used as a polynomial element. We will make its derivative to be `1`.
    '''
    logger.debug(f"[GenPolyAn] Generating the variables for the constant coefficients and the polynomial variable")
    var_names = [f"{ansatz_var}_{i}_{j}" for i in range(n-1) for j in range(d+1)] + [var_name] 
    logger.debug(f"[GenPolyAn] Creating the differential ring for the ansatz...")
    base = PolynomialRing(base, var_names)
    base_diff = DifferentialRing(base, lambda p : diff(p, base(var_name)))
    logger.debug(f"[GenPolyAn] {base_diff=}")

    logger.debug(f"[GenPolyAn] Creating the list of functions that will act as U's...")
    B = [[base_diff(f"{ansatz_var}_{i}_{j}") for j in range(d+1)] for i in range(n-1)]
    X = [base_diff(var_name)**j for j in range(d+1)]
    
    logger.debug(f"[GenPolyAn] Returning the ansatz functions")
    return [sum(b*x for (b,x) in zip(row, X)) for row in B]

#################################################################################################
###
### METHODS TO EXTRACT EQUATIONS
###
#################################################################################################
def generate_polynomial_equations(H: DPolynomial, var_name: str = "x") -> list[Polynomial]:
    r'''Method to extract equations assuming a polynomial ansatz'''
    logger.debug(f"[GenPolyEqus] Getting equations (w.r.t. {var_name}) from: H={repr(H)[:20]}...")
    B = H.parent().base()
    # We remove the diff. variable and the diff. structure remaining only the ansatz variables and the polynomial variable
    H = H.coefficients()[0].numerator().wrapped if isinstance(B, DFractionField) else H.coefficients()[0].wrapped
    B = parent(H) # this is the algebraic structure

    if B.is_field() and B != QQ: # field of fractions of polynomials
        x = B.base()(var_name) # this is the polynomial variable that will be removed
        output = list(H.numerator().polynomial(x).coefficients())
    else:
        x = B(var_name) # this is the polynomial variable that will be removed
        output = list(H.polynomial(x).coefficients())
    return output

__all__ = [
    "GetEquationsForSolution", "PolynomialCommutator",
    "generate_polynomial_ansatz",
    "generate_polynomial_equations"
]