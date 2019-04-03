# -*- coding: utf-8 -*-
"""
Utilitiy classes to define custom types.
"""

from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from .._utils import Lazy, lazy
from ..exc import ScalarParsingError, ScalarSerializationError, UnknownEnumValue
from ..lang import ast as _ast
from ..lang.parser import DIRECTIVE_LOCATIONS

# TODO: Encode as much of the rules for validate_schema in the type system

# TODO: Multiple objects expose both a X and X_map method which could be
# staandardised under either of these.

T = TypeVar("T")
OT = TypeVar("OT", bound="ObjectType")

_UNSET = object()

# Use this to allow providing input as a list, tuple or dict of entries.
LazyIter = Lazy[Union[Sequence[Lazy[T]], Sequence[T]]]


def _evaluate_lazy_iter(entries: Optional[LazyIter[T]]) -> List[T]:
    _entries = lazy(entries)
    if not _entries:
        return []
    elif isinstance(_entries, (list, tuple)):
        return [lazy(entry) for entry in _entries]
    raise TypeError("Expected list or dict of items")


class GraphQLType:
    """
    Base type class.

    All types used in a :class:`py_gql.schema.Schema` should be instances of
    this class.
    """

    def __eq__(self, lhs: Any) -> bool:
        return self is lhs or (
            isinstance(self, (ListType, NonNullType))
            and self.__class__ == lhs.__class__
            and self.type == lhs.type
        )

    def __hash__(self) -> int:
        return id(self)


class NamedType(GraphQLType):
    """
    Named type base class.

    Warning:
        Named types must be unique across a single :class:`~py_gql.schema.Schema`
        instance.

    Attributes:
        name (str): Type name.
    """

    name = NotImplemented  # type: str

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return "%s(%s at %d)" % (self.__class__.__name__, self.name, id(self))


class NonNullType(GraphQLType):
    """
    Non nullable wrapping type.

    A non-null type is a wrapping type which points to another type.

    Non-null types enforce that their values are never null and can ensure
    an error is raised if this ever occurs during a request. It is useful for
    fields which you can make a strong guarantee on non-nullability, for example
    usually the id field of a database row will never be null.

    Args:
        type_: Wrapped type
        node: Source node used when building type from the SDL

    Attributes:
        type (GraphQLType): Wrapped type
        node (Optional[py_gql.lang.ast.NonNullType]):
            Source node used when building type from the SDL

    """

    __slots__ = ("node", "_ltype", "_type")

    def __init__(
        self, type_: Lazy[GraphQLType], node: Optional[_ast.NonNullType] = None
    ):
        assert not isinstance(type_, NonNullType)
        self._ltype = type_
        self._type = None  # type: Optional[GraphQLType]
        self.node = node

    def __str__(self) -> str:
        return "%s!" % self.type

    @property
    def type(self) -> GraphQLType:
        if self._type is None:
            self._type = lazy(self._ltype)
        return self._type

    @type.setter
    def type(self, type_: GraphQLType) -> None:
        self._type = self._ltype = type_


class ListType(GraphQLType):
    """
    List wrapping type.

    A list type is a wrapping type which points to another type.

    Lists are often created within the context of defining the fields of
    an object type.

    Args:
        type_: Wrapped type
        node: Source node used when building type from the SDL

    Attributes:
        type (GraphQLType): Wrapped type
        node (Optional[py_gql.lang.ast.ListType]):
            Source node used when building type from the SDL
    """

    __slots__ = ("node", "_ltype", "_type")

    def __init__(
        self, type_: Lazy[GraphQLType], node: Optional[_ast.ListType] = None
    ):
        self._ltype = type_
        self._type = None  # type: Optional[GraphQLType]
        self.node = node

    def __str__(self):
        return "[%s]" % self.type

    @property
    def type(self) -> GraphQLType:
        if self._type is None:
            self._type = lazy(self._ltype)
        return self._type

    @type.setter
    def type(self, type_: GraphQLType) -> None:
        self._type = self._ltype = type_


