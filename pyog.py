#
# This program takes a set of entities and divides them into groups
# based on numerical and categorical variables
#
# Copyright (C) 2014,  Oscar Dowson
#
from pulp import *
import pyodbc
import csv


class Model(object):

    def __init__(self, name):
        self.model = LpProblem(name, LpMinimize)
        return

    @staticmethod
    def mean(x):
        return sum(x) / float(len(x))

    def var(self, x, u=None):
        if u is None:
            u = self.mean(x)
        return sum([pow(i - u, 2) for i in x]) / len(x)

    def solve(self, time_limit):
        try:
            # New PuLP needs this
            self.model.solve(solvers.COIN_CMD(maxSeconds=time_limit))
        except solvers.PulpSolverError:
            # Old PuLP needs this
            self.model.solve(solvers.PULP_CBC_CMD(maxSeconds=time_limit))
        return self.process_solution()

    def process_solution(self):
        raise NotImplementedError


class PartitionModel(Model):

    def __init__(self, model_data, n_groups, name='PartitionModel'):
        """

        :param model_data: data class
        :param n_groups: number of groups to partition into
        :param name: model name (optional)
        :return:
        """

        # Inherits Model class
        Model.__init__(self, name)

        self.df = model_data

        # Number of entities
        self.n_entities = len(self.df.data)

        # List of entities
        self.entities = self.df.data.keys()

        self.variables = dict()

        # Create groups
        self.groups, self.group_size = self.create_groups(n_groups, self.n_entities)

        # List of tuple indices
        tuples = dict()
        tuples['entity'] = [(e, g) for e in self.entities for g in self.groups]
        for c in self.df.categorical:
            tuples[c] = [(i, g) for (i, n) in self.df.categorical[c] for g in self.groups]

        # Add variables
        self.create_variables(tuples)

        # Add objective function
        self.create_objective_function(tuples)

        # Add entity constraints
        self.create_entity_constraints()

        # Add numerical variable constraints
        self.add_numerical_constraints()

        # Add categorical variable constraints
        self.add_categorical_constraints()

        return

    @staticmethod
    def create_groups(n_groups, n_entities):
        groups = range(1, n_groups + 1)
        # Number of groups with floor(n_entities/n_groups) people
        k = n_groups - int(n_entities - int(n_entities / n_groups) * n_groups)
        group_size = dict()
        for g in groups:
            if g <= k:
                group_size[g] = int(n_entities / n_groups)
            else:
                group_size[g] = int(n_entities / n_groups) + 1
        return groups, group_size

    def create_variables(self, tuples):
        """

        :param tuples:
        :return:
        """

        # Entity allocation variables
        self.variables['x'] = LpVariable.dicts('x', tuples['entity'], None, None, LpBinary)

        for c in self.df.categorical:
            # Penalty variables for violating categorical constraints
            self.variables[c] = LpVariable.dicts('%s_violation' % c, tuples[c], 0, None)

        for v in self.df.numerical:
            # Numerical variables
            self.variables[v] = dict()

            # Smallest mean
            self.variables[v]['mean_min'] = LpVariable('%s_mean_min' % v, None, None)

            # Largest mean
            self.variables[v]['mean_max'] = LpVariable('%s_mean_max' % v, None, None)

            # Smallest variance
            self.variables[v]['var_min'] = LpVariable('%s_var_min' % v, 0, None)

            # Largest variance
            self.variables[v]['var_max'] = LpVariable('%s_var_max' % v, 0, None)
        return

    def create_objective_function(self, tuples):
        """

        :param tuples:
        :return:
        """

        obj = None

        for v in self.df.numerical:
            # Minimise mean and variance range
            obj += (self.variables[v]['mean_max'] - self.variables[v]['mean_min']) / self.df.numerical[v]['mean']
            obj += (self.variables[v]['var_max'] - self.variables[v]['var_min']) / self.df.numerical[v]['var']

            # TODO: weightings on variables

        for c in self.df.categorical:
            # Penalise violations
            obj += 1e4 * lpSum([self.variables[c][i] for i in tuples[c]])

            # TODO: weightings on violations

        # Add to model
        self.model += obj

        return

    def create_entity_constraints(self):
        """

        :return:
        """

        for e in self.entities:
            # Each entity can be assigned to one group
            self.model += lpSum([self.variables['x'][(e, g)] for g in self.groups]) == 1, "entity_%s" % e

        return

    def add_numerical_constraints(self):
        """

        :return:
        """

        for g in self.groups:
            # Each group must contain a certain number of people
            self.model += lpSum([self.variables['x'][(i, g)] for i in self.df.data]) == self.group_size[g], '%s' % g

            for v in self.df.numerical:
                # Each mean must be bigger than some L.B.
                self.model += lpSum([self.df.data[i][v] * self.variables['x'][(i, g)] for i in self.df.data]) \
                    >= self.group_size[g] * self.variables[v]['mean_min']

                # Each mean must be smaller than some U.B.
                self.model += lpSum([self.df.data[i][v] * self.variables['x'][(i, g)] for i in self.df.data]) \
                    <= self.group_size[g] * self.variables[v]['mean_max']

                # Each variance must be bigger than some L.B.
                #
                #   Note: This is an approximation of the variance as we use global mean rather than
                #       the sample mean (as this would be non-linear)
                self.model += lpSum([pow(self.df.data[i][v] - self.df.numerical[v]['mean'], 2)
                                     * self.variables['x'][(i, g)] for i in self.df.data]) \
                    >= self.group_size[g] * self.variables[v]['var_min']

                # Each variance must be smaller than some U.B.
                self.model += lpSum([pow(self.df.data[i][v] - self.df.numerical[v]['mean'], 2)
                                     * self.variables['x'][(i, g)] for i in self.df.data]) \
                    <= self.group_size[g] * self.variables[v]['var_max']

        return

    def add_categorical_constraints(self):
        """
        Adds the categorical constraints
        :return:
        """

        # For each group
        for g in self.groups:
            # For each categorical variable
            for c in self.df.categorical:
                # For each level in that variable
                for (l, n) in self.df.categorical[c]:
                    # L.B.
                    self.model += lpSum([self.variables['x'][(i, g)] for i in self.df.data if self.df.data[i][c] == l])\
                        + self.variables[c][(l, g)] >= int(n * self.group_size[g])

                    # U.B.
                    self.model += lpSum([self.variables['x'][(i, g)] for i in self.df.data if self.df.data[i][c] == l])\
                        - self.variables[c][(l, g)] <= int(n * self.group_size[g]) + 1

        return

    def extract_results(self):
        """

        :return:
        """

        allocation = {'entity-group': dict(), 'group-entity': dict()}

        for (e, g) in self.variables['x']:

            if self.variables['x'][(e, g)].value() == 1:

                allocation['entity-group'][e] = g

                if g not in allocation['group-entity']:
                    allocation['group-entity'][g] = [e]
                else:
                    allocation['group-entity'][g].append(e)

        return allocation

    def get_numerical_solution_quality(self, allocation):
        """

        :param allocation:
        :return:
        """

        quality = dict()

        for v in self.df.numerical:
            quality[v] = {'mean': {'max': None, 'min': None, 'mean': None, 'sd': None},
                          'var': {'max': None, 'min': None, 'mean': None, 'sd': None}}
            mean_list = list()
            var_list = list()

            for g in allocation['group-entity']:

                values = [self.df.data[e][v] for e in allocation['group-entity'][g]]

                mean_list.append(self.mean(values))
                var_list.append(self.var(values, mean_list[-1]))

            # Add statistical metrics
            quality[v]['mean']['max'] = max(mean_list)
            quality[v]['mean']['min'] = min(mean_list)
            quality[v]['mean']['mean'] = self.mean(mean_list)
            quality[v]['mean']['sd'] = pow(self.var(mean_list), 0.5)
            quality[v]['var']['max'] = max(var_list)
            quality[v]['var']['min'] = min(var_list)
            quality[v]['var']['mean'] = self.mean(var_list)
            quality[v]['var']['sd'] = pow(self.var(var_list), 0.5)
        return quality

    def get_categorical_solution_quality(self, allocation):
        """

        :param allocation:
        :return:
        """

        quality = dict()

        for c in self.df.categorical:

            quality[c] = dict()

            for (l, n) in self.df.categorical[c]:

                quality[c][l] = {'max': None, 'min': None, 'mean': None, 'sd': None}

                violation_list = [self.variables[c][(l, g)].value() for g in allocation['group-entity']]

                quality[c][l]['max'] = max(violation_list)
                quality[c][l]['min'] = min(violation_list)
                quality[c][l]['mean'] = self.mean(violation_list)
                quality[c][l]['sd'] = pow(self.var(violation_list), 0.5)
        return quality

    def get_solution_quality(self, allocation):
        """

        :param allocation:
        :return:
        """
        quality = {'numerical': self.get_numerical_solution_quality(allocation),
                   'categorical': self.get_categorical_solution_quality(allocation)}
        return quality

    def process_solution(self):
        """

        :return:
        """
        allocation = self.extract_results()
        quality = self.get_solution_quality(allocation)
        return allocation, quality


