# Authors: Stephane Gaiffas <stephane.gaiffas@gmail.com>
# License: BSD 3 clause

# py.test -rA

import numpy as np
from numpy.random.mtrand import multivariate_normal
from scipy.linalg import toeplitz
from scipy.special import expit

import pytest

# from sklearn.datasets import make_moons
# from sklearn.model_selection import train_test_split
# from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.datasets import make_moons, make_circles, make_classification

# from . import parameter_test_with_min, parameter_test_with_type, approx

import numbers
from linlearn import BinaryClassifier
import pytest

from scipy.special import expit, logit

# TODO: parameter_test_with_type does nothing !!!

# TODO: va falloir furieusement tester plein de types de données d'entrée, avec labels
#  non-contigus, et avec labels strings par exemple.

# TODO: verifier que fit avec strategy="erm" amène exactement au meme coef_ et intercept_ que sklearn

# TODO: test the __repr__ (even if it's the one from sklearn


# class TestBinaryClassifierProperties(object):
def test_keyword_args_only():
    with pytest.raises(TypeError) as exc_info:
        _ = BinaryClassifier("l2")
    assert exc_info.type is TypeError
    match = "__init__() takes 1 positional argument but 2 were given"
    assert exc_info.value.args[0] == match


def test_penalty():
    clf = BinaryClassifier()
    assert clf.penalty == "l2"

    for penalty in BinaryClassifier._penalties:
        clf.penalty = penalty
        assert clf.penalty == penalty

    penalty = "stuff"
    with pytest.raises(ValueError) as exc_info:
        clf.penalty = penalty
    assert exc_info.type is ValueError
    match = "penalty must be one of %r; got (penalty=%r)" % (
        BinaryClassifier._penalties,
        penalty,
    )
    assert exc_info.value.args[0] == match

    penalty = "stuff"
    with pytest.raises(ValueError) as exc_info:
        _ = BinaryClassifier(penalty=penalty)
    assert exc_info.type is ValueError
    match = "penalty must be one of %r; got (penalty=%r)" % (
        BinaryClassifier._penalties,
        penalty,
    )
    assert exc_info.value.args[0] == match

    setattr(clf, "penalty", "l1")
    assert getattr(clf, "penalty") == "l1"


def test_C():
    clf = BinaryClassifier()
    assert isinstance(clf.C, float)
    assert clf.C == 1.0

    clf.C = 42e1
    assert isinstance(clf.C, float)
    assert clf.C == 420.0

    clf.C = 0
    assert isinstance(clf.C, float)
    assert clf.C == 0.0

    for C in [-1, complex(1.0, 1.0), "1.0"]:
        with pytest.raises(ValueError) as exc_info:
            clf.C = C
        assert exc_info.type is ValueError
        match = "C must be a positive number; got (C=%r)" % C
        assert exc_info.value.args[0] == match

    for C in [-1, complex(1.0, 1.0), "1.0"]:
        with pytest.raises(ValueError) as exc_info:
            BinaryClassifier(C=C)
        assert exc_info.type is ValueError
        match = "C must be a positive number; got (C=%r)" % C
        assert exc_info.value.args[0] == match

    setattr(clf, "C", 3.140)
    assert getattr(clf, "C") == 3.14


def test_loss():
    clf = BinaryClassifier()
    assert clf.loss == "logistic"

    for loss in BinaryClassifier._losses:
        clf.loss = loss
        assert clf.loss == loss

    loss = "stuff"
    with pytest.raises(ValueError) as exc_info:
        clf.loss = loss
    assert exc_info.type is ValueError
    match = "loss must be one of %r; got (loss=%r)" % (BinaryClassifier._losses, loss,)
    assert exc_info.value.args[0] == match

    loss = "stuff"
    with pytest.raises(ValueError) as exc_info:
        _ = BinaryClassifier(loss=loss)
    assert exc_info.type is ValueError
    match = "loss must be one of %r; got (loss=%r)" % (BinaryClassifier._losses, loss,)
    assert exc_info.value.args[0] == match

    setattr(clf, "loss", "logistic")
    assert getattr(clf, "loss") == "logistic"