class InputField:
    """
    Member of an :class:`py_gql.schema.InputObjectType`.

    Warning:
        As ``None`` is a valid default value, in order to define an argument
        without any default value, the ``default_value`` argument **must** be
        omitted.

    Args:
        name: Field name

        type_: Field type (must be input type)

        default_value: Default value

        description: Field description

        node: Source node used when building type from the SDL

    Attributes:
        name (str): Field name

        description (Optional[str]): Field description

        has_default_value (bool): ``True`` if default value is set

        default_value (Any):
            Default value if it was set. Accessing this attribute raises an
            :py:class:`AttributeError` if default value wasn't set.

        type (GraphQLType): Vaue type.

        required (bool):
            Whether this field is required (non nullable and does not have
            any default value)

        node (Optional[py_gql.lang.ast.InputValueDefinition]):
            Source node used when building type from the SDL
    """

    def __init__(
        self,
        name: str,
        type_: Lazy[GraphQLType],
        default_value: Any = _UNSET,
        description: Optional[str] = None,
        node: Optional[_ast.InputValueDefinition] = None,
    ):
        self.name = name
        self.description = description
        self.has_default_value = default_value is not _UNSET
        self.node = node

        self._default_value = default_value
        self._ltype = type_
        self._type = None  # type: Optional[GraphQLType]

    @property
    def default_value(self) -> Any:
        if self._default_value is _UNSET:
            raise AttributeError("No default value")
        return self._default_value

    @default_value.setter
    def default_value(self, value: Any) -> None:
        self._default_value = value

    @default_value.deleter
    def default_value(self) -> None:
        self._default_value = _UNSET

    @property
    def type(self) -> GraphQLType:
        if self._type is None:
            self._type = lazy(self._ltype)
        return self._type

    @type.setter
    def type(self, type_: GraphQLType) -> None:
        self._type = self._ltype = type_

    @property
    def required(self) -> bool:
        return (
            isinstance(self.type, NonNullType) and self._default_value is _UNSET
        )

    def __str__(self) -> str:
        return "InputField(%s: %s)" % (self.name, self.type)

    def __repr__(self) -> str:
        return "InputField(%s: %s at %d)" % (self.name, self.type, id(self))


class InputObjectType(NamedType):
    """
    Input Object Type Definition

    An input object defines a structured collection of fields which can be
    supplied as a field or directive argument.

    Args:
        name: Type name

        fields: Fields

        description: Type description

        nodes: Source nodes used when building type from the SDL

    Attributes:
        name (str): Type name

        description (Optional[str]): Type description

        nodes (List[\
            Union[\
                py_gql.lanf.ast.InputObjectTypeDefinition,\
                py_gql.lanf.ast.InputObjectTypeExtension,\
            ]\
        ]): Source nodes used when building type from the SDL

        fields (List[InputField]): Object fields.

        field_map (Dict[str, InputField]): Object field as a map.
    """

    def __init__(
        self,
        name: str,
        fields: LazyIter[InputField],
        description: Optional[str] = None,
        nodes: Optional[
            List[
                Union[
                    _ast.InputObjectTypeDefinition,
                    _ast.InputObjectTypeExtension,
                ]
            ]
        ] = None,
    ):
        self.name = name
        self.description = description
        self._source_fields = fields
        self._fields = None  # type: Optional[List[InputField]]
        self.nodes = (
            [] if nodes is None else nodes
        )  # noqa: B950, type: List[Union[_ast.InputObjectTypeDefinition, _ast.InputObjectTypeExtension]]

    @property
    def fields(self) -> List[InputField]:
        if self._fields is None:
            self._fields = _evaluate_lazy_iter(self._source_fields)
        return self._fields

    @fields.setter
    def fields(self, fields: List[InputField]) -> None:
        self._fields = self._source_fields = fields

    @property
    def field_map(self) -> Dict[str, InputField]:
        return {f.name: f for f in self.fields}


_EV = TypeVar("_EV", bound="EnumValue")

# TODO: Support defining enum from enum.Enum