class DistributionModel(Model):

    def __init__(self, old_population, new_population, n_people, name='DistributionModel'):
        """
        Instantiates DistributionModel
        :param old_population: data for population we wish to match
        :param new_population: data for population we draw entities from
        :param n_people: number of entities to select from new_population
        :param name: name of match
        :return:
        """

        # Inherits Model class
        Model.__init__(self, name)

        # list of entities
        self.entities = new_population.data.keys()

        # Control population (trying to match)
        self.old_df = old_population

        # New population (drawing from)
        self.new_df = new_population

        # number of people to select from new population
        self.n_people = n_people

        # Add the variables
        self.variables = self.create_variables()

        # add the objective function
        self.create_objective_function()

        # Add the entity constraints
        self.add_entity_constraints()

        # Add the numeric constraints
        self.add_numeric_constraints()

        # Add the categorical constraints
        self.add_categorical_constraints()

        return

    def create_variables(self):
        """
        Add the variables to the model
        :return:
        """

        variables = dict()

        # Entity variables
        variables['x'] = LpVariable.dicts('x', self.entities, None, None, LpBinary)

        # Categorical variables
        for c in self.new_df.categorical:
            variables[c] = LpVariable.dicts('%s_violation' % c, [a for a, b in self.new_df.categorical[c]], 0, None)

        # Numerical variables
        for v in self.new_df.numerical:
            variables[v] = dict()
            variables[v]['mean_p'] = LpVariable('%s_mean_p' % v, 0, None)
            variables[v]['mean_n'] = LpVariable('%s_mean_n' % v, 0, None)
            variables[v]['var_p'] = LpVariable('%s_var_p' % v, 0, None)
            variables[v]['var_n'] = LpVariable('%s_var_n' % v, 0, None)
        return variables

    def create_objective_function(self):
        """
        Add objective function
        :return:
        """

        obj = None

        for v in self.new_df.numerical:
            # Difference between means of each population
            obj += self.variables[v]['mean_p'] + self.variables[v]['mean_n']

            # Difference between the variance of each population
            obj += self.variables[v]['var_p'] + self.variables[v]['var_n']

        # Penalise violations
        obj += 1e4 * lpSum([self.variables[c] for c in self.new_df.categorical])

        # TODO: weightings on variables

        # Add to model
        self.model += obj

        return

    def add_entity_constraints(self):
        """
        Adds entity constraints to model
        :return:
        """

        self.model += lpSum([self.variables['x'][i] for i in self.entities]) == self.n_people

        return

    def add_numeric_constraints(self):
        """
        Add the numeric constraints
        :return:
        """

        # For each numeric variable
        for v in self.new_df.numerical:
            # Make the means similar
            self.model += lpSum([self.new_df.data[i][v] * self.variables['x'][i] for i in self.new_df.data]) \
                / self.n_people - self.old_df.numerical[v]["mean"] \
                == self.variables[v]['mean_p'] - self.variables[v]['mean_n']

            # Make the variances similar
            self.model += lpSum([pow(self.new_df.data[i][v] - self.new_df.numerical[v]['mean'], 2)
                                * self.variables['x'][i] for i in self.new_df.data]) / self.n_people - \
                self.old_df.numerical[v]['var'] \
                == self.variables[v]['var_p'] - self.variables[v]['var_n']

        return

    @staticmethod
    def get_proportion(my_list, level):
        """
        gets proportion from list of tuples (level, proportion)
        :param my_list: list of tuples from categorical variable
        :param level: level of categorical variable
        :return: proportion
        """

        # For each tuple in list
        for l, n in my_list:
            if level == l:
                # Return proportion
                return n

        # Level not in list
        return 0.0

    def add_categorical_constraints(self):
        """
        Add categorical constraints
        :return:
        """

        # For each categorical variable
        for c in self.new_df.categorical:
            # For each level in that variable
            for (l, n) in self.new_df.categorical[c]:
                # Goal proportion
                m = self.get_proportion(self.old_df.categorical[c], l)

                # L.B.
                self.model += lpSum([self.variables['x'][i] for i in self.new_df.data if self.new_df.data[i][c] == l])\
                    + self.variables[c][l] >= int(m * self.n_people)

                # U.B.
                self.model += lpSum([self.variables['x'][i] for i in self.new_df.data if self.new_df.data[i][c] == l])\
                    - self.variables[c][l] <= int(m * self.n_people) + 1

        return

    def extract_results(self):
        """
        Get assignment
        :return:
        """
        return [i for i in self.variables['x'] if self.variables['x'][i].value() == 1]

    def get_numerical_solution_quality(self):
        """
        Get statistical metrics about numerical variables
        :return:
        """

        quality = dict()

        for v in self.new_df.numerical:

            quality[v] = dict()

            quality[v]['mean'] = self.variables[v]['mean_p'].value() + self.variables[v]['mean_n'].value()
            quality[v]['var'] = self.variables[v]['var_p'].value() + self.variables[v]['var_n'].value()

        return quality

    def get_categorical_solution_quality(self):
        """
        Get statistical metrics of categorical solution quality
        :return:
        """

        quality = dict()

        for c in self.new_df.categorical:
            quality[c] = dict()

            for (l, n) in self.new_df.categorical[c]:
                quality[c][l] = self.variables[c][l].value()

        return quality

    def get_solution_quality(self):
        """
        get quality report
        :return:
        """

        return {
            'numerical': self.get_numerical_solution_quality(),
            'categorical': self.get_categorical_solution_quality()}

    def process_solution(self):
        """
        get results and build quality report
        :return:
        """

        allocation = self.extract_results()
        quality = self.get_solution_quality()

        return allocation, quality

