# coding=utf-8
# pylint: disable=abstract-method
"""
Build and index fields within documents.
"""
from __future__ import absolute_import

from functools import partial

from dateutil import tz
from psycopg2.extras import NumericRange, DateTimeTZRange
from sqlalchemy import cast
from sqlalchemy import func
from sqlalchemy.dialects import postgresql as postgres
from sqlalchemy.dialects.postgresql import INT4RANGE
from sqlalchemy.dialects.postgresql import NUMRANGE, TSTZRANGE
from sqlalchemy.dialects.postgresql.base import DOUBLE_PRECISION

from datacube.index.fields import Expression, Field
from datacube.index.postgres.tables import FLOAT8RANGE
from datacube.model import Range
from datacube.utils import get_doc_offset


class PgField(Field):
    """
    Postgres implementation of a searchable field. May be a value inside
    a JSONB column.
    """

    def __init__(self, name, description, metadata_type_id, alchemy_column):
        super(PgField, self).__init__(name, description)
        self.metadata_type_id = metadata_type_id

        # The underlying SQLAlchemy column. (eg. DATASET.c.metadata)
        self.alchemy_column = alchemy_column

    @property
    def required_alchemy_table(self):
        return self.alchemy_column.table

    @property
    def alchemy_expression(self):
        """
        Get an SQLAlchemy expression for accessing this field.
        :return:
        """
        raise NotImplementedError('alchemy expression')

    @property
    def postgres_index_type(self):
        return 'btree'

    def __eq__(self, value):
        """
        :rtype: Expression
        """
        return EqualsExpression(self, value)

    def between(self, low, high):
        """
        :rtype: Expression
        """
        raise NotImplementedError('between expression')


class NativeField(PgField):
    """
    Fields hard-coded into the schema. (not user configurable)
    """

    def __init__(self, name, description, metadata_type_id, alchemy_column, alchemy_expression=None):
        super(NativeField, self).__init__(name, description, metadata_type_id, alchemy_column)
        self._expression = alchemy_expression

    @property
    def alchemy_expression(self):
        return (self._expression or self.alchemy_column).label(self.name)

    @property
    def postgres_index_type(self):
        # Don't add extra indexes for native fields.
        return None


class SimpleDocField(PgField):
    """
    A field with a single value (eg. String, int)
    """

    def __init__(self, name, description, metadata_type_id, alchemy_column, offset=None):
        super(SimpleDocField, self).__init__(name, description, metadata_type_id, alchemy_column)
        self.offset = offset

    @property
    def alchemy_casted_type(self):
        # Default no cast: string
        return None

    def from_string(self, s):
        """
        Parse the value from a string. May be overridden by subclasses.
        """
        return s

    @property
    def alchemy_expression(self):
        _field = self.alchemy_column[self.offset].astext
        return cast(_field, self.alchemy_casted_type) if self.alchemy_casted_type else _field

    def __eq__(self, value):
        """
        :rtype: Expression
        """
        return EqualsExpression(self, value)

    def between(self, low, high):
        """
        :rtype: Expression
        """
        raise NotImplementedError('Simple field between expression')

    def extract(self, document):
        v = get_doc_offset(self.offset, document)
        if v is None:
            return None

        return self.from_string(v)

    def evaluate(self, ctx):
        return self.extract(ctx)


class IntDocField(SimpleDocField):
    @property
    def alchemy_casted_type(self):
        return postgres.INTEGER

    def from_string(self, s):
        return int(s)


class DoubleDocField(SimpleDocField):
    @property
    def alchemy_casted_type(self):
        return postgres.DOUBLE_PRECISION

    def from_string(self, s):
        return float(s)


class RangeDocField(PgField):
    """
    A range of values. Has min and max values, which may be calculated from multiple
    values in the document.
    """

    def __init__(self, name, description, metadata_type_id, alchemy_column, min_offset=None, max_offset=None):
        super(RangeDocField, self).__init__(name, description, metadata_type_id, alchemy_column)
        self.min_offset = min_offset
        self.max_offset = max_offset

    @property
    def alchemy_create_range(self):
        raise NotImplementedError('range type')

    def alchemy_parse_value(self, value):
        # Default no cast: string
        return None

    @property
    def postgres_index_type(self):
        return 'gist'

    def _get_expr(self, doc_offsets, agg_function, parse_value):
        fields = [self.alchemy_column[offset].astext for offset in doc_offsets]

        fields = [parse_value(field) for field in fields]

        # If there's multiple fields, we aggregate them (eg. "min()"). Otherwise use the one.
        return agg_function(*fields) if len(fields) > 1 else fields[0]

    @property
    def alchemy_expression(self):
        return self.alchemy_create_range(
            self._get_expr(self.min_offset, func.least, self.alchemy_parse_value),
            self._get_expr(self.max_offset, func.greatest, self.alchemy_parse_value),
            # Inclusive on both sides.
            '[]'
        )

    def __eq__(self, value):
        """
        :rtype: Expression
        """
        raise NotImplementedError('range equals expression')

    def extract(self, document):
        def safe_get_doc_offset(offset, document):
            try:
                return get_doc_offset(offset, document)
            except KeyError:
                return None

        min_vals = [v for v in (safe_get_doc_offset(offset, document) for offset in self.min_offset) if v]
        max_vals = [v for v in (safe_get_doc_offset(offset, document) for offset in self.max_offset) if v]

        min_val = min(min_vals) if min_vals else None
        max_val = max(max_vals) if max_vals else None

        if not min_val and not max_val:
            return None

        return Range(min_val, max_val)


