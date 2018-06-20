from .utils import price_from_stripe, dt_from_stripe
from django.db import models
from django.db.models.expressions import Col
from django.db.models.lookups import IExact
from django.db.models.fields.related_lookups import RelatedLookupMixin

__all__ = ['IntegerField']


class DatetimeProxy:
    def __init__(self, source):
        self.source = source
        self.path = source.split('.')

    def __get__(self, obj, type=None):
        if obj is None:
            return obj
        value = obj.data
        for p in self.path:
            value = value.get(p, MISSING)
            if value is MISSING:
                return
        if value is not None:
            return dt_from_stripe(value)


class CharProxy:
    def __init__(self, source):
        self.source = source
        self.path = source.split('.')

    def __get__(self, obj, type=None):
        if obj is None:
            return obj
        value = obj.data
        for p in self.path:
            value = value.get(p, MISSING)
            if value is MISSING:
                return
        if value is not None:
            return str(value)


class IntegerProxy:
    def __init__(self, source):
        self.source = source
        self.path = source.split('.')

    def __get__(self, obj, type=None):
        if obj is None:
            return obj
        value = obj.data
        for p in self.path:
            value = value.get(p, MISSING)
            if value is MISSING:
                return
        if value is not None:
            return int(value)


class PriceProxy:
    def __init__(self, source):
        self.source = source
        self.path = source.split('.')

    def __get__(self, obj, type=None):
        if obj is None:
            return obj
        value = obj.data
        currency = value.get('currency', MISSING)
        for p in self.path:
            currency = value.get('currency', MISSING)
            value = value.get(p, MISSING)
            if value is MISSING:
                return
        if value is not None:
            # TODO: convert the value to local
            pass
        return price_from_stripe(value, currency)


class BooleanProxy:
    def __init__(self, source):
        self.source = source
        self.path = source.split('.')

    def __get__(self, obj, type=None):
        if obj is None:
            return obj
        value = obj.data
        for p in self.path:
            value = value.get(p, MISSING)
            if value is MISSING:
                return
        if value is not None:
            return bool(value)


class StripeCol(Col):
    def as_sql(self, compiler, connection):
        qn = compiler.quote_name_unless_alias
        *prev, last = ["data"] + [f"'{p}'" for p in self.target.source.split('.')]
        field = '->'.join(prev) + '->>' + last
        # cast for now
        field = "%s.%s" % (qn(self.alias), field)
        if isinstance(self.target, DateTimeField):
            field = f'to_timestamp(({field})::text::double precision)'
        elif isinstance(self.target, IntegerField):
            field = f'({field})::text::numeric'
        elif isinstance(self.target, BooleanField):
            field = f'({field})::text::bool'
        else:
            field = f'({field})::text'
        return field, []


class StripeField(models.Field):
    proxy = None

    def __init__(self, *args, source, **kwargs):
        """
        Parameters:
            source (str): the path in data JSON
        """
        self.source = source
        kwargs['null'] = True
        kwargs['editable'] = False
        kwargs['serialize'] = False
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["source"] = self.source
        del kwargs["editable"]
        del kwargs["serialize"]
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name):
        self.name = name
        self.verbose_name = name
        self.field_name = name
        self.attname = name
        self.model = cls

        self.concrete = False
        self.column = f'__{self.source}__'
        proxy = type(self).proxy(self.source)
        cls._meta.add_field(self, private=True)
        setattr(cls, name, proxy)

    def get_col(self, alias, output_field=None):
        col = super().get_col(alias, output_field)
        if isinstance(col, Col):
            col.__class__ = StripeCol
        return col

    # def select_format(self, compiler, sql, params):
    #     sql, params = super().select_format(compiler, sql, params)
    #     print('select_format', self, sql, params)
    #     return sql, params

    # def get_lookup(self, name):
    #     result = super().get_lookup(name)
    #     print('get_lookup', self, result, name)
    #     # get_lookup rayures.Coupon.created_at <class 'django.db.models.lookups.GreaterThanOrEqual'> gte
    #     # get_lookup rayures.Coupon.created_at <class 'django.db.models.lookups.LessThan'> lt
    #     return result

    # def get_transform(self, name):
    #     result = super().get_transform(name)
    #     print('get_transform', self, result, name)
    #     return result


class IntegerField(StripeField, models.IntegerField):
    # description = _("String (up to %(max_length)s)")
    proxy = IntegerProxy

    def get_internal_type(self):
        return 'IntegerField'


class CharField(StripeField, models.CharField):
    # description = _("String (up to %(max_length)s)")
    proxy = CharProxy

    def get_internal_type(self):
        return 'CharField'


class DateTimeField(StripeField, models.DateTimeField):
    # description = _("String (up to %(max_length)s)")
    proxy = DatetimeProxy

    def get_internal_type(self):
        return 'DateTimeField'


class PriceField(StripeField):
    # description = _("String (up to %(max_length)s)")
    proxy = PriceProxy


class BooleanField(StripeField, models.NullBooleanField):
    # description = _("String (up to %(max_length)s)")
    proxy = BooleanProxy

    def get_internal_type(self):
        return 'NullBooleanField'


MISSING = object()


class ForeignKey(models.ForeignKey):
    def __init__(self, to, related_name=None, related_query_name=None,
                 limit_choices_to=None, parent_link=False, to_field=None,
                 source=None,
                 **kwargs):
        kwargs['to'] = to
        kwargs['related_name'] = related_name
        kwargs['related_query_name'] = related_query_name
        kwargs['limit_choices_to'] = limit_choices_to
        kwargs['parent_link'] = parent_link
        kwargs['to_field'] = to_field
        # forced
        kwargs['db_constraint'] = False
        kwargs['db_index'] = False
        kwargs['null'] = True
        kwargs['on_delete'] = models.SET_NULL

        # our
        kwargs['editable'] = False
        self.source = source

        super().__init__(**kwargs)

    def get_col(self, alias, output_field=None):
        col = super().get_col(alias, output_field)
        if isinstance(col, Col):
            col.__class__ = StripeCol
        return col

    def contribute_to_class(self, cls, name, private_only=False, **kwargs):
        return super().contribute_to_class(cls, name, private_only=True, **kwargs)


@ForeignKey.register_lookup
class RelatedIExact(RelatedLookupMixin, IExact):
    pass