class EnumValue:
    """

    Enum value definition.

    Args:
        name: Name of the value

        value: Python value.
            Defaults to ``name`` if omitted.

            Warning:
                Must be hashable to support reverse lookups when coercing python
                values into enum values

        deprecation_reason:
            If set, the value will be marked as deprecated and the introspection
            layer will expose this to consumers.

        description: Enum value description

        node: Source node used when building type from the SDL

    Attributes:
        name (str): Enum value name

        value (str): Enum value value

        description (Optional[str]): Enum value description

        deprecation_reason (Optional[str]):
            If set, the value will be marked as deprecated and the introspection
            layer will expose this to consumers.

        deprecated: ``True`` if :attr:`deprecation_reason` is set.

        node (Optional[py_gql.lang.ast.EnumValueDefinition]):
            Source node used when building type from the SDL
    """

    @classmethod
    def from_def(
        cls: Type[_EV],
        definition: Union[_EV, str, Tuple[str, Any], Dict[str, Any]],
    ) -> _EV:
        """
        Create an enum value from various source objects.

        This supports existing `EnumValue` instances, strings,
        ``(name, value)`` tuples and dictionnaries matching the signature of
        `EnumValue.__init__`.
        """
        if isinstance(definition, cls):
            return definition
        elif isinstance(definition, str):
            return cls(definition, definition)
        elif isinstance(definition, tuple):
            name, value = definition
            return cls(name, value)
        elif isinstance(definition, dict):
            return cls(**definition)
        else:
            raise TypeError("Invalid enum value definition %s" % definition)

    def __init__(
        self,
        name: str,
        value: Any = _UNSET,
        deprecation_reason: Optional[str] = None,
        description: Optional[str] = None,
        node: Optional[_ast.EnumValueDefinition] = None,
    ):
        assert name not in ("true", "false", "null")
        self.name = name
        self.value = value if value is not _UNSET else name
        self.description = description
        self.deprecated = deprecation_reason is not None
        self.deprecation_reason = deprecation_reason
        self.node = node

    def __str__(self) -> str:
        return self.name


class EnumType(NamedType):
    """
    Enum Type Definition

    Some leaf values of requests and input values are Enums. GraphQL serializes
    Enum values as strings, however internally Enums can be represented by any
    kind of Python type.

    Args:
        name: Enum name

        values: List of enum value definition supported by `EnumValue.from_def`

        description: Enum description

        nodes: Source nodes used when building type from the SDL

    Attributes:
        name (str): Enum name

        values (Dict[str, py_gql.schema.EnumValue]): Values by name

        reverse_values: (Dict[H, EnumValue]): Values by value

        description (Optional[str]): Enum description

        nodes (List[Union[\
            py_gql.lang.ast.EnumTypeDefinition, \
            py_gql.lang.ast.EnumTypeExtension,\
        ]]):
            Source nodes used when building type from the SDL
    """

    def __init__(
        self,
        name: str,
        values: Iterable[
            Union[EnumValue, str, Tuple[str, Any], Dict[str, Any]]
        ],
        description: Optional[str] = None,
        nodes: Optional[
            List[Union[_ast.EnumTypeDefinition, _ast.EnumTypeExtension]]
        ] = None,
    ):
        self.name = name
        self.description = description
        self.nodes = (
            [] if nodes is None else nodes
        )  # type: List[Union[_ast.EnumTypeDefinition, _ast.EnumTypeExtension]]

        self._set_values(values)

    def _set_values(
        self,
        values: Iterable[
            Union[EnumValue, str, Tuple[str, Any], Dict[str, Any]]
        ],
    ) -> None:
        self.values = []  # type: List[EnumValue]
        self._values = {}  # type: Dict[str, EnumValue]
        self._reverse_values = {}  # type: Dict[Any, EnumValue]

        for v in values:
            v = EnumValue.from_def(v)
            assert v.name not in self._values, (
                "Duplicate enum value %s" % v.name
            )
            self.values.append(v)
            self._reverse_values[v.value] = self._values[v.name] = v

    def get_value(self, name: str) -> Any:
        """
        Extract the value for a given name.

        Args:
            name: Name of the value to extract

        Returns:
            :class:`py_gql.schema.EnumValue`: The corresponding EnumValue

        Raises:
            :class:`~py_gql.exc.UnknownEnumValue` when the name is unknown
        """
        try:
            return self._values[name].value
        except KeyError:
            raise UnknownEnumValue(
                "Invalid name %s for enum %s" % (name, self.name)
            )

    def get_name(self, value: Any) -> str:
        """
        Extract the name for a given value.

        Args:
            value: Value of the value to extract, must be hashable

        Returns:
            :class:`py_gql.schema.EnumValue`: The corresponding EnumValue

        Raises:
            :class:`~py_gql.exc.UnknownEnumValue` when the value is unknown
        """
        try:
            return self._reverse_values[value].name
        except KeyError:
            raise UnknownEnumValue(
                "Invalid value %r for enum %s" % (value, self.name)
            )


