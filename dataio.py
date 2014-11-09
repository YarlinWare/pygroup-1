#
# This program creates a python dictionary containing the data
# in the format needed for main.py
#
# Copyright (C) 2014,  Oscar Dowson
#
import pyodbc
import csv


class DataBase(object):
    """
    Class for managing database
    """

    def __init__(self, server, database, entity_data_table, variable_classification_table, uid=None, pwd=None):
        if uid is not None:
            # If password specified
            connection_string = 'DRIVER={SQL Server}; SERVER=%s;DATABASE=%s;UID=%s;PWD=%s' \
                                % (server, database, uid, pwd)
        else:
            # Otherwise
            connection_string = 'DRIVER={SQL Server}; SERVER=%s;DATABASE=%s' % (server, database)

        # Create connection
        self.con = pyodbc.connect(connection_string)

        # Create cursor
        self.cursor = self.con.cursor()

        # Classification of variables
        classification = self.get_categories(variable_classification_table)

        # Entity Data
        self.data = self.get_table(entity_data_table)

        # Categorical Variable Data
        self.categorical = self.get_category_levels(entity_data_table, classification)

        # Numerical Variable Data
        self.numerical = self.get_numerical_metrics(entity_data_table, classification)

        return

    def get_pk(self, table_name):
        """
        Returns list of primary keys associated with table
        :param table_name: name of table
        :return: list of tuples (pk_name, col_index)
        """

        pks = list()

        # Get list of primary keys
        self.cursor.primaryKeys(table_name)

        for pk in self.cursor.fetchall():
            # (database_name, schema, table_name, col_name, col_index, pk_name)
            pks.append(tuple([str(pk[-3]), pk[-2]]))
        return pks

    def get_table(self, table_name, where_clause=None):
        """
        Method for turning table into python dictionary
        :param table_name: name of table
        :param where_clause: optional clause to limit rows returned.
        i.e. where_clause='COLUMN1 > 5 and COLUMN2 <= 10'
        :return: dictionary[(tuple of pks)][column_name] = value
        """

        # Get list of primary keys associated with table
        pks = self.get_pk(table_name)

        data = dict()

        # Create sql command
        sql_command = "select * from %s" % table_name
        if where_clause is not None:
            sql_command += 'where ' + where_clause

        # Execute command
        self.cursor.execute(sql_command)

        # Get list of columns
        cols = [column[0] for column in self.cursor.description]

        for row in self.cursor.fetchall():
            # Create index
            if len(pks) <= 1:
                t = row[0]
            else:
                t = tuple([row[i-1] for s, i in pks])

            # add data
            data[t] = dict(zip(cols, row))
        return data

    def get_categories(self, table):
        """
        Gets list of categorical and numerical variables from table
        table must be in form table_name(Variable, IsCategorical)
        :param table: table containing data
        :return: dictionary containing lists of categorical and numerical variables
        """

        # Get table
        data = self.get_table(table)

        # Categories
        variables = {'categorical': list(), 'numerical': list()}
        for v in data:
            if int(data[v]['IsCategorical']) == 1:
                variables['categorical'].append(data[v]['Variable'])
            else:
                variables['numerical'].append(data[v]['Variable'])
        return variables

    def get_category_levels(self, table, variables):
        data = dict()
        for v in variables['categorical']:
            data[v] = list()
            sql_command = "select %s, count(1) from %s group by %s" % (v, table, v)
            for row in self.cursor.execute(sql_command):
                data[v].append((row[0], float(row[1])))
        return data

    def get_numerical_metrics(self, table, variables):
        data = dict()
        metrics = ['mean', 'var']
        for v in variables['numerical']:
            sql_command = "select avg(%s), var(%s) from %s" % (v, v, table)
            for row in self.cursor.execute(sql_command):
                data[v] = dict(zip(metrics, row))
        return data


class FlatFile(object):

    def __init__(self, classification_filepath, entity_filepath, delimiter="\t"):
        """

        :param classification_filepath:
        :param entity_filepath:
        :return:
        """
        self.classification_filepath = classification_filepath
        self.entity_filepath = entity_filepath
        self.delimiter = delimiter

        classification = self.get_categories()
        self.data = self.read_file(self.entity_filepath, classification)
        self.categorical = self.get_category_levels(classification)
        self.numerical = self.get_numerical_metrics(classification)
        return

    def get_categories(self):
        variables = {'categorical': list(), 'numerical': list()}
        with open(self.classification_filepath, 'r') as f:
            f.readline()
            while True:
                items = self.split_next_line(f)
                if items is None:
                    break
                if int(items[1]) == 1:
                    variables['categorical'].append(items[0])
                else:
                    variables['numerical'].append(items[0])
        return variables

    def split_next_line(self, f):
        line = f.readline()
        if not line:
            return None
        line = line.strip()
        items = csv.reader([line], delimiter=self.delimiter).next()
        return items

    def read_file(self, filename, classification):
        data = dict()
        with open(filename, 'r') as f:
            headers = self.split_next_line(f)
            while True:
                items = self.split_next_line(f)
                if items is None:
                    break
                data[items[0]] = dict(zip(headers, items))
        for v in classification['numerical']:
            for i in data:
                data[i][v] = float(data[i][v])
        return data

    def get_category_levels(self, classification):
        cat = dict()
        for c in classification['categorical']:
            cat[c] = dict()
        for i in self.data:
            for c in cat:
                if self.data[i][c] in cat[c]:
                    cat[c][self.data[i][c]] += 1
                else:
                    cat[c][self.data[i][c]] = 1
        categorical = dict()
        for c in cat:
            categorical[c] = list()
            for l in cat[c]:
                categorical[c].append((l, cat[c][l]))
        return categorical

    def get_numerical_metrics(self, classification):
        numerical = dict()
        for v in classification['numerical']:
            numerical[v] = {'mean': sum([self.data[i][v] for i in self.data]) / len(self.data)}
            numerical[v]['var'] = sum([pow(self.data[i][v] - numerical[v]['mean'], 2) for i in self.data])\
                / len(self.data)
        return numerical