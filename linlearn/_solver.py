from abc import ABC, abstractmethod
import numpy as np
from math import fabs
from numpy.random import permutation
from numba import jit
import matplotlib.pyplot as plt
from collections import namedtuple

# from .history import History
# from linlearn.model.utils import inner_prods

# from .strategy import grad_coordinate_erm, decision_function, strategy_classes
from ._estimator import decision_function
from ._loss import decision_function_factory
from ._utils import NOPYTHON, NOGIL, BOUNDSCHECK, FASTMATH, nb_float, np_float


# TODO: good default for tol when using duality gap
# TODO: step=float or {'best', 'auto'}
# TODO: random_state same thing as in scikit

OptimizationResult = namedtuple(
    "OptimizationResult", ["n_iter", "tol", "success", "w", "message"]
)


jit_kwargs = {
    "nopython": NOPYTHON,
    "nogil": NOGIL,
    "boundscheck": BOUNDSCHECK,
    "fastmath": FASTMATH,
}


# Attributes
# xndarray
# The solution of the optimization.
# successbool
# Whether or not the optimizer exited successfully.
# statusint
# Termination status of the optimizer. Its value depends on the underlying solver. Refer to message for details.
# messagestr
# Description of the cause of the termination.
# fun, jac, hess: ndarray
# Values of objective function, its Jacobian and its Hessian (if available). The Hessians may be approximations, see the documentation of the function in question.
# hess_invobject
# Inverse of the objective function’s Hessian; may be an approximation. Not available for all solvers. The type of this attribute may be either np.ndarray or scipy.sparse.linalg.LinearOperator.
# nfev, njev, nhevint
# Number of evaluations of the objective functions and of its Jacobian and Hessian.
# nitint
# Number of iterations performed by the optimizer.
# maxcvfloat
# The maximum constraint violation.

class Solver(ABC):
    def __init__(
            self,
            X,
            y,
            loss,
            fit_intercept,
            estimator,
            penalty,
            max_iter,
            tol,
            random_state,
            history,
    ):
        self.X = X
        self.y = y
        self.loss = loss
        self.fit_intercept = fit_intercept
        self.estimator = estimator
        self.penalty = penalty
        self.max_iter = max_iter
        self.tol = tol
        self.random_state = random_state
        self.n_samples, self.n_features = self.X.shape
        if self.fit_intercept:
            self.n_weights = self.n_features + 1
        else:
            self.n_weights = self.n_features

        self.history = history

    def objective_factory(self):

        value_loss = self.loss.value_batch_factory()
        value_penalty = self.penalty.value_factory()
        y = self.y
        if self.fit_intercept:

            @jit(**jit_kwargs)
            def objective(weights, inner_products):
                obj = value_loss(y, inner_products)
                obj += value_penalty(weights[1:])
                return obj

            return objective
        else:

            @jit(**jit_kwargs)
            def objective(weights, inner_products):
                obj = value_loss(y, inner_products)
                obj += value_penalty(weights)
                return obj

            return objective

    @abstractmethod
    def cycle_factory(self):
        pass

    def solve(self, w0=None):
        X = self.X
        fit_intercept = self.fit_intercept
        inner_products = np.empty(self.n_samples, dtype=np_float)
        # We use intp and not uintp since j-1 is np.float64 when j has type np.uintp
        # (namely np.uint64 on most machines), and this fails in nopython mode for
        # coverage analysis
        coordinates = np.arange(self.n_weights, dtype=np.uintp)
        weights = np.empty(self.n_weights, dtype=np_float)
        tol = self.tol
        max_iter = self.max_iter
        history = self.history
        if w0 is not None:
            weights[:] = w0
        else:
            weights.fill(0.0)

        # Computation of the initial inner products
        decision_function = decision_function_factory(X, fit_intercept)
        decision_function(weights, inner_products)

        random_state = self.random_state
        if random_state is not None:
            @jit(**jit_kwargs)
            def numba_seed_numpy(rnd_state):
                np.random.seed(rnd_state)

            numba_seed_numpy(random_state)

        # Get the cycle function
        cycle = self.cycle_factory()
        # Get the objective function
        objective = self.objective_factory()
        # Compute the first value of the objective
        obj = objective(weights, inner_products)
        # Get the estimator state (a place-holder for the estimator's internal
        # computations)
        state_estimator = self.estimator.get_state()

        # TODO: First value for tolerance is 1.0 or NaN
        history.update(epoch=0, obj=obj, tol=1.0, update_bar=True)

        for n_iter in range(1, max_iter + 1):
            max_abs_delta, max_abs_weight = cycle(
                coordinates, weights, inner_products, state_estimator
            )
            # Compute the new value of objective
            obj = objective(weights, inner_products)
            if max_abs_weight == 0.0:
                current_tol = 0.0
            else:
                current_tol = max_abs_delta / max_abs_weight

            # TODO: tester tous les cas "max_abs_weight == 0.0" etc..
            history.update(epoch=n_iter, obj=obj, tol=current_tol, update_bar=True)

            if current_tol < tol:
                history.close_bar()
                return OptimizationResult(
                    w=weights, n_iter=n_iter, success=True, tol=tol, message=None
                )

        history.close_bar()
        return OptimizationResult(
            w=weights, n_iter=max_iter + 1, success=False, tol=tol, message=None
        )


