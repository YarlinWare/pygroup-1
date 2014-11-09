#
# This program takes a set of entities and divides them into groups
# based on numerical and categorical variables
#
# Copyright (C) 2014,  Oscar Dowson
#
from pulp import *


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
        Model.__init__(self, name)
        self.df = model_data
        self.n_entities = len(self.df.data)
        self.entities = self.df.data.keys()
        self.variables = dict()
        self.groups, self.group_size = self.create_groups(n_groups, self.n_entities)
        tuples = dict()
        tuples['entity'] = [(e, g) for e in self.entities for g in self.groups]
        for c in self.df.categorical:
            tuples[c] = [(i, g) for (i, n) in self.df.categorical[c] for g in self.groups]

        self.create_variables(tuples)
        self.create_objective_function(tuples)
        self.create_entity_constraints()
        self.add_numerical_constraints()
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
        self.variables['x'] = LpVariable.dicts('x', tuples['entity'], None, None, LpBinary)
        for c in self.df.categorical:
            self.variables[c] = LpVariable.dicts('%s_violation' % c, tuples[c], 0, None)
        for v in self.df.numerical:
            self.variables[v] = dict()
            self.variables[v]['mean_min'] = LpVariable('%s_mean_min' % v, None, None)
            self.variables[v]['mean_max'] = LpVariable('%s_mean_max' % v, None, None)
            self.variables[v]['var_min'] = LpVariable('%s_var_min' % v, 0, None)
            self.variables[v]['var_max'] = LpVariable('%s_var_max' % v, 0, None)
        return

    def create_objective_function(self, tuples):
        obj = None
        for v in self.df.numerical:
            obj += (self.variables[v]['mean_max'] - self.variables[v]['mean_min']) / self.df.numerical[v]['mean']
            obj += (self.variables[v]['var_max'] - self.variables[v]['var_min']) / self.df.numerical[v]['var']
        for c in self.df.categorical:
            obj += 1e4 * lpSum([self.variables[c][i] for i in tuples[c]])
        self.model += obj
        return

    def create_entity_constraints(self):
        for e in self.entities:
            self.model += lpSum([self.variables['x'][(e, g)] for g in self.groups]) == 1, "entity_%s" % e
        return

    def add_numerical_constraints(self):
        for g in self.groups:
            self.model += lpSum([self.variables['x'][(i, g)] for i in self.df.data]) == self.group_size[g], '%s' % g
            for v in self.df.numerical:
                self.model += lpSum([self.df.data[i][v] * self.variables['x'][(i, g)] for i in self.df.data]) \
                    >= self.group_size[g] * self.variables[v]['mean_min']
                self.model += lpSum([self.df.data[i][v] * self.variables['x'][(i, g)] for i in self.df.data]) \
                    <= self.group_size[g] * self.variables[v]['mean_max']
                self.model += lpSum([pow(self.df.data[i][v] - self.df.numerical[v]['mean'], 2)
                                     * self.variables['x'][(i, g)] for i in self.df.data]) \
                    >= self.group_size[g] * self.variables[v]['var_min']
                self.model += lpSum([pow(self.df.data[i][v] - self.df.numerical[v]['mean'], 2)
                                     * self.variables['x'][(i, g)] for i in self.df.data]) \
                    <= self.group_size[g] * self.variables[v]['var_max']
        return

    def add_categorical_constraints(self):
        for g in self.groups:
            for c in self.df.categorical:
                for (l, n) in self.df.categorical[c]:
                    self.model += lpSum([self.variables['x'][(i, g)] for i in self.df.data if self.df.data[i][c] == l])\
                        + self.variables[c][(l, g)] >= int(n / self.n_entities * self.group_size[g])
                    self.model += lpSum([self.variables['x'][(i, g)] for i in self.df.data if self.df.data[i][c] == l])\
                        - self.variables[c][(l, g)] <= int(n / self.n_entities * self.group_size[g]) + 1
        return

    def extract_results(self):
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
        quality = {'numerical': self.get_numerical_solution_quality(allocation),
                   'categorical': self.get_categorical_solution_quality(allocation)}
        return quality

    def process_solution(self):
        allocation = self.extract_results()
        quality = self.get_solution_quality(allocation)
        return allocation, quality


