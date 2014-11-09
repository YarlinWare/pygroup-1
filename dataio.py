#
# This program creates a python dictionary containing the data
# in the format needed for main.py
#
# Copyright (C) 2014,  Oscar Dowson
#
import pyodbc
import csv


class DataBase():
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


def grab_ff_categories(filename, delimiter='\t'):
    variables = {'categorical': list(), 'numerical': list()}
    with open(filename, 'r') as f:
        f.readline()
        while True:
            items = split_next_line(f, delimiter)
            if items is None:
                break
            if int(items[1]) == 1:
                variables['categorical'].append(items[0])
            else:
                variables['numerical'].append(items[0])
    return variables


def split_next_line(f, delimiter):
    line = f.readline()
    if not line:
        return None
    line = line.strip()
    return csv.reader([line], delimiter).next()


def build_ff_data_dictionary(filename, classification):
    data = dict()
    with open(filename, 'r') as f:
        headers = split_next_line(f, '\t')
        while True:
            items = split_next_line(f, '\t')
            if items is None:
                break
            data[items[0]] = dict(zip(headers, items))
    for v in classification['numerical']:
        for i in data:
            data[i][v] = float(data[i][v])
    return data


def get_ff_category_levels(data, variables):
    cat = dict()
    for c in variables['categorical']:
        cat[c] = dict()
    for i in data:
        for c in cat:
            if data[i][c] in cat[c]:
                cat[c][data[i][c]] += 1
            else:
                cat[c][data[i][c]] = 1
    categorical = dict()
    for c in cat:
        categorical[c] = list()
        for l in cat[c]:
            categorical[c].append((l, cat[c][l]))
    return categorical


def get_ff_numerical_metrics(data, variables):
    numerical = dict()
    for v in variables['numerical']:
        numerical[v] = {'mean': sum([data[i][v] for i in data]) / len(data)}
        numerical[v]['var'] = sum([pow(data[i][v] - numerical[v]['mean'], 2) for i in data]) / len(data)
    return numerical


def get_data_from_flatfiles(classification_filepath, entity_filepath):
    classification = grab_ff_categories(classification_filepath)
    entity_data = build_ff_data_dictionary(entity_filepath, classification)
    categorical = get_ff_category_levels(entity_data, classification)
    numerical = get_ff_numerical_metrics(entity_data, classification)
    ff_data = dict()
    ff_data['entity_data'] = entity_data
    ff_data['categorical_data'] = categorical
    ff_data['numerical_data'] = numerical
    return ff_data