class CGD(Solver):
    def __init__(
        self,
        X,
        y,
        loss,
        fit_intercept,
        estimator,
        penalty,
        max_iter,
        tol,
        random_state,
        steps,
        history,
    ):
        super(CGD, self).__init__(
            X=X,
            y=y,
            loss=loss,
            fit_intercept=fit_intercept,
            estimator=estimator,
            penalty=penalty,
            max_iter=max_iter,
            tol=tol,
            random_state=random_state,
            history=history
        )

        # Automatic steps
        self.steps = steps

    def cycle_factory(self):

        X = self.X
        fit_intercept = self.fit_intercept
        n_samples = self.estimator.n_samples
        n_weights = self.n_weights
        partial_deriv_estimator = self.estimator.partial_deriv_factory()
        penalize = self.penalty.apply_one_unscaled_factory()
        steps = self.steps

        # The learning rates scaled by the strength of the penalization (we use the
        # apply_one_unscaled penalization function)
        scaled_steps = self.steps.copy()
        scaled_steps *= self.penalty.strength

        if fit_intercept:

            @jit(**jit_kwargs)
            def cycle(coordinates, weights, inner_products, state_estimator):
                max_abs_delta = 0.0
                max_abs_weight = 0.0
                # weights = state_cgd.weights
                # inner_products = state_cgd.inner_products
                # for idx in range(n_weights):
                #     coordinates[idx] = idx
                np.random.shuffle(coordinates)

                for j in coordinates:
                    partial_deriv_j = partial_deriv_estimator(
                        j, inner_products, state_estimator
                    )
                    if j == 0:
                        # It's the intercept, so we don't penalize
                        w_j_new = weights[j] - steps[j] * partial_deriv_j
                    else:
                        # It's not the intercept
                        w_j_new = weights[j] - steps[j] * partial_deriv_j
                        # TODO: compute the
                        w_j_new = penalize(w_j_new, scaled_steps[j])
                    # Update the inner products
                    delta_j = w_j_new - weights[j]
                    # Update the maximum update change
                    abs_delta_j = fabs(delta_j)
                    if abs_delta_j > max_abs_delta:
                        max_abs_delta = abs_delta_j
                    # Update the maximum weight
                    abs_w_j_new = fabs(w_j_new)
                    if abs_w_j_new > max_abs_weight:
                        max_abs_weight = abs_w_j_new
                    if j == 0:
                        for i in range(n_samples):
                            inner_products[i] += delta_j
                    else:
                        for i in range(n_samples):
                            inner_products[i] += delta_j * X[i, j - 1]
                    weights[j] = w_j_new

                return max_abs_delta, max_abs_weight

            return cycle

        else:
            # There is no intercept, so the code changes slightly
            @jit(**jit_kwargs)
            def cycle(coordinates, weights, inner_products, state_estimator):
                max_abs_delta = 0.0
                max_abs_weight = 0.0
                # for idx in range(n_weights):
                #     coordinates[idx] = idx
                np.random.shuffle(coordinates)

                for j in coordinates:

                    partial_deriv_j = partial_deriv_estimator(
                        j, inner_products, state_estimator
                    )
                    w_j_new = weights[j] - steps[j] * partial_deriv_j
                    w_j_new = penalize(w_j_new, scaled_steps[j])
                    # Update the inner products
                    delta_j = w_j_new - weights[j]
                    # Update the maximum update change
                    abs_delta_j = fabs(delta_j)
                    if abs_delta_j > max_abs_delta:
                        max_abs_delta = abs_delta_j
                    # Update the maximum weight
                    abs_w_j_new = fabs(w_j_new)
                    if abs_w_j_new > max_abs_weight:
                        max_abs_weight = abs_w_j_new

                    for i in range(n_samples):
                        inner_products[i] += delta_j * X[i, j]

                    weights[j] = w_j_new
                return max_abs_delta, max_abs_weight

            return cycle