_ScalarValueNode = Union[
    _ast.IntValue, _ast.FloatValue, _ast.StringValue, _ast.BooleanValue
]


# pylint: disable=unsubscriptable-object
class ScalarType(Generic[T], NamedType):
    """
    Scalar Type Definition

    The leaf values of any request and input values to arguments are
    Scalars (or Enums) and are defined with a name and a series of functions
    used to parse input from ast or variables and to ensure validity.

    To define custom scalars, you can either instantiate this class with the
    corresponding arguments (that is how `Int`, `Float`, etc. are implemented)
    or subclass this class and implement :meth:`serialize`, :meth:`parse` and
    :meth:`parse_literal` (this is how `RegexType` is implemented).

    Args:
        name: Type name

        serialize: Type serializer.

            This function will receive a Python value and must output JSON serialisable
            scalars.

            Raise :class:`~py_gql.exc.ScalarSerializationError`,
            :py:class:`ValueError` or :py:class:`TypeError` to signify that the
            value cannot be serialized.

        parse: Type de-serializer.

            This function will receive JSON scalars and can outputs any Python
            value.

            Raise :class:`~py_gql.exc.ScalarParsingError`, :py:class:`ValueError`
            or :py:class:`TypeError` to signify that the value cannot be parsed.

        parse_literal: Type de-serializer for value nodes.

            This function receives a :class:`py_gql.lang.ast.Value`
            and can outputs any Python value.

            Raise :class:`~py_gql.exc.ScalarParsingError`, :py:class:`ValueError`
            or :py:class:`TypeError` to signify that the value cannot be parsed.

            If not provided, the execution layer will extract the node's value
            as a string and pass it to `parse`.

        description: Type description

        nodes: Source nodes used when building type from the SDL

    Attributes:
        name (str): Type name

        description (Optional[str]): Type description

        nodes (List[Union[\
            py_gql.lang.ast.ScalarTypeDefinition, \
            py_gql.lang.ast.ScalarTypeExtension\
        ]]):
            Source nodes used when building type from the SDL

    """

    def __init__(
        self,
        name: str,
        serialize: Callable[[Any], Union[str, int, float, bool, None]],
        parse: Callable[[Any], T],
        parse_literal: Optional[
            Callable[[_ScalarValueNode, Mapping[str, Any]], T]
        ] = None,
        description: Optional[str] = None,
        nodes: Optional[
            List[Union[_ast.ScalarTypeDefinition, _ast.ScalarTypeExtension]]
        ] = None,
    ):
        self.name = name
        self.description = description
        assert callable(serialize)
        self._serialize = serialize
        assert callable(parse)
        self._parse = parse
        assert parse_literal is None or callable(parse_literal)
        self._parse_literal = parse_literal
        self.nodes = (
            [] if nodes is None else nodes
        )  # type: List[Union[_ast.ScalarTypeDefinition, _ast.ScalarTypeExtension]]

    def serialize(self, value: Any) -> Union[str, int, float, bool, None]:
        """
        Transform a Python value in a JSON serializable one.

        Args:
            value: Python level value

        Returns:
            JSON scalar

        Raises:
            ScalarParsingError:
        """
        try:
            return self._serialize(value)
        except (ValueError, TypeError) as err:
            raise ScalarSerializationError(str(err)) from err

    def parse(self, value: Any) -> T:
        """
        Transform a GraphQL value in a valid Python value

        Args:
            value: JSON scalar

        Returns:
            Python level value

        Raises:
            ScalarParsingError:
        """
        try:
            return self._parse(value)
        except (ValueError, TypeError) as err:
            raise ScalarParsingError(str(err)) from err

    def parse_literal(
        self,
        node: _ScalarValueNode,
        variables: Optional[Mapping[str, Any]] = None,
    ) -> T:
        """
        Transform an AST node in a valid Python value

        Args:
            value: Parse node

        Returns:
            Python level value

        Raises:
            ScalarParsingError:
        """
        try:
            try:
                if self._parse_literal is not None:
                    return self._parse_literal(node, variables or {})
                return self.parse(node.value)
            except AttributeError:
                return self.parse(node.value)
        except (ValueError, TypeError) as err:
            raise ScalarParsingError(str(err), [node]) from err