class DistributionModel(Model):

    def __init__(self, old_population, new_population, n_people, name='DistributionModel'):
        Model.__init__(self, name)

        self.entities = new_population.data.keys()
        self.old_df = old_population
        self.new_df = new_population

        self.n_people = n_people

        self.variables = self.create_variables()
        self.create_objective_function()
        self.add_entity_constraints()
        self.add_numeric_constraints()
        self.add_categorical_constraints()
        return

    def create_variables(self):
        variables = dict()
        variables['x'] = LpVariable.dicts('x', self.entities, None, None, LpBinary)
        for c in self.new_df.categorical:
            variables[c] = LpVariable.dicts('%s_violation' % c, [a for a, b in self.new_df.categorical[c]], 0, None)
        for v in self.new_df.numerical:
            variables[v] = dict()
            variables[v]['mean_p'] = LpVariable('%s_mean_p' % v, 0, None)
            variables[v]['mean_n'] = LpVariable('%s_mean_n' % v, 0, None)
            variables[v]['var_p'] = LpVariable('%s_var_p' % v, 0, None)
            variables[v]['var_n'] = LpVariable('%s_var_n' % v, 0, None)
        return variables

    def create_objective_function(self):
        obj = None
        for v in self.new_df.numerical:
            obj += self.variables[v]['mean_p'] + self.variables[v]['mean_n']
            obj += self.variables[v]['var_p'] + self.variables[v]['var_n']
        obj += 1e4 * lpSum([self.variables[c] for c in self.new_df.categorical])
        self.model += obj
        return

    def add_entity_constraints(self):
        self.model += lpSum([self.variables['x'][i] for i in self.entities]) == self.n_people
        return

    def add_numeric_constraints(self):
        for v in self.new_df.numerical:
            self.model += lpSum([self.new_df.data[i][v] * self.variables['x'][i] for i in self.new_df.data]) \
                / self.n_people - self.old_df.numerical[v]["mean"] \
                == self.variables[v]['mean_p'] - self.variables[v]['mean_n']
            self.model += lpSum([pow(self.new_df.data[i][v] - self.new_df.numerical[v]['mean'], 2)
                                * self.variables['x'][i] for i in self.new_df.data]) / self.n_people - \
                self.old_df.numerical[v]['var'] \
                == self.variables[v]['var_p'] - self.variables[v]['var_n']
        return

    def add_categorical_constraints(self):
        for c in self.new_df.categorical:
            for (l, n) in self.new_df.categorical[c]:
                m = self.old_df.categorical[c][1]
                self.model += lpSum([self.variables['x'][i] for i in self.new_df.data if self.new_df.data[i][c] == l])\
                    + self.variables[c][l] >= int(m * self.n_people)
                self.model += lpSum([self.variables['x'][i] for i in self.new_df.data if self.new_df.data[i][c] == l])\
                    - self.variables[c][l] <= int(m * self.n_people) + 1
        return

    def extract_results(self):
        return [i for i in self.variables['x'] if self.variables['x'][i].value() == 1]

    def get_numerical_solution_quality(self):
        quality = dict()
        for v in self.new_df.numerical:
            quality[v] = dict()
            quality[v]['mean'] = self.variables[v]['mean_p'] + self.variables[v]['mean_n']
            quality[v]['var'] = self.variables[v]['var_p'] + self.variables[v]['var_n']
        return quality

    def get_categorical_solution_quality(self):
        quality = dict()
        for c in self.new_df.categorical:
            quality[c] = dict()
            for (l, n) in self.new_df.categorical[c]:
                quality[c][l] = self.new_df.variables[c][l].value()
        return quality

    def get_solution_quality(self):
        quality = {
            'numerical': self.get_numerical_solution_quality(),
            'categorical': self.get_categorical_solution_quality()}
        return quality

    def process_solution(self):
        allocation = self.extract_results()
        quality = self.get_solution_quality()
        return allocation, quality