class GD(Solver):
    def __init__(
            self,
            X,
            y,
            loss,
            fit_intercept,
            estimator,
            penalty,
            max_iter,
            tol,
            random_state,
            step,
            history,
    ):
        super(GD, self).__init__(
            X=X,
            y=y,
            loss=loss,
            fit_intercept=fit_intercept,
            estimator=estimator,
            penalty=penalty,
            max_iter=max_iter,
            tol=tol,
            random_state=random_state,
            history=history
        )

        # Automatic steps
        self.step = step

    def cycle_factory(self):

        X = self.X
        fit_intercept = self.fit_intercept
        n_samples = self.estimator.n_samples
        n_weights = self.n_weights
        grad_estimator = self.estimator.grad_factory()
        penalize = self.penalty.apply_one_unscaled_factory()
        step = self.step

        # The learning rates scaled by the strength of the penalization (we use the
        # apply_one_unscaled penalization function)
        scaled_step = self.penalty.strength * self.step

        if fit_intercept:

            @jit(**jit_kwargs)
            def cycle(coordinates, weights, inner_products, state_estimator):
                max_abs_delta = 0.0
                max_abs_weight = 0.0
                decision_function(X, fit_intercept, weights, inner_products)

                grad = grad_estimator(
                    inner_products, state_estimator
                )
                w_new = weights - step * grad
                for j in range(1, n_weights):
                    w_new[j] = penalize(w_new[j], scaled_step)
                for j in range(n_weights):
                    # Update the maximum update change
                    abs_delta_j = fabs(w_new[j] - weights[j])
                    if abs_delta_j > max_abs_delta:
                        max_abs_delta = abs_delta_j
                    # Update the maximum weight
                    abs_w_j_new = fabs(w_new[j])
                    if abs_w_j_new > max_abs_weight:
                        max_abs_weight = abs_w_j_new

                weights[:] = w_new

                return max_abs_delta, max_abs_weight

            return cycle

        else:
            # There is no intercept, so the code changes slightly
            @jit(**jit_kwargs)
            def cycle(coordinates, weights, inner_products, state_estimator):
                max_abs_delta = 0.0
                max_abs_weight = 0.0
                decision_function(X, fit_intercept, weights, inner_products)

                grad = grad_estimator(
                    inner_products, state_estimator
                )
                w_new = weights - step * grad
                for j in coordinates:
                    w_new[j] = penalize(w_new[j], scaled_step)
                    # Update the maximum update change
                    abs_delta_j = fabs(w_new[j] - weights[j])
                    if abs_delta_j > max_abs_delta:
                        max_abs_delta = abs_delta_j
                    # Update the maximum weight
                    abs_w_j_new = fabs(w_new[j])
                    if abs_w_j_new > max_abs_weight:
                        max_abs_weight = abs_w_j_new

                weights[:] = w_new
                return max_abs_delta, max_abs_weight

            return cycle

    # TODO: stopping criterion max(weigth difference) / max(weight) + duality gap
    # TODO: and then use
    # if w_max == 0.0 or d_w_max / w_max < d_w_tol or n_iter == max_iter - 1:
    #     # the biggest coordinate update of this iteration was smaller than
    #     # the tolerance: check the duality gap as ultimate stopping
    #     # criterion
    #
    #     # XtA = np.dot(X.T, R) - l2_reg * W.T
    #     for ii in range(n_features):
    #         for jj in range(n_tasks):
    #             XtA[ii, jj] = _dot(
    #                 n_samples, X_ptr + ii * n_samples, 1, & R[0, jj], 1
    #             ) - l2_reg * W[jj, ii]
    #
    #     # dual_norm_XtA = np.max(np.sqrt(np.sum(XtA ** 2, axis=1)))
    #     dual_norm_XtA = 0.0
    #     for ii in range(n_features):
    #         # np.sqrt(np.sum(XtA ** 2, axis=1))
    #         XtA_axis1norm = _nrm2(n_tasks, & XtA[ii, 0], 1)
    #         if XtA_axis1norm > dual_norm_XtA:
    #             dual_norm_XtA = XtA_axis1norm
    #
    #     # TODO: use squared L2 norm directly
    #     # R_norm = linalg.norm(R, ord='fro')
    #     # w_norm = linalg.norm(W, ord='fro')
    #     R_norm = _nrm2(n_samples * n_tasks, & R[0, 0], 1)
    #     w_norm = _nrm2(n_features * n_tasks, & W[0, 0], 1)
    #     if (dual_norm_XtA > l1_reg):
    #         const = l1_reg / dual_norm_XtA
    #         A_norm = R_norm * const
    #         gap = 0.5 * (R_norm ** 2 + A_norm ** 2)
    #     else:
    #         const = 1.0
    #         gap = R_norm ** 2
    #
    #     # ry_sum = np.sum(R * y)
    #     ry_sum = _dot(n_samples * n_tasks, & R[0, 0], 1, & Y[0, 0], 1)
    #
    #     # l21_norm = np.sqrt(np.sum(W ** 2, axis=0)).sum()
    #     l21_norm = 0.0
    #     for ii in range(n_features):
    #         l21_norm += _nrm2(n_tasks, & W[0, ii], 1)
    #
    #         gap += l1_reg * l21_norm - const * ry_sum + \
    #                0.5 * l2_reg * (1 + const ** 2) * (w_norm ** 2)
    #
    #         if gap < tol:
    #             # return if we reached desired tolerance
    #             break
    #     else:
    #         # for/else, runs if for doesn't end with a `break`
    #         with gil:
    #             warnings.warn("Objective did not converge. You might want to "
    #                           "increase the number of iterations. Duality "
    #                           "gap: {}, tolerance: {}".format(gap, tol),
    #                           ConvergenceWarning)

    # TODO: return more than just this... return an object that include for things than
    #  this