class NumericRangeDocField(RangeDocField):
    def alchemy_parse_value(self, value):
        return cast(value, postgres.NUMERIC)

    @property
    def alchemy_create_range(self):
        # Call the postgres 'numrange()' function, hinting to SQLAlchemy that it returns a NUMRANGE.
        return partial(func.numrange, type_=NUMRANGE)

    def between(self, low, high):
        """
        :rtype: Expression
        """
        return RangeBetweenExpression(self, low, high, _range_class=NumericRange)


class IntRangeDocField(RangeDocField):
    def alchemy_parse_value(self, value):
        return cast(value, postgres.INTEGER)

    @property
    def alchemy_create_range(self):
        return partial(func.numrange, type_=INT4RANGE)

    def between(self, low, high):
        """
        :rtype: Expression
        """
        return RangeBetweenExpression(self, low, high, _range_class=NumericRange)



class DoubleRangeDocField(RangeDocField):
    def alchemy_parse_value(self, value):
        return cast(value, DOUBLE_PRECISION)

    @property
    def alchemy_create_range(self):
        return partial(func.agdc.float8range, type_=FLOAT8RANGE)

    def between(self, low, high):
        """
        :rtype: Expression
        """
        return RangeBetweenExpression(self, low, high, _range_class=NumericRange)


class DateRangeDocField(RangeDocField):
    def alchemy_parse_value(self, value):
        return func.agdc.common_timestamp(value)

    @property
    def alchemy_create_range(self):
        # Call the postgres 'tstzrange()' function, hinting to SQLAlchemy that it returns a TSTZRANGE.
        return partial(func.tstzrange, type_=TSTZRANGE)

    def _default_utc(self, d):
        if d.tzinfo is None:
            return d.replace(tzinfo=tz.tzutc())
        return d

    def between(self, low, high):
        """
        :rtype: Expression
        """
        return RangeBetweenExpression(
            self,
            self._default_utc(low),
            self._default_utc(high),
            _range_class=DateTimeTZRange
        )


class PgExpression(Expression):
    def __init__(self, field):
        super(PgExpression, self).__init__()
        #: :type: PgField
        self.field = field

    @property
    def alchemy_expression(self):
        """
        Get an SQLAlchemy expression for accessing this field.
        :return:
        """
        raise NotImplementedError('alchemy expression')


class RangeBetweenExpression(PgExpression):
    def __init__(self, field, low_value, high_value, _range_class):
        super(RangeBetweenExpression, self).__init__(field)
        self.low_value = low_value
        self.high_value = high_value
        self._range_class = _range_class

    @property
    def alchemy_expression(self):
        return self.field.alchemy_expression.overlaps(
            self._range_class(self.low_value, self.high_value)
        )


class EqualsExpression(PgExpression):
    def __init__(self, field, value):
        super(EqualsExpression, self).__init__(field)
        self.value = value

    @property
    def alchemy_expression(self):
        return self.field.alchemy_expression == self.value

    def evaluate(self, ctx):
        return self.field.evaluate(ctx) == self.value


def parse_fields(doc, metadata_type_id, table_column):
    """
    Parse a field spec document into objects.

    Example document:
    :param metadata_type_id:
    ::

        {
            # Field name:
            'lat': {
                # Field type & properties.
                'type': 'float-range',
                'min_offset': [
                    # Offsets within a dataset document for this field.
                    ['extent', 'coord', 'ul', 'lat'],
                    ['extent', 'coord', 'll', 'lat']
                ],
                'max_offset': [
                    ['extent', 'coord', 'ur', 'lat'],
                    ['extent', 'coord', 'lr', 'lat']
                ]
            }
        }

    :param table_column: SQLAlchemy jsonb column for the document we're reading fields from.
    :type doc: dict
    :rtype: dict[str, PgField]
    """

    def _get_field(name, metadata_type_id, descriptor, column):
        """

        :type name: str
        :type descriptor: dict
        :param column: SQLAlchemy table column
        :rtype: PgField
        """
        type_map = {
            'numeric-range': NumericRangeDocField,
            'double-range': DoubleRangeDocField,
            'integer-range': IntRangeDocField,
            'datetime-range': DateRangeDocField,
            'string': SimpleDocField,
            'integer': IntDocField,
            'double': DoubleDocField,
            # For backwards compatibility
            'float-range': NumericRangeDocField,
        }
        type_name = descriptor.pop('type', 'string')
        description = descriptor.pop('description', None)

        field_class = type_map.get(type_name)
        if not field_class:
            raise ValueError(('Field %r has unknown type %r.'
                              ' Available types are: %r') % (name, type_name, list(type_map.keys())))
        try:
            return field_class(name, description, metadata_type_id, column, **descriptor)
        except TypeError as e:
            raise RuntimeError(
                'Field {name} has unexpected argument for a {type}'.format(
                    name=name, type=type_name
                ), e
            )

    return {name: _get_field(name, metadata_type_id, descriptor, table_column) for name, descriptor in doc.items()}
