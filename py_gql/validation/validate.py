# -*- coding: utf-8 -*-

from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Type,
)

from ..exc import ValidationError
from ..lang import ast as _ast
from ..lang.visitor import ParallelVisitor
from ..schema import Schema
from ..utilities import TypeInfoVisitor
from . import rules as _rules
from .visitors import ValidationVisitor

Validator = Callable[
    [Schema, _ast.Document, Optional[Dict[str, Any]]], Iterable[ValidationError]
]

SPECIFIED_RULES = (
    _rules.ExecutableDefinitionsChecker,
    _rules.UniqueOperationNameChecker,
    _rules.LoneAnonymousOperationChecker,
    _rules.SingleFieldSubscriptionsChecker,
    _rules.KnownTypeNamesChecker,
    _rules.FragmentsOnCompositeTypesChecker,
    _rules.VariablesAreInputTypesChecker,
    _rules.ScalarLeafsChecker,
    _rules.FieldsOnCorrectTypeChecker,
    _rules.UniqueFragmentNamesChecker,
    _rules.KnownFragmentNamesChecker,
    _rules.NoUnusedFragmentsChecker,
    _rules.PossibleFragmentSpreadsChecker,
    _rules.NoFragmentCyclesChecker,
    _rules.UniqueVariableNamesChecker,
    _rules.NoUndefinedVariablesChecker,
    _rules.NoUnusedVariablesChecker,
    _rules.KnownDirectivesChecker,
    _rules.UniqueDirectivesPerLocationChecker,
    _rules.KnownArgumentNamesChecker,
    _rules.UniqueArgumentNamesChecker,
    _rules.ValuesOfCorrectTypeChecker,
    _rules.ProvidedRequiredArgumentsChecker,
    _rules.VariablesInAllowedPositionChecker,
    _rules.OverlappingFieldsCanBeMergedChecker,
    _rules.UniqueInputFieldNamesChecker,
)


class ValidationResult:
    """
    Encode validation result by wrapping a collection of
    :class:`~py_gql.exc.ValidationError`. Instances are iterable and falsy
    when they contain at least one error.
    """

    def __init__(self, errors: Optional[List[ValidationError]] = None):
        self.errors = errors if errors is not None else []

    def __bool__(self):
        return not self.errors

    def __iter__(self) -> Iterator[ValidationError]:
        return iter(self.errors)


def default_validator(
    schema: Schema,
    document: _ast.Document,
    variables: Optional[Dict[str, Any]] = None,
    *,
    validators: Sequence[Type[ValidationVisitor]] = SPECIFIED_RULES,
) -> Iterable[ValidationError]:
    """Default validator implementation.

    This uses a chain of :class:`~py_gql.validation.ValidationVisitor` classes
    and collect all errors by passing the document through all visitors in order.
    This is helpful as visitors can rely on previous visitors having filtered out
    invalid nodes.

    In order to use this with :func:`~py_gql.validation.validate_ast` and custom
    visitor classes a lambda or partial should be created.
    """

    type_info = TypeInfoVisitor(schema)

    visitors = [cls(schema, type_info) for cls in validators]

    # Type info NEEDS to be first to be accurately used inside other validators
    # so when a validator enters node the type stack has already been updated.
    validator = ParallelVisitor(type_info, *visitors)
    validator.visit(document)

    return [error for visitor in visitors for error in visitor.errors]


def validate_ast(
    schema: Schema,
    document: _ast.Document,
    *,
    validators: Optional[Sequence[Validator]] = None,
    variables: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """
    Check that an ast is a valid GraphQL query document by running the parse
    tree through a list of :class:`~py_gql.validation.ValidationVisitor` given a
    :class:`~py_gql.schema.Schema` instance.

    Warning:
        This assumes the ast is a document generated by :func:`py_gql.lang.parse`
        (as opposed to manually constructed) and will most likely break
        unexpectedly if that's not the case.

    Args:
        schema:
            Schema to validate against (for known types, directives, etc.).

        document: The parse tree root.

        validators:
            List of validator callables to use. Defaults to the rules defined in
            the specificaton.

    Returns:
        Validation result wrapping any validatione error that occured.
    """
    if validators is None:
        validators = [default_validator]

    return ValidationResult(
        [
            error
            for validator in validators
            for error in validator(schema, document, variables)
        ]
    )