def test_fit_intercept():
    clf = BinaryClassifier()
    assert isinstance(clf.fit_intercept, bool)
    assert clf.fit_intercept is True

    clf.fit_intercept = False
    assert isinstance(clf.fit_intercept, bool)
    assert clf.fit_intercept is False

    for fit_intercept in [0, 1, -1, complex(1.0, 1.0), "1.0", "true"]:
        with pytest.raises(ValueError) as exc_info:
            clf.fit_intercept = fit_intercept
        assert exc_info.type is ValueError
        match = "fit_intercept must be True or False; got (C=%r)" % fit_intercept
        assert exc_info.value.args[0] == match

    for fit_intercept in [0, 1, -1, complex(1.0, 1.0), "1.0", "true"]:
        with pytest.raises(ValueError) as exc_info:
            BinaryClassifier(fit_intercept=fit_intercept)
        assert exc_info.type is ValueError
        match = "fit_intercept must be True or False; got (C=%r)" % fit_intercept
        assert exc_info.value.args[0] == match

    setattr(clf, "fit_intercept", True)
    assert getattr(clf, "fit_intercept") is True


def test_strategy():
    clf = BinaryClassifier()
    assert clf.strategy == "erm"

    for strategy in BinaryClassifier._strategies:
        clf.strategy = strategy
        assert clf.strategy == strategy

    strategy = "stuff"
    with pytest.raises(ValueError) as exc_info:
        clf.strategy = strategy
    assert exc_info.type is ValueError
    match = "strategy must be one of %r; got (strategy=%r)" % (
        BinaryClassifier._strategies,
        strategy,
    )
    assert exc_info.value.args[0] == match

    strategy = "stuff"
    with pytest.raises(ValueError) as exc_info:
        _ = BinaryClassifier(strategy=strategy)
    assert exc_info.type is ValueError
    match = "strategy must be one of %r; got (strategy=%r)" % (
        BinaryClassifier._strategies,
        strategy,
    )
    assert exc_info.value.args[0] == match

    setattr(clf, "strategy", "mom")
    assert getattr(clf, "strategy") == "mom"


def test_solver():
    clf = BinaryClassifier()
    assert clf.solver == "cgd"

    for solver in BinaryClassifier._solvers:
        clf.solver = solver
        assert clf.solver == solver

    solver = "stuff"
    with pytest.raises(ValueError) as exc_info:
        clf.solver = solver
    assert exc_info.type is ValueError
    match = "solver must be one of %r; got (solver=%r)" % (
        BinaryClassifier._solvers,
        solver,
    )
    assert exc_info.value.args[0] == match

    solver = "stuff"
    with pytest.raises(ValueError) as exc_info:
        _ = BinaryClassifier(solver=solver)
    assert exc_info.type is ValueError
    match = "solver must be one of %r; got (solver=%r)" % (
        BinaryClassifier._solvers,
        solver,
    )
    assert exc_info.value.args[0] == match

    setattr(clf, "solver", "cgd")
    assert getattr(clf, "solver") == "cgd"


def test_tol():
    clf = BinaryClassifier()
    assert isinstance(clf.tol, float)
    assert clf.tol == 1e-4

    clf.tol = 3.14e-3
    assert isinstance(clf.tol, float)
    assert clf.tol == 3.14e-3

    for tol in [-1, 0.0, complex(1.0, 1.0), "1.0"]:
        with pytest.raises(ValueError) as exc_info:
            clf.tol = tol
        assert exc_info.type is ValueError
        match = "Tolerance for stopping criteria must be positive; got (tol=%r)" % tol
        assert exc_info.value.args[0] == match

    for tol in [-1, 0.0, complex(1.0, 1.0), "1.0"]:
        with pytest.raises(ValueError) as exc_info:
            BinaryClassifier(tol=tol)
        assert exc_info.type is ValueError
        match = "Tolerance for stopping criteria must be positive; got (tol=%r)" % tol
        assert exc_info.value.args[0] == match

    setattr(clf, "tol", 3.14)
    assert getattr(clf, "tol") == 3.14