# Dans SAG critere d'arret :
# if status == -1:
#     break
# # check if the stopping criteria is reached
# max_change = 0.0
# max_weight = 0.0
# for idx in range(n_features * n_classes):
#     max_weight = fmax
#     {{name}}(max_weight, fabs(weights[idx]))
#     max_change = fmax
#     {{name}}(max_change,
#              fabs(weights[idx] -
#                   previous_weights[idx]))
#     previous_weights[idx] = weights[idx]
# if ((max_weight != 0 and max_change / max_weight <= tol)
#         or max_weight == 0 and max_change == 0):
#     if verbose:
#         end_time = time(NULL)
#         with gil:
#             print("convergence after %d epochs took %d seconds" %
#                   (n_iter + 1, end_time - start_time))
#     break
# elif verbose:
#     printf('Epoch %d, change: %.8f\n', n_iter + 1,
#            max_change / max_weight)


# @njit
# def gd(model, w, max_epochs, step):
#     callback = History(True)
#     obj = model.loss_batch(w)
#     callback.update(obj)
#     g = np.empty(w.shape)
#     for epoch in range(max_epochs):
#         model.grad_batch(w, out=g)
#         w[:] = w[:] - step * g
#         obj = model.loss_batch(w)
#         callback.update(obj)
#     return w