class Argument:
    """
    Argument definition for use in field or directives.

    Warning:
        As ``None`` is a valid default value, in order to define an argument
        without any default value, the ``default_value`` argument **must** be
        omitted.

    Args:
        name: Argument name

        type_: Argument type (must be input type)

        default_value: Default value

        description: Argument description

        node: Source node used when building type from the SDL

    Attributes:
        name (str): Argument name

        description (Optional[str]): Argument description

        has_default_value (bool): ``True`` if default value is set

        default_value (Any):
            Default value if it was set. Accessing this attribute raises an
            :py:class:`AttributeError` if default value wasn't set.

        type (GraphQLType): Vaue type.

        required (bool):
            Whether this argument is required (non nullable and does not have
            any default value)

        node (Optional[py_gql.lang.ast.InputValueDefinition]):
            Source node used when building type from the SDL
    """

    def __init__(
        self,
        name: str,
        type_: Lazy[GraphQLType],
        default_value: Any = _UNSET,
        description: Optional[str] = None,
        node: Optional[_ast.InputValueDefinition] = None,
    ):
        self.name = name
        self.description = description
        self.has_default_value = default_value is not _UNSET
        self.node = node

        self._default_value = default_value
        self._ltype = type_
        self._type = None  # type: Optional[GraphQLType]

    @property
    def default_value(self) -> Any:
        if self._default_value is _UNSET:
            raise AttributeError("No default value")
        return self._default_value

    @default_value.setter
    def default_value(self, value: Any) -> None:
        self._default_value = value

    @default_value.deleter
    def default_value(self) -> None:
        self._default_value = _UNSET

    @property
    def type(self) -> GraphQLType:
        if self._type is None:
            self._type = lazy(self._ltype)
        return self._type

    @type.setter
    def type(self, type_: GraphQLType) -> None:
        self._type = self._ltype = type_

    @property
    def required(self) -> bool:
        return (
            isinstance(self.type, NonNullType) and self._default_value is _UNSET
        )

    def __str__(self) -> str:
        return "Argument(%s: %s)" % (self.name, self.type)

    def __repr__(self) -> str:
        return "Argument(%s: %s at %d)" % (self.name, self.type, id(self))


