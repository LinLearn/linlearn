# Authors: Stephane Gaiffas <stephane.gaiffas@gmail.com>
#          Ibrahim Merad <imerad7@gmail.com>
# License: BSD 3 clause

"""
This module implement the ``CH`` class for the Catoni-Holland robust estimator.

``StateCH`` is a place-holder for the CH estimator containing:


    gradient: numpy.ndarray
        A numpy array of shape (n_weights,) containing gradients computed by the
        `grad` function returned by the `grad_factory` factory function.

    TODO: fill the missing things in StateCH
"""

from collections import namedtuple
import numpy as np
from numba import jit
from ._base import Estimator, jit_kwargs, vectorize_kwargs
from .._utils import np_float
from numba import vectorize


@vectorize(**vectorize_kwargs)
def catoni(x):
    return np.sign(x) * np.log(1 + np.sign(x) * x + x * x / 2)
    # if x > 0 else -np.log(1 - x + x*x/2)


@vectorize(**vectorize_kwargs)
def khi(x):
    return 0.62 - 1 / (1 + x * x)  # np.log(0.5 + x*x)#


@vectorize(**vectorize_kwargs)
def gud(x):
    return 2 * np.arctan(np.exp(x)) - np.pi / 2 if x < 12 else np.pi / 2


@jit(**jit_kwargs)
def estimate_sigma(x, eps=0.001):
    sigma = 1.0
    x_mean = x.mean()
    delta = 1
    khi0 = khi(0.0)
    while delta > eps:
        tmp = sigma * np.sqrt(1 - (khi((x - x_mean) / sigma)).mean() / khi0)
        delta = np.abs(tmp - sigma)
        sigma = tmp
    return sigma


@jit(**jit_kwargs)
def holland_catoni_estimator(x, eps=0.001):
    # if the array is constant, do not try to estimate scale
    # the following condition is supposed to reproduce np.allclose() behavior
    if (np.abs(x[0] - x) <= ((1e-8) + (1e-5) * np.abs(x[0]))).all():
        return x[0]

    s = estimate_sigma(x) * np.sqrt(len(x) / np.log(1 / eps))
    m = 0.0
    diff = 1.0
    while diff > eps:
        tmp = m + s * gud((x - m) / s).mean()
        diff = np.abs(tmp - m)
        m = tmp
    return m


from scipy.optimize import brentq


def standard_catoni_estimator(x, eps=0.001):
    if (np.abs(x[0] - x) <= ((1e-8) + (1e-5) * np.abs(x[0]))).all():
        return x[0]
    s = estimate_sigma(x)
    res = brentq(lambda u: s * catoni((x - u) / s).mean(), np.min(x), np.max(x))
    return res


StateCH = namedtuple(
    "StateCH", ["deriv_samples", "deriv_samples_outer_prods", "gradient"]
)


class CH(Estimator):
    def __init__(self, X, y, loss, fit_intercept, eps=0.001):
        Estimator.__init__(self, X, y, loss, fit_intercept)
        self.eps = eps

    def get_state(self):
        return StateCH(
            deriv_samples=np.empty(self.n_samples, dtype=np_float),
            deriv_samples_outer_prods=np.empty(self.n_samples, dtype=np_float),
            gradient=np.empty(
                self.X.shape[1] + int(self.fit_intercept), dtype=np_float
            ),
        )

    def partial_deriv_factory(self):
        X = self.X
        y = self.y
        loss = self.loss
        deriv_loss = loss.deriv_factory()
        n_samples = self.n_samples
        eps = self.eps

        if self.fit_intercept:

            @jit(**jit_kwargs)
            def partial_deriv(j, inner_products, state):
                deriv_samples = state.deriv_samples
                if j == 0:
                    for i in range(n_samples):
                        deriv_samples[i] = deriv_loss(y[i], inner_products[i])
                else:
                    for i in range(n_samples):
                        deriv_samples[i] = (
                            deriv_loss(y[i], inner_products[i]) * X[i, j - 1]
                        )

                return holland_catoni_estimator(deriv_samples, eps)

            return partial_deriv
        else:

            @jit(**jit_kwargs)
            def partial_deriv(j, inner_products, state):
                deriv_samples = state.deriv_samples
                for i in range(n_samples):
                    deriv_samples[i] = deriv_loss(y[i], inner_products[i]) * X[i, j]

                return holland_catoni_estimator(deriv_samples, eps)

            return partial_deriv

    def grad_factory(self):
        X = self.X
        y = self.y
        loss = self.loss
        deriv_loss = loss.deriv_factory()
        n_samples = self.n_samples
        eps = self.eps

        if self.fit_intercept:

            @jit(**jit_kwargs)
            def grad(inner_products, state):
                deriv_samples = state.deriv_samples
                deriv_samples_outer_prods = state.deriv_samples_outer_prods
                gradient = state.gradient

                gradient.fill(0.0)
                for i in range(n_samples):
                    deriv_samples[i] = deriv_loss(y[i], inner_products[i])
                gradient[0] = holland_catoni_estimator(deriv_samples, eps)
                for j in range(X.shape[1]):
                    deriv_samples_outer_prods[:] = deriv_samples * X[:, j]
                    gradient[j + 1] = holland_catoni_estimator(
                        deriv_samples_outer_prods, eps
                    )

            return grad
        else:

            @jit(**jit_kwargs)
            def grad(inner_products, state):
                deriv_samples = state.deriv_samples
                deriv_samples_outer_prods = state.deriv_samples_outer_prods
                gradient = state.gradient

                gradient.fill(0.0)
                for i in range(n_samples):
                    deriv_samples[i] = deriv_loss(y[i], inner_products[i])
                for j in range(X.shape[1]):
                    deriv_samples_outer_prods[:] = deriv_samples * X[:, j]
                    gradient[j] = holland_catoni_estimator(
                        deriv_samples_outer_prods, eps
                    )

            return grad