def test_max_iter():
    clf = BinaryClassifier()
    assert isinstance(clf.max_iter, int)
    assert clf.max_iter == 100

    clf.max_iter = 42.0
    assert isinstance(clf.max_iter, int)
    assert clf.max_iter == 42

    for max_iter in [-1, 0, complex(1.0, 1.0), "1.0"]:
        with pytest.raises(ValueError) as exc_info:
            clf.max_iter = max_iter
        assert exc_info.type is ValueError
        match = (
            "Maximum number of iteration must be positive; got (max_iter=%r)" % max_iter
        )
        assert exc_info.value.args[0] == match

    for max_iter in [-1, 0.0, complex(1.0, 1.0), "1.0"]:
        with pytest.raises(ValueError) as exc_info:
            BinaryClassifier(max_iter=max_iter)
        assert exc_info.type is ValueError
        match = (
            "Maximum number of iteration must be positive; got (max_iter=%r)" % max_iter
        )
        assert exc_info.value.args[0] == match

    setattr(clf, "max_iter", 123)
    assert getattr(clf, "max_iter") == 123


def simulate_true_logistic(n_samples=150, n_features=5, fit_intercept=True, corr=0.5):
    rng = np.random.RandomState(42)
    coef0 = rng.randn(n_features)
    if fit_intercept:
        intercept0 = -2.0
    else:
        intercept0 = 0.0

    cov = toeplitz(corr ** np.arange(0, n_features))
    X = rng.multivariate_normal(np.zeros(n_features), cov, size=n_samples)
    logits = X.dot(coef0)
    logits += intercept0
    p = expit(logits)
    y = rng.binomial(1, p, size=n_samples)
    return X, y


penalties = BinaryClassifier._penalties


@pytest.mark.parametrize("fit_intercept", (False, True))
@pytest.mark.parametrize("penalty", penalties)
@pytest.mark.parametrize("C", (1e-3, 1e-2, 1e-1, 1.0, 1e1, 1e2, 1e3))
def test_fit_same_sklearn_logistic(fit_intercept, penalty, C):
    """
    This is a test that checks on many combinations that BinaryClassifier gets the
    same coef_ and intercept_ as scikit-learn on simulated data
    """
    n_samples = 128
    n_features = 5
    tol = 1e-10
    max_iter = 200
    verbose = False

    X, y = simulate_true_logistic(
        n_samples=n_samples, n_features=n_features, fit_intercept=fit_intercept,
    )

    args = {
        "penalty": penalty,
        "tol": tol,
        "max_iter": max_iter,
        "C": C,
        "verbose": verbose,
        "fit_intercept": fit_intercept,
        "random_state": 42,
    }

    def approx(v):
        return pytest.approx(v, abs=1e-7)

    # We compare with saga since it supports all penalties
    clf_scikit = LogisticRegression(solver="saga", **args).fit(X, y)
    clf_linlearn = BinaryClassifier(solver="cgd", **args).fit(X, y)

    # For some weird reason scikit's intercept_ does not match for "l1" with
    # intercept and for small C
    if not (penalty == "l1" and fit_intercept and C < 1e-1):
        assert clf_scikit.intercept_ == approx(clf_linlearn.intercept_)

    assert clf_scikit.coef_ == approx(clf_linlearn.coef_)


@pytest.mark.parametrize("fit_intercept", (False, True))
@pytest.mark.parametrize("penalty", penalties)
@pytest.mark.parametrize("C", (1e-3, 1e-2, 1e-1, 1.0, 1e1, 1e2, 1e3))
def test_fit_same_sklearn_moons(fit_intercept, penalty, C):
    """
    This is a test that checks on many combinations that BinaryClassifier gets the
    same coef_ and intercept_ as scikit-learn on simulated data
    """
    n_samples = 150
    tol = 1e-15
    max_iter = 200
    verbose = False
    random_state = 42

    X, y = make_moons(n_samples=n_samples, noise=0.2, random_state=random_state)

    args = {
        "penalty": penalty,
        "tol": tol,
        "max_iter": max_iter,
        "C": C,
        "verbose": verbose,
        "fit_intercept": fit_intercept,
        "random_state": 42,
    }

    def approx(v):
        return pytest.approx(v, abs=1e-4)

    clf_scikit = LogisticRegression(solver="saga", **args).fit(X, y)
    clf_linlearn = BinaryClassifier(solver="cgd", **args).fit(X, y)

    if not (penalty == "l1" and fit_intercept and C < 1e-1):
        assert clf_scikit.intercept_ == approx(clf_linlearn.intercept_)

    if not (penalty == "l1" and C == 1e-1 and not fit_intercept):
        assert clf_scikit.coef_ == approx(clf_linlearn.coef_)