class Field:
    """
    Member of an :class:`py_gql.schema.ObjectType` or
    :class:`py_gql.schema.InterfaceType`.

    Args:
        name: Field name

        type_: Field type (must be output type)

        args: Field arguments

        description: Field description

        deprecation_reason:
            If set, the field will be marked as deprecated and the introspection
            layer will expose this to consumers.

        resolver: Resolver function.

        node: Source node used when building type from the SDL

    Attributes:
        name (str): Field name

        description (Optional[str]): Field description

        deprecation_reason (Optional[str]):
            If set, the field will be marked as deprecated and the introspection
            layer will expose this to consumers.

        deprecated: ``True`` if :attr:`deprecation_reason` is set.

        type (GraphQLType): Field type.

        arguments (List[py_gql.schema.Argument]): Field arguments.

        argument_map (Dict[str, py_gql.schema.Argument]):
            Field arguments in indexed form.

        resolver (callable): Field resolver.

        node (Optional[py_gql.lang.ast.FieldDefinition]):
            Source node used when building type from the SDL
    """

    def __init__(
        self,
        name: str,
        type_: Lazy[GraphQLType],
        args: Optional[LazyIter[Argument]] = None,
        description: Optional[str] = None,
        deprecation_reason: Optional[str] = None,
        resolver: Optional[Callable[..., Any]] = None,
        node: Optional[_ast.FieldDefinition] = None,
    ):
        assert resolver is None or callable(resolver)

        self.name = name
        self.description = description
        self.deprecated = bool(deprecation_reason)
        self.deprecation_reason = deprecation_reason
        self.resolver = resolver
        self._source_args = args
        self._args = None  # type: Optional[List[Argument]]
        self.node = node

        self._ltype = type_
        self._type = None  # type: Optional[GraphQLType]

    @property
    def type(self) -> GraphQLType:
        if self._type is None:
            self._type = lazy(self._ltype)
        return self._type

    @type.setter
    def type(self, type_: GraphQLType) -> None:
        self._type = self._ltype = type_

    @property
    def arguments(self) -> List[Argument]:
        if self._args is None:
            self._args = _evaluate_lazy_iter(self._source_args)
        return self._args

    @arguments.setter
    def arguments(self, args: List[Argument]) -> None:
        self._args = self._source_args = args

    @property
    def argument_map(self) -> Dict[str, Argument]:
        return {arg.name: arg for arg in self.arguments}

    def __str__(self) -> str:
        return "Field(%s: %s)" % (self.name, self.type)

    def __repr__(self) -> str:
        return "Field(%s: %s at %d)" % (self.name, self.type, id(self))


class InterfaceType(NamedType):
    """
    Interface Type Definition.

    When a field can return one of a heterogeneous set of types, a Interface
    type is used to describe what types are possible, what fields are in
    common across all types, as well as a function to determine which type
    is actually used when the field is resolved.

    Args:
        name: Type name

        fields: Fields

        resolve_type: Type resolver

        description: Type description

        nodes: Source nodes used when building type from the SDL

    Attributes:
        name (str): Type name

        description (Optional[str]): Type description

        fields (List[py_gql.schema.Field]): Object fields.

        field_map (Dict[str, py_gql.schema.Field]):
            Object field as a map.

        resolve_type (Optional[callable]): Type resolver

        nodes (List[Union[\
            py_gql.lang.ast.InterfaceTypeDefinition,\
            py_gql.lang.ast.InterfaceTypeExtension,\
        ]]):
            Source nodes used when building type from the SDL
    """

    def __init__(
        self,
        name: str,
        fields: LazyIter[Field],
        resolve_type: Optional[Callable[[Any], Union[OT, str]]] = None,
        description: Optional[str] = None,
        nodes: Optional[
            List[
                Union[_ast.InterfaceTypeDefinition, _ast.InterfaceTypeExtension]
            ]
        ] = None,
    ):
        self.name = name
        self.description = description
        self._source_fields = fields
        self._fields = None  # type: Optional[List[Field]]
        self.nodes = (
            [] if nodes is None else nodes
        )  # noqa: B950, type: List[Union[_ast.InterfaceTypeDefinition, _ast.InterfaceTypeExtension]]

        assert resolve_type is None or callable(resolve_type)
        self.resolve_type = resolve_type

    @property
    def fields(self) -> List[Field]:
        if self._fields is None:
            self._fields = _evaluate_lazy_iter(self._source_fields)
        return self._fields

    @fields.setter
    def fields(self, fields: List[Field]) -> None:
        self._fields = self._source_fields = fields

    @property
    def field_map(self) -> Dict[str, Field]:
        return {f.name: f for f in self.fields}