#
# # TODO: good default for tol when using duality gap
# # TODO: step=float or {'best', 'auto'}
# # TODO: random_state same thing as in scikit
# # TODO:
#
#
# @njit
# def svrg_epoch(model, prox, w, w_old, gradient_memory, step, indices):
#     # This implementation assumes dense data and a separable prox_old
#     X = model.X
#     n_samples, n_features = X.shape
#     # TODO: indices.shape[0] == model.X.shape[0] == model.y.shape[0] ???
#     for idx in range(n_samples):
#         i = indices[idx]
#         c_new = model.grad_sample_coef(i, w)
#         c_old = model.grad_sample_coef(i, w_old)
#         if model.fit_intercept:
#             # Intercept is never penalized
#             w[0] = w[0] - step * ((c_new - c_old) + gradient_memory[0])
#             for j in range(1, n_features + 1):
#                 w_j = w[j] - step * ((c_new - c_old) * X[i, j - 1] + gradient_memory[j])
#                 w[j] = prox.call_single(w_j, step)
#         else:
#             for j in range(w.shape[0]):
#                 w_j = w[j] - step * ((c_new - c_old) * X[i, j] + gradient_memory[j])
#                 w[j] = prox.call_single(w_j, step)
#     return w
#
#
# class SVRG(object):
#     def __init__(
#         self,
#         step="best",
#         rand_type="unif",
#         tol=1e-10,
#         max_iter=10,
#         verbose=True,
#         print_every=1,
#         random_state=-1,
#     ):
#         self.step = step
#         self.rand_type = rand_type
#         self.tol = tol
#         self.max_iter = max_iter
#         self.print_every = print_every
#         self.random_state = random_state
#         self.verbose = verbose
#         self.history = History("SVRG", self.max_iter, self.verbose)
#
#     def set(self, model, prox):
#         self.model = model
#         self.prox = prox
#         return self
#
#     # def loss_batch(self, w):
#     #     return loss_batch(self.features, self.labels, self.loss, w)
#     #
#     # def grad_batch(self, w, out):
#     #     grad_batch(self.features, self.labels, self.loss, w, out=out)
#
#     def solve(self, w):
#         # TODO: check that set as been called
#         # TODO: save gradient_memory, so that we can continue training later
#
#         gradient_memory = np.empty(w.shape)
#         w_old = np.empty(w.shape)
#
#         model = self.model.no_python
#         prox = self.prox.no_python
#
#         n_samples = model.n_samples
#         obj = model.loss_batch(w) + prox.value(w)
#
#         history = self.history
#         # features = self.features
#         # labels = self.labels
#         # loss = self.loss
#         step = self.step
#
#         history.update(epoch=0, obj=obj, step=step, tol=0.0, update_bar=False)
#
#         for epoch in range(1, self.max_iter + 1):
#             # At the beginning of each epoch we compute the full gradient
#             # TODO: veriifer que c'est bien le cas... qu'il ne faut pas le
#             #  faire a la fin de l'epoque
#             w_old[:] = w
#
#             # Compute the full gradient
#             model.grad_batch(w, gradient_memory)
#             # grad_batch(self.features, self.labels, self.loss, w, out=gradient_memory)
#
#             # TODO: en fonction de rand_type...
#             indices = np.random.randint(n_samples, size=n_samples)
#
#             # Launch the epoch pass
#             svrg_epoch(model, prox, w, w_old, gradient_memory, step, indices)
#
#             obj = model.loss_batch(w) + prox.value(w)
#             history.update(epoch=epoch, obj=obj, step=step, tol=0.0, update_bar=True)
#
#         history.close_bar()
#         return w


# License: BSD 3 clause
from collections import defaultdict

import warnings


# We want to import the tqdm.autonotebook but don't want to see the warning...
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from tqdm.autonotebook import trange


