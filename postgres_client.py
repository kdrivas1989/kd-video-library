"""
Supabase-compatible query builder over psycopg2.

Drop-in replacement so that `supabase.table('x').select('*').eq('col', val).execute()`
works identically whether backed by Supabase or plain Postgres.
"""

import psycopg2
import psycopg2.extras


class QueryResult:
    """Mimics the Supabase APIResponse."""
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class _NotProxy:
    """Handles supabase `.not_.is_('col', 'null')` syntax."""
    def __init__(self, query):
        self._query = query

    def is_(self, column, value):
        if value == 'null':
            self._query._conditions.append((column, 'is not', None))
        else:
            self._query._conditions.append((column, 'is not', value))
        return self._query


class SelectQuery:
    def __init__(self, conn_factory, table, columns='*', count_mode=None):
        self._conn_factory = conn_factory
        self._table = table
        self._columns = columns
        self._count_mode = count_mode
        self._conditions = []
        self._or_clause = None
        self._order_col = None
        self._order_desc = False
        self._limit_val = None
        self.not_ = _NotProxy(self)

    def eq(self, column, value):
        self._conditions.append((column, '=', value))
        return self

    def gt(self, column, value):
        self._conditions.append((column, '>', value))
        return self

    def lt(self, column, value):
        self._conditions.append((column, '<', value))
        return self

    def gte(self, column, value):
        self._conditions.append((column, '>=', value))
        return self

    def lte(self, column, value):
        self._conditions.append((column, '<=', value))
        return self

    def in_(self, column, values):
        self._conditions.append((column, 'in', tuple(values)))
        return self

    def or_(self, filter_string):
        """Parse Supabase PostgREST-style OR filter string.

        Example: "title.ilike.%q%,description.ilike.%q%"
        """
        self._or_clause = filter_string
        return self

    def order(self, column, desc=False):
        self._order_col = column
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit_val = n
        return self

    def _parse_or_clause(self):
        """Convert PostgREST filter string to SQL conditions."""
        parts = []
        params = []
        # Split on commas, but each part is "column.operator.value"
        for token in self._or_clause.split(','):
            segments = token.split('.', 2)
            if len(segments) < 3:
                continue
            col, op, val = segments[0], segments[1], segments[2]
            if op == 'ilike':
                parts.append(f'"{col}" ILIKE %s')
                params.append(val)
            elif op == 'like':
                parts.append(f'"{col}" LIKE %s')
                params.append(val)
            elif op == 'eq':
                parts.append(f'"{col}" = %s')
                params.append(val)
            elif op == 'neq':
                parts.append(f'"{col}" != %s')
                params.append(val)
            elif op == 'gt':
                parts.append(f'"{col}" > %s')
                params.append(val)
            elif op == 'lt':
                parts.append(f'"{col}" < %s')
                params.append(val)
        return parts, params

    def execute(self):
        conn = self._conn_factory()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if self._columns == '*':
            select_part = '*'
        else:
            select_part = ', '.join(f'"{c.strip()}"' for c in self._columns.split(','))

        sql = f'SELECT {select_part} FROM "{self._table}"'
        params = []

        where_parts = []
        for col, op, val in self._conditions:
            if op == 'in':
                where_parts.append(f'"{col}" IN %s')
                params.append(val)
            elif op == 'is not':
                where_parts.append(f'"{col}" IS NOT NULL')
            elif val is None:
                where_parts.append(f'"{col}" IS NULL')
            else:
                where_parts.append(f'"{col}" {op} %s')
                params.append(val)

        if self._or_clause:
            or_parts, or_params = self._parse_or_clause()
            if or_parts:
                where_parts.append(f'({" OR ".join(or_parts)})')
                params.extend(or_params)

        if where_parts:
            sql += ' WHERE ' + ' AND '.join(where_parts)

        if self._order_col:
            direction = 'DESC' if self._order_desc else 'ASC'
            sql += f' ORDER BY "{self._order_col}" {direction}'

        if self._limit_val is not None:
            sql += f' LIMIT {int(self._limit_val)}'

        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

        count = None
        if self._count_mode == 'exact':
            # Run a separate COUNT query with the same WHERE clause
            count_sql = f'SELECT COUNT(*) FROM "{self._table}"'
            if where_parts:
                count_sql += ' WHERE ' + ' AND '.join(where_parts)
            cur.execute(count_sql, params)
            count = cur.fetchone()['count']

        cur.close()
        return QueryResult(data=rows, count=count)


class InsertQuery:
    def __init__(self, conn_factory, table, data):
        self._conn_factory = conn_factory
        self._table = table
        self._data = data if isinstance(data, list) else [data]

    def execute(self):
        conn = self._conn_factory()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        all_rows = []
        for row in self._data:
            cols = list(row.keys())
            vals = [row[c] for c in cols]
            col_str = ', '.join(f'"{c}"' for c in cols)
            placeholder = ', '.join(['%s'] * len(cols))
            sql = f'INSERT INTO "{self._table}" ({col_str}) VALUES ({placeholder}) RETURNING *'
            cur.execute(sql, vals)
            result = cur.fetchone()
            if result:
                all_rows.append(dict(result))

        cur.close()
        return QueryResult(data=all_rows)


class UpdateQuery:
    def __init__(self, conn_factory, table, data):
        self._conn_factory = conn_factory
        self._table = table
        self._data = data
        self._conditions = []

    def eq(self, column, value):
        self._conditions.append((column, '=', value))
        return self

    def in_(self, column, values):
        self._conditions.append((column, 'in', tuple(values)))
        return self

    def execute(self):
        conn = self._conn_factory()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        set_cols = list(self._data.keys())
        set_vals = [self._data[c] for c in set_cols]
        set_str = ', '.join(f'"{c}" = %s' for c in set_cols)

        sql = f'UPDATE "{self._table}" SET {set_str}'
        params = list(set_vals)

        where_parts = []
        for col, op, val in self._conditions:
            if op == 'in':
                where_parts.append(f'"{col}" IN %s')
                params.append(val)
            else:
                where_parts.append(f'"{col}" {op} %s')
                params.append(val)

        if where_parts:
            sql += ' WHERE ' + ' AND '.join(where_parts)

        sql += ' RETURNING *'
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return QueryResult(data=rows)


class DeleteQuery:
    def __init__(self, conn_factory, table):
        self._conn_factory = conn_factory
        self._table = table
        self._conditions = []

    def eq(self, column, value):
        self._conditions.append((column, '=', value))
        return self

    def in_(self, column, values):
        self._conditions.append((column, 'in', tuple(values)))
        return self

    def execute(self):
        conn = self._conn_factory()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        sql = f'DELETE FROM "{self._table}"'
        params = []

        where_parts = []
        for col, op, val in self._conditions:
            if op == 'in':
                where_parts.append(f'"{col}" IN %s')
                params.append(val)
            else:
                where_parts.append(f'"{col}" {op} %s')
                params.append(val)

        if where_parts:
            sql += ' WHERE ' + ' AND '.join(where_parts)

        sql += ' RETURNING *'
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return QueryResult(data=rows)


class TableQuery:
    def __init__(self, conn_factory, table):
        self._conn_factory = conn_factory
        self._table = table

    def select(self, columns='*', count=None):
        return SelectQuery(self._conn_factory, self._table, columns, count_mode=count)

    def insert(self, data):
        return InsertQuery(self._conn_factory, self._table, data)

    def update(self, data):
        return UpdateQuery(self._conn_factory, self._table, data)

    def delete(self):
        return DeleteQuery(self._conn_factory, self._table)


class PostgresClient:
    """Drop-in replacement for supabase.Client using psycopg2.

    Usage:
        supabase = PostgresClient(database_url)
        result = supabase.table('videos').select('*').eq('id', '123').execute()
    """

    def __init__(self, database_url):
        self._database_url = database_url
        self._local = None  # Will use thread-local or Flask g

    def _get_conn(self):
        """Get or create a connection. Uses Flask g if available, else creates new."""
        try:
            from flask import g, has_app_context
            if has_app_context():
                if not hasattr(g, '_pg_conn') or g._pg_conn is None or g._pg_conn.closed:
                    g._pg_conn = psycopg2.connect(self._database_url)
                    g._pg_conn.autocommit = True
                return g._pg_conn
        except (ImportError, RuntimeError):
            pass
        # Fallback: new connection each time (for scripts, migrations, etc.)
        conn = psycopg2.connect(self._database_url)
        conn.autocommit = True
        return conn

    def table(self, name):
        return TableQuery(self._get_conn, name)

    def close(self):
        """Close the current connection if any."""
        try:
            from flask import g, has_app_context
            if has_app_context():
                conn = g.pop('_pg_conn', None)
                if conn and not conn.closed:
                    conn.close()
        except (ImportError, RuntimeError):
            pass
