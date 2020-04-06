"""
WORM, the simplest ORM ever.
"""

import string, types

# 'cursor' must be injected from outside
DEBUG = 0

class DatabaseObject:
    """Common superclass for all objects mapped from the database. The
    convention is that all fields must be _foo attributes, where 'foo'
    is the name of an actual database column. The framework handles the
    rest. Fields are accessed with normal get/set methods."""

    def __init__(self, idfield, table, typemap = {}):
        self.__idfield = idfield
        self.__loaded = 0
        self.__table = table
        self.__typemap = typemap

    def get_primary_key(self):
        return self.__dict__["_" + self.__idfield]

    def get_primary_key_sql(self):
        return self._convert_to_sql(self.__idfield, self.get_primary_key())

    def __getattr__(self, name):
        if name[ : 4] == "get_" and self.__dict__.has_key(name[3 : ]):
            if not self.__loaded and self.__dict__.get(name[3 : ]) == None:
                self._load()
            return lambda x = self, attr = name[3 : ]: x.__dict__[attr]
        elif name[ : 4] == "set_" and self.__dict__.has_key(name[3 : ]):
            return SetMethod(self, name[3 : ])
        else:
            raise AttributeError, name

    def _load(self):
        if self.__loaded:
            return

        if DEBUG:
            print "Loaded %s from %s<br>" % (self.get_primary_key(),
                                             self.__table)

        cursor.execute('select * from %s where %s = %%s' %
                          (self.__table, self.__idfield),
                       (self.get_primary_key(), ))
        row = cursor.fetchone()
        self._populate_from_row(row)
        self.__loaded = True

    def _populate_from_row(self, row):
        for ix in range(len(row)):
            colname = cursor.description[ix][0]
            if self.__typemap.has_key(colname):
                klass = self.__typemap[colname]
                if row[ix]:
                    val = klass(row[ix])
                else:
                    val = None
            else:
                val = row[ix]
            self.__dict__['_' + colname] = val
        self.__loaded = (len(cursor.description) == len(self._get_fields()))

    def _get_fields(self):
        return map(lambda x: x[1 : ],
                   filter(lambda x: x[0] == "_" and x != "_id" and string.find(x, "__") == -1,
                          self.__dict__.keys()))

    def _convert_to_sql(self, field, value):
        if value == None:
            return "NULL"

        if type(value) == types.LongType:
            return str(value)
        else:
            return repr(value)

    def _make_fields(self): # FIXME: soon to be unused
        return ['%s = %%s' % field for field in self._get_fields()]

    def _make_field_args(self):
        return [self.__dict__["_" + field] for field in self._get_fields()]

    def save(self):
        fields = self._make_fields()
        sql = "update %s set %s where %s = %s" % \
              (self.__table, string.join(fields, ", "),
               self.__idfield,
               self.get_primary_key_sql())
        if DEBUG:
            print sql, "<br>"
        cursor.execute(sql)

    def create(self):
        fields = self._make_fields()
        sql = "insert into %s (%s) values (%s)" % \
              (self.__table, string.join(self._get_fields(), ", "),
               string.join(['%s' for field in fields], ', '))
        cursor.execute(sql, self._make_field_args())

    def delete(self):
        cursor.execute("delete from %s where id = %s" %
                       (self.__table, self.get_primary_key_sql()))

    def _load_many_to_many(self, near, table, far, klass, limit = None,
                           offset = None, order = None, filter = None):
        query = '''
          select t1.*
          from %s t1
          join %s t2 on t1.%s = t2.%s
          where t2.%s = %%s
        ''' % (klass.TABLE, table, klass.ID, far, near)
        if filter:
            query += ' and ' + filter
        if order:
            query += ' order by ' + order
        if offset:
            query += ' offset %s' % offset
        if limit:
            query += ' limit %s' % limit
        return query_for_list(query, klass, (self.get_primary_key(), ))

    def _count_many_to_many(self, near, table, far, klass, filter = None):
        query = '''
          select count(t1.*)
          from %s t1
          join %s t2 on t1.%s = t2.%s
          where t2.%s = %%s
        ''' % (klass.TABLE, table, klass.ID, far, near)
        if filter:
            query += ' and ' + filter
        return query_for_value(query, (self.get_primary_key(), ))

    def _load_one_to_many(self, klass, column, limit = None, filter = None,
                          offset = None, order = None):
        query = 'select * from %s t1 where %s = %%s' % (klass.TABLE, column)
        if filter:
            query += ' and ' + filter
        if order:
            query += ' order by ' + order
        if offset:
            query += ' offset %s' % offset
        if limit:
            query += ' limit %s' % limit
        return query_for_list(query, klass, (self.get_primary_key(), ))

    def _count_one_to_many(self, klass, column, filter = None):
        query = 'select count(*) from %s t1 where %s = %%s' % \
                   (klass.TABLE, column)
        if filter:
            query += ' and ' + filter
        return query_for_value(query, (self.get_primary_key(), ))

class SetMethod:

    def __init__(self, object, attribute):
        self._object = object
        self._attribute = attribute

    def __call__(self, *args):
        if self._object.get_primary_key():
            self._object._load() # needed since we don't track dirtyness
        self._object.__dict__[self._attribute] = args[0]

def query_for_list(query, constructor, args = ()):
    list = []
    cursor.execute(query, args)
    return [make(constructor, row) for row in cursor.fetchall()]

def query_for_one(query, constructor, args = ()):
    cursor.execute(query, args)
    return make(constructor, cursor.fetchone())

def query_for_value(query, args = ()):
    cursor.execute(query, args)
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        return None

def get_extent(klass, where = None):
    if where:
        where = ' where ' + where
    else:
        where = ''
    return query_for_list("select * from " + klass.TABLE + where, klass)

def make(klass, row):
    object = klass(None)
    object._populate_from_row(row)
    return object