class ObjectType(NamedType):
    """
    Object Type Definition

    Almost all of the GraphQL types you define will be object types. Object
    types have a name, but most importantly describe their fields.

    Args:
        name: Type name

        fields: Fields

        interfaces: Implemented interfaces

        is_type_of: Value type checker

        description: Type description

        nodes: Source nodes used when building type from the SDL

    Attributes:
        name (str): Type name

        description (Optional[str]): Type description

        interfaces (List[InterfaceType]):
            Implemented interfaces.

        fields (List[py_gql.schema.Field]): Object fields.

        field_map (Dict[str, py_gql.schema.Field]):
            Object field as a map.

        is_type_of (Optional[callable]): Value type checker.

        nodes (List[Union[\
            py_gql.lang.ast.ObjectTypeDefinition,\
            py_gql.lang.ast.ObjectTypeExtension,\
        ]]):
            Source nodes used when building type from the SDL
    """

    def __init__(
        self,
        name: str,
        fields: LazyIter[Field],
        interfaces: Optional[LazyIter[InterfaceType]] = None,
        is_type_of: Optional[Union[Callable[[Any], bool], Type[Any]]] = None,
        description: Optional[str] = None,
        nodes: Optional[
            List[Union[_ast.ObjectTypeDefinition, _ast.ObjectTypeExtension]]
        ] = None,
    ):
        self.name = name
        self.description = description
        self._source_fields = fields
        self._source_fields = fields
        self._fields = None  # type: Optional[List[Field]]
        self._source_interfaces = interfaces
        self._interfaces = None  # type: Optional[List[InterfaceType]]
        self.nodes = (
            [] if nodes is None else nodes
        )  # type: List[Union[_ast.ObjectTypeDefinition, _ast.ObjectTypeExtension]]

        assert is_type_of is None or callable(is_type_of)
        if isinstance(is_type_of, type):
            self.is_type_of = lambda v, *_, **__: isinstance(v, is_type_of)
        else:
            self.is_type_of = is_type_of  # type: ignore

    @property
    def interfaces(self) -> List[InterfaceType]:
        if self._interfaces is None:
            self._interfaces = _evaluate_lazy_iter(self._source_interfaces)
        return self._interfaces

    @interfaces.setter
    def interfaces(self, interfaces: List[InterfaceType]) -> None:
        self._interfaces = self._source_interfaces = interfaces

    @property
    def fields(self) -> List[Field]:
        if self._fields is None:
            self._fields = _evaluate_lazy_iter(self._source_fields)
        return self._fields

    @fields.setter
    def fields(self, fields: List[Field]) -> None:
        self._fields = self._source_fields = fields

    @property
    def field_map(self) -> Dict[str, Field]:
        return {f.name: f for f in self.fields}


class UnionType(NamedType):
    """
    Union Type Definition

    When a field can return one of a heterogeneous set of types, a Union type
    is used to describe what types are possible as well as providing a function
    to determine which type is actually used when the field is resolved.

    Args:
        name: Type name

        types: Member types

        resolve_type: Type resolver

        description: Type description

        nodes: Source nodes used when building type from the SDL

    Attributes:
        name (str): Type name

        description (Optional[str]): Type description

        resolve_type (Optional[callable]): Type resolver

        types (List[ObjectType]): Member types.

        nodes (List[Union[\
            py_gql.lang.ast.UnionTypeDefinition,\
            py_gql.lang.ast.UnionTypeExtension,\
        ]]):
            Source nodes used when building type from the SDL

    """

    def __init__(
        self,
        name: str,
        types: LazyIter[ObjectType],
        resolve_type: Optional[Callable[[Any], Union[OT, str]]] = None,
        description: Optional[str] = None,
        nodes: Optional[
            List[Union[_ast.UnionTypeDefinition, _ast.UnionTypeExtension]]
        ] = None,
    ):
        self.name = name
        self.description = description
        self._source_types = types
        self._types = None  # type: Optional[List[ObjectType]]
        self.nodes = (
            [] if nodes is None else nodes
        )  # type: List[Union[_ast.UnionTypeDefinition, _ast.UnionTypeExtension]]

        assert resolve_type is None or callable(resolve_type)
        self.resolve_type = resolve_type

    @property
    def types(self) -> List[ObjectType]:
        if self._types is None:
            self._types = _evaluate_lazy_iter(self._source_types)
        return self._types

    @types.setter
    def types(self, types: List[ObjectType]) -> None:
        self._types = self._source_types = types


