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

    def __init__(self, server, database, entity_table, classification_table,
                 uid=None, pwd=None, where=None):
        """
        Instantiate database class
        :param server: location of SQL server
        :param database: name of SQL database
        :param entity_table: name of entity table in SQL database
            entity_table(ID, var1, var2, var3, ... )
        :param classification_table: name of classification table in SQL database
            classification_table(Variable, IsCategorical)
            Variable = Name of variable
            IsCategorical = 0 if numerical, 1 if categorical
        :param uid: username for SQL database
        :param pwd: password for SQL database
        :param where: optional where clause for selecting entity data
        :return: instance of database class
        """
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
        classification = self.get_categories(classification_table)

        # Entity Data
        self.data = self.get_table(entity_table, where_clause=where)

        # Categorical Variable Data
        self.categorical = self.get_category_levels(entity_table, classification['categorical'])

        # Numerical Variable Data
        self.numerical = self.get_numerical_metrics(entity_table, classification['numerical'])

        return

    def get_table(self, table_name, where_clause=None):
        """
        Method for turning table into python dictionary
        :param table_name: name of table
        :param where_clause: optional clause to limit rows returned.
        i.e. where_clause='COLUMN1 > 5 and COLUMN2 <= 10'
        :return: dictionary[(tuple of pks)][column_name] = value
        """

        data = dict()

        # Create sql command
        sql_command = "select * from %s" % table_name
        if where_clause is not None:
            sql_command += ' where ' + where_clause

        # Execute command
        self.cursor.execute(sql_command)

        # Get list of columns
        cols = [column[0] for column in self.cursor.description]

        for row in self.cursor.fetchall():
            # add data
            data[row[0]] = dict(zip(cols[1:], row[1:]))
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
                # Add categorical variable
                variables['categorical'].append(v)
            else:
                # Add numerical variable
                variables['numerical'].append(v)
        return variables

    def get_category_levels(self, table, categorical_variables):
        """
        This function gets a list of levels and proportions for each categorical variable
        :param table:   name of entity table
        :param categorical_variables: list of categorical variables
        :return: dictionary[categorical] = list of tuples (level, proportion)
        """

        # Number of entities
        n = len(self.data)

        data = dict()

        # For each categorical variable
        for v in categorical_variables:

            data[v] = list()

            # SQL query to get counts
            sql_command = "select %s, count(1) from %s group by %s" % (v, table, v)

            # For each level
            for row in self.cursor.execute(sql_command):
                # Add data (level, proportion)
                data[v].append((row[0], float(row[1]) / n))

        return data

    def get_numerical_metrics(self, table, numerical_variables):
        """
        Get the numerical metrics for data
        :param table:   name of entity table
        :param numerical_variables: list of numerical variables
        :return:
        """

        data = dict()

        # Get the mean and variance of each variable
        metrics = ['mean', 'var']

        for v in numerical_variables:
            # SQL Query to get mean and variance of each variable
            sql_command = "select avg(%s), var(%s) from %s" % (v, v, table)

            # This should only return one row
            for row in self.cursor.execute(sql_command):
                # Zip into dictionary item
                data[v] = dict(zip(metrics, row))

        return data


class FlatFile(object):

    def __init__(self, classification_filepath, entity_filepath, delimiter="\t"):
        """
        Instantiate FlatFile class
        :param classification_filepath: full filepath of classification text file
        :param entity_filepath: full filepath of entity text file
        :return:
        """

        # Classification filepath
        self.classification_filepath = classification_filepath

        # Entitiy filepath
        self.entity_filepath = entity_filepath

        # Delimiter to use
        self.delimiter = delimiter

        # Get categories
        classification = self.get_categories()

        # Get data
        self.data = self.read_file(self.entity_filepath, classification['numerical'])

        # Get categorical variable data
        self.categorical = self.get_category_levels(classification['categorical'])

        # Get numerical variable data
        self.numerical = self.get_numerical_metrics(classification['numerical'])
        return

    def get_categories(self):
        """

        :return:
        """
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
        """
        Read next line, parse and split into list
        :param f: file pointer
        :return: list of values
        """

        # get next line
        line = f.readline()

        if not line:
            # EOF
            return None

        # Get rid of new line characters etc
        line = line.strip()

        # Split into items
        items = csv.reader([line], delimiter=self.delimiter).next()

        return items

    def read_file(self, filename, numerical_variables):
        """
        This function reads a csv and turns it into a dictionary, indexed by first column
        :param filename: full filepath of file
        :param numerical_variables: list of numerical variable names
        :return: dictionary[index][variable] = value
        """

        data = dict()

        with open(filename, 'r') as f:

            # Read headers
            headers = self.split_next_line(f)

            while True:
                # Get next line
                items = self.split_next_line(f)

                if items is None:
                    # EOF
                    break

                # Zip into dictionary
                data[items[0]] = dict(zip(headers, items))

        # make sure numerical variables are floats instead of strings
        for v in numerical_variables:
            for i in data:
                data[i][v] = float(data[i][v])

        return data

    def get_category_levels(self, categorical_variables):
        """

        :param categorical_variables: list of categorical variables
        :return: dictionary[variable] = list of tuples (level, proportion)
        """

        cat = dict()
        for c in categorical_variables:
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

    def get_numerical_metrics(self, numerical_variables):
        """
        Calculates the mean and variance of each numerical variable
        :param numerical_variables: list of numerical variables
        :return: dictionary[variable][metric (mean/var)] = value
        """

        numerical = dict()

        # For each numerical variable
        for v in numerical_variables:

            # calculate the mean
            numerical[v] = {'mean': sum([self.data[i][v] for i in self.data]) / len(self.data)}

            # calculate the variance
            numerical[v]['var'] = sum([pow(self.data[i][v] - numerical[v]['mean'], 2) for i in self.data])\
                / len(self.data)

        return numerical