class History(object):
    """

    """

    def __init__(self, title, max_iter, verbose):
        self.max_iter = max_iter
        self.verbose = verbose
        self.keys = None
        self.values = defaultdict(list)
        self.title = title
        self.n_updates = 0
        # TODO: List all possible keys
        print_style = defaultdict(lambda: "%.2e")
        print_style.update(
            **{
                "n_iter": "%d",
                "epoch": "%d",
                'n_inner_prod"': "%d",
                "spars": "%d",
                "rank": "%d",
                "tol": "%.2e",
            }
        )
        self.print_style = print_style

        # The progress bar using tqdm
        if self.verbose:
            bar_format = (
                "{desc} : {percentage:2.0f}% {bar} epoch: {n_fmt} "
                "/ {total_fmt} , elapsed: {elapsed_s:3.1f}s {postfix}"
            )
            self.bar = trange(
                max_iter, desc=title, unit=" epoch ", leave=True, bar_format=bar_format
            )
        else:
            self.bar = None

    def update(self, update_bar=True, **kwargs):
        # Total number of calls to update must be smaller than max_iter + 1
        if self.max_iter >= self.n_updates:
            self.n_updates += 1
        else:
            raise ValueError(
                "Already %d updates while max_iter=%d" % (self.n_updates, self.max_iter)
            )

        # The first time update is called it establishes the list of keys to be
        # given to the history. Following calls to update must provide the
        # exact same keys
        if self.keys is None:
            # OK since order is preserved in kwargs since Python 3.6
            self.keys = list(kwargs.keys())
        else:
            k1, k2 = set(self.keys), set(kwargs.keys())
            if k1 != k2:
                raise ValueError(
                    "'update' excepted the following keys: %s "
                    "must received %s instead" % (k1, k2)
                )

        values = self.values
        print_style = self.print_style

        # Update the history
        for key, val in kwargs.items():
            values[key].append(val)

        # If required, update the tqdm bar
        if self.verbose and update_bar:
            postfix = " , ".join(
                [
                    key + ": " + str(print_style[key] % val)
                    for key, val in kwargs.items()
                ]
            )
            self.bar.set_postfix_str(postfix)
            self.bar.update(1)

    def close_bar(self):
        if self.bar is not None:
            self.bar.close()

    def clear(self):
        """Reset history values"""
        self.values = defaultdict(list)
        self.keys = None
        self.n_updates = 0

    def print(self):
        keys = self.keys
        values = self.values
        print("keys: ", keys)
        min_width = 9
        line = " | ".join([key.center(min_width) for key in keys])
        names = [key.center(min_width) for key in keys]

        col_widths = list(map(len, names))
        print(line)

        print_style = self.print_style
        n_lines = len(list(values.values())[0])
        for i_line in range(n_lines):
            line = " | ".join(
                [
                    str(print_style[key] % values[key][i_line]).rjust(col_widths[i])
                    for i, key in enumerate(keys)
                ]
            )
            print(line)


# Matplotlib colors of tab cmap (previously called Vega)
# It has been re-ordered so that light colors apperas at the end
tab20_colors = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    "#aec7e8",
    "#ffbb78",
    "#98df8a",
    "#ff9896",
    "#c5b0d5",
    "#c49c94",
    "#f7b6d2",
    "#c7c7c7",
    "#dbdb8d",
    "#9edae5",
]


def get_plot_color(number):
    """Return color for a line number.
    Color are extracted from tab20 colormap which is an extension of
    matplotlib 2.x CN colors. 20 colors are available.

    Parameters
    ----------
    number : `int`
        Number of the color to pick

    Returns
    -------
    color : `str`
        Color in hexadecimal format
    """
    return tab20_colors[number % len(tab20_colors)]


# TODO: use n_iter instead or pass, epoch or whatnot


def extract_history(solvers, x, y, given_labels):
    x_arrays = []
    y_arrays = []
    labels = []
    for i, solver in enumerate(solvers):
        if hasattr(solver, "history_"):
            history = solver.history_
            if not isinstance(history, History):
                raise ValueError("Not an history !")
        else:
            raise ValueError("Object %s has no history" % solver.__class__.__name__)

        # If label was not given we override it
        if given_labels is not None and i < len(given_labels):
            # Better test
            label = given_labels[i]
        else:
            label = solver.__class__.__name__

        if x not in history.values.keys():
            raise ValueError("%s has no history for %s" % (label, x))
        elif y not in history.values.keys():
            raise ValueError("%s has no history for %s" % (label, y))
        else:
            x_arrays.append(np.array(history.values[x]))
            y_arrays.append(np.array(history.values[y]))
            labels.append(label)
    return x_arrays, y_arrays, labels


# TODO: defaults for x and