# ===================================================================================================================
# ===================================================================================================================
# ===================================================================================================================
# ===================================================================================================================


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

        table_data = dict()

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
            table_data[row[0]] = dict(zip(cols[1:], row[1:]))

        return table_data

    def get_categories(self, table):
        """
        Gets list of categorical and numerical variables from table
        table must be in form table_name(Variable, IsCategorical)
        :param table: table containing data
        :return: dictionary containing lists of categorical and numerical variables
        """

        # Get table
        category_data = self.get_table(table)

        # Categories
        variables = {'categorical': list(), 'numerical': list()}
        for v in category_data:
            if int(category_data[v]['IsCategorical']) == 1:
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

        category_data = dict()

        # For each categorical variable
        for v in categorical_variables:

            category_data[v] = list()

            # SQL query to get counts
            sql_command = "select %s, count(1) from %s group by %s" % (v, table, v)

            # For each level
            for row in self.cursor.execute(sql_command):
                # Add data (level, proportion)
                category_data[v].append((row[0], float(row[1]) / n))

        return category_data

    def get_numerical_metrics(self, table, numerical_variables):
        """
        Get the numerical metrics for data
        :param table:   name of entity table
        :param numerical_variables: list of numerical variables
        :return:
        """

        numeric_data = dict()

        # Get the mean and variance of each variable
        metrics = ['mean', 'var']

        for v in numerical_variables:
            # SQL Query to get mean and variance of each variable
            sql_command = "select avg(%s), var(%s) from %s" % (v, v, table)

            # This should only return one row
            for row in self.cursor.execute(sql_command):
                # Zip into dictionary item
                numeric_data[v] = dict(zip(metrics, row))

        return numeric_data


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

        file_data = dict()

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
                file_data[items[0]] = dict(zip(headers, items))

        # make sure numerical variables are floats instead of strings
        for v in numerical_variables:
            for i in file_data:
                file_data[i][v] = float(data[i][v])

        return file_data

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