@pytest.mark.parametrize("fit_intercept", (False, True))
@pytest.mark.parametrize("penalty", penalties)
@pytest.mark.parametrize("C", (1e-3, 1e-2, 1e-1, 1.0, 1e1, 1e2, 1e3))
def test_fit_same_sklearn_circles(fit_intercept, penalty, C):
    """
    This is a test that checks on many combinations that BinaryClassifier gets the
    same coef_ and intercept_ as scikit-learn on simulated data
    """
    n_samples = 150
    tol = 1e-15
    max_iter = 200
    verbose = False
    random_state = 42

    X, y = make_circles(n_samples=n_samples, noise=0.2, random_state=random_state)

    args = {
        "penalty": penalty,
        "tol": tol,
        "max_iter": max_iter,
        "C": C,
        "verbose": verbose,
        "fit_intercept": fit_intercept,
        "random_state": 42,
    }

    def approx(v):
        return pytest.approx(v, abs=1e-4)

    clf_scikit = LogisticRegression(solver="saga", **args).fit(X, y)
    clf_linlearn = BinaryClassifier(solver="cgd", **args).fit(X, y)

    if not (penalty == "l1" and fit_intercept and C <= 1e-1):
        assert clf_scikit.intercept_ == approx(clf_linlearn.intercept_)

    assert clf_scikit.coef_ == approx(clf_linlearn.coef_)


# TODO: test "mom" strategy works best with outlying data


# def test_predict_proba(self):
#     clf = AMFClassifier(n_classes=2)
#     with pytest.raises(
#         RuntimeError,
#         match="You must call `partial_fit` before asking for predictions",
#     ):
#         X_test = np.random.randn(2, 3)
#         clf.predict_proba(X_test)
#
#     with pytest.raises(ValueError) as exc_info:
#         X = np.random.randn(2, 2)
#         y = np.array([0.0, 1.0])
#         clf.partial_fit(X, y)
#         X_test = np.random.randn(2, 3)
#         clf.predict_proba(X_test)
#     assert exc_info.type is ValueError
#     assert exc_info.value.args[
#         0
#     ] == "`partial_fit` was called with n_features=%d while predictions are asked with n_features=%d" % (
#         clf.n_features,
#         3,
#     )
#

# TODO: test_performance_on_moons
# def test_performance_on_moons(self):
#     n_samples = 300
#     random_state = 42
#     X, y = make_moons(n_samples=n_samples, noise=0.25, random_state=random_state)
#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.5, random_state=random_state
#     )
#     clf = AMFClassifier(n_classes=2, random_state=random_state)
#     clf.partial_fit(X_train, y_train)
#     y_pred = clf.predict_proba(X_test)
#     score = roc_auc_score(y_test, y_pred[:, 1])
#     # With this random_state, the score should be exactly 0.9709821428571429
#     assert score > 0.97


#
# def test_random_state_is_consistant(self):
#     n_samples = 300
#     random_state = 42
#     X, y = make_moons(n_samples=n_samples, noise=0.25, random_state=random_state)
#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.5, random_state=random_state
#     )
#
#     clf = AMFClassifier(n_classes=2, random_state=random_state)
#     clf.partial_fit(X_train, y_train)
#     y_pred_1 = clf.predict_proba(X_test)
#
#     clf = AMFClassifier(n_classes=2, random_state=random_state)
#     clf.partial_fit(X_train, y_train)
#     y_pred_2 = clf.predict_proba(X_test)
#
#     assert y_pred_1 == approx(y_pred_2)
