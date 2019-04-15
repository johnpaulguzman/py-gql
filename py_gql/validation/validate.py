# -*- coding: utf-8 -*-

from itertools import chain
from typing import Iterator, List, Optional, Sequence, Type

from ..exc import ValidationError
from ..lang import ast as _ast
from ..lang.visitor import ParallelVisitor, visit
from ..schema import Schema
from ..utilities import TypeInfoVisitor
from . import rules as _rules
from .visitors import ValidationVisitor

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

    def __init__(self, errors: Optional[List[ValidationError]]):
        self.errors = errors if errors is not None else []

    def __bool__(self):
        return not self.errors

    def __iter__(self) -> Iterator[ValidationError]:
        return iter(self.errors)


def validate_ast(
    schema: Schema,
    ast_root: _ast.Document,
    validators: Optional[Sequence[Type[ValidationVisitor]]] = None,
) -> ValidationResult:
    """
    Check that an ast is a valid GraphQL query document by running the parse
    tree through a list of :class:`~py_gql.validation.ValidationVisitor` given a
    :class:`~py_gql.schema.Schema` instance.

    Warning:
        This assumes the ast is a valid document generated by
        :func:`py_gql.lang.parse` and will most likely break
        unexpectedly if that's not the case.

    Args:
        schema:
            Schema to validate against (for known types, directives, etc.).

        ast_root: The parse tree root.

        validators:
            List of validator classes (subclasses of
            :class:`py_gql.validation.ValidationVisitor`) to use.
            Defaults to :obj:`~py_gql.validation.SPECIFIED_RULES`.

    Returns:
        Validation result wrapping any validatione error that occured.
    """
    type_info = TypeInfoVisitor(schema)
    if validators is None:
        validators = SPECIFIED_RULES

    def instantiate_validator(cls_, schema, type_info):
        if not issubclass(cls_, ValidationVisitor):
            raise TypeError(
                'Expected ValidationVisitor subclass but got "%r"' % cls_
            )
        return cls_(schema, type_info)

    validator_instances = [
        instantiate_validator(validator_, schema, type_info)
        for validator_ in validators
    ]

    # Type info NEEDS to be first to be accurately used inside other validators
    # so when a validator enters node the type stack has already been updated.
    validator = ParallelVisitor(type_info, *validator_instances)

    visit(validator, ast_root)
    return ValidationResult(
        list(chain(*[v.errors for v in validator_instances]))
    )