class Directive(NamedType):
    """
    Directive definition

    `Directives <https://graphql.github.io/graphql-spec/June2018/#sec-Type-System.Directives>`_
    are used by the GraphQL runtime as a way of modifying execution behavior.
    Type system creators will usually not create these directly.

    Args:
        name: Directive name

        locations: Possible locations for that directive

        args: Argument definitions

        description: Directive description

        node: Source node used when building type from the SDL.

    Attributes:
        name (str): Directive name

        description (Optional[str]): Directive description

        locations (List[str]): Possible locations for that directive

        arguments (List[py_gql.schema.Argument]): Directive arguments.

        argument_map (Dict[str, py_gql.schema.Argument]):
            Directive arguments in indexed form.

        node (Optional[py_gql.lang.ast.DirectiveDefinition]):
            Source node used when building type from the SDL
    """

    def __init__(
        self,
        name: str,
        locations: List[str],
        args: Optional[List[Argument]] = None,
        description: Optional[str] = None,
        node: Optional[_ast.DirectiveDefinition] = None,
    ):
        assert locations and all(
            loc in DIRECTIVE_LOCATIONS for loc in locations
        )
        self.name = name
        self.description = description
        self.locations = locations
        self.arguments = args if args is not None else []
        self.argument_map = {arg.name: arg for arg in self.arguments}
        self.node = node


def is_input_type(type_: GraphQLType) -> bool:
    """ These types may be used as input types for arguments and directives. """
    return isinstance(
        unwrap_type(type_), (ScalarType, EnumType, InputObjectType)
    )


def is_output_type(type_: GraphQLType) -> bool:
    """ These types may be used as output types as the result of fields. """
    return isinstance(
        unwrap_type(type_),
        (ScalarType, EnumType, ObjectType, InterfaceType, UnionType),
    )


def is_leaf_type(type_: GraphQLType) -> bool:
    """  These types may describe types which may be leaf values. """
    return isinstance(type_, (ScalarType, EnumType))


def is_composite_type(type_: GraphQLType) -> bool:
    """ These types may describe the parent context of a selection set. """
    return isinstance(type_, (ObjectType, InterfaceType, UnionType))


def is_abstract_type(type_: GraphQLType) -> bool:
    """ These types may describe the parent context of a selection set. """
    return isinstance(type_, (InterfaceType, UnionType))


def unwrap_type(type_: GraphQLType) -> GraphQLType:
    """ Recursively extract type for a potentially wrapping type like
    :class:`ListType` or :class:`NonNullType`.

    >>> from py_gql.schema import Int, NonNullType, ListType
    >>> unwrap_type(NonNullType(ListType(NonNullType(Int)))) is Int
    True
    """
    if isinstance(type_, (ListType, NonNullType)):
        return unwrap_type(type_.type)
    return type_


def nullable_type(type_: GraphQLType) -> GraphQLType:
    """ Extract nullable type from a potentially non nulllable one.

    >>> from py_gql.schema import Int, NonNullType
    >>> unwrap_type(NonNullType(Int)) is Int
    True

    >>> unwrap_type(Int) is Int
    True
    """
    if isinstance(type_, NonNullType):
        return type_.type
    return type_


# Used for simple isinstance classes
AbstractTypes = (InterfaceType, UnionType)
CompositeTypes = (ObjectType, InterfaceType, UnionType)
LeafTypes = (ScalarType, EnumType)
OutputTypes = (ScalarType, EnumType, ObjectType, InterfaceType, UnionType)