def plot_history(
    solvers,
    x,
    y,
    labels=None,
    show=True,
    log_scale: bool = False,
    dist_min: bool = False,
    rendering: str = "matplotlib",
    ax=None,
):
    """Plot the history of convergence of learners or solvers.

    It is used to compare easily their convergence performance.

    Parameters
    ----------
    solvers : `list` of `object`
        A list of solvers or learners with an history attribute to plot

    x : `str`
        The element of history to use as x-axis

    y : `str`, default='obj'
        The element of history to use as y-axis

    labels : `list` of `str`, default=None
        Label of each solver_old in the legend. If set to None then the class
        name of each solver_old will be used.

    show : `bool`, default=`True`
        if `True`, show the plot. Otherwise an explicit call to the show
        function is necessary. Useful when superposing several plots.

    log_scale : `bool`, default=`False`
        If `True`, then y-axis is on a log-scale

    dist_min : `bool`, default=`False`
        If `True`, plot the difference between `y` of each solver_old and the
        minimal `y` of all solvers. This is useful when comparing solvers on
        a logarithmic scale, to illustrate linear convergence of algorithms

    rendering : {'matplotlib', 'bokeh'}, default='matplotlib'
        Rendering library. 'bokeh' might fail if the module is not installed.

    ax : `list` of `matplotlib.axes`, default=None
        If not None, the figure will be plot on this axis and show will be
        set to False. Used only with matplotlib
    """
    x_arrays, y_arrays, labels = extract_history(solvers, x, y, labels)

    if dist_min:
        min_y = np.min(np.hstack(y_arrays))
        y_arrays = [y_array - min_y for y_array in y_arrays]

    min_x, max_x = np.min(np.hstack(x_arrays)), np.max(np.hstack(x_arrays))
    min_y, max_y = np.min(np.hstack(y_arrays)), np.max(np.hstack(y_arrays))

    # We want to ensure theses plots starts at 0
    if x in ["time", "n_iter"]:
        min_x = 0

    if rendering == "matplotlib":
        if ax is None:
            _, ax = plt.subplots(1, 1, figsize=(8, 4))
        else:
            show = False

        for i, (solver, x_array, y_array, label) in enumerate(
            zip(solvers, x_arrays, y_arrays, labels)
        ):
            color = get_plot_color(i)
            ax.plot(x_array, y_array, lw=3, label=label, color=color)

        if log_scale:
            ax.set_yscale("log")

        ax.set_xlabel(x, fontsize=16)
        ax.set_ylabel(y, fontsize=16)
        ax.set_xlim([min_x, max_x])
        ax.set_ylim([min_y, max_y])
        ax.tick_params(axis="both", which="major", labelsize=12)
        ax.legend()

        if show is True:
            plt.show()

        return ax.figure

    elif rendering == "bokeh":
        mins = (min_x, max_x, min_y, max_y)
        return plot_bokeh_history(
            solvers, x, y, x_arrays, y_arrays, mins, labels, log_scale, show
        )

    else:
        raise ValueError(
            "Unknown rendering type. Expected 'matplotlib' or "
            "'bokeh', received %s" % rendering
        )


def plot_bokeh_history(
    solvers, x, y, x_arrays, y_arrays, mins, legends, log_scale, show
):
    import bokeh.plotting as bk

    min_x, max_x, min_y, max_y = mins
    if log_scale:
        # Bokeh has a weird behaviour when using logscale with 0 entries...
        # We use the difference between smallest value of second small
        # to set the range of y
        all_ys = np.hstack(y_arrays)
        y_range_min = np.min(all_ys[all_ys != 0])
        if y_range_min < 0:
            raise ValueError("Cannot plot negative values on a log scale")

        fig = bk.Figure(
            plot_height=300, y_axis_type="log", y_range=[y_range_min, max_y]
        )
    else:
        fig = bk.Figure(plot_height=300, x_range=[min_x, max_x], y_range=[min_y, max_y])

    for i, (solver, x_array, y_array, legend) in enumerate(
        zip(solvers, x_arrays, y_arrays, legends)
    ):
        color = get_plot_color(i)
        fig.line(x_array, y_array, line_width=3, legend=legend, color=color)
    fig.xaxis.axis_label = x
    fig.yaxis.axis_label = y
    fig.xaxis.axis_label_text_font_size = "12pt"
    fig.yaxis.axis_label_text_font_size = "12pt"
    if show:
        bk.show(fig)
        return None
    else:
        return fig
