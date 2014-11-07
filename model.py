#
# This program takes a set of entities and divides them into groups
# based on numerical and categorical variables
#
# Copyright (C) 2014,  Oscar Dowson
#
from pulp import *


#
# This section deals with partitioning entities into equitable groups
#
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


def create_variables(categorical, numerical, tuples):
    variables = dict()
    variables['x'] = LpVariable.dicts('x', tuples['entity'], None, None, LpBinary)
    for c in categorical:
        variables[c] = LpVariable.dicts('%s_violation' % c, tuples[c], 0, None)
    for v in numerical:
        variables[v] = dict()
        variables[v]['mean_min'] = LpVariable('%s_mean_min' % v, None, None)
        variables[v]['mean_max'] = LpVariable('%s_mean_max' % v, None, None)
        variables[v]['var_min'] = LpVariable('%s_var_min' % v, 0, None)
        variables[v]['var_max'] = LpVariable('%s_var_max' % v, 0, None)
    return variables


def create_objective_function(model, variables, categorical, numerical, tuples):
    obj = None
    for v in numerical:
        obj += (variables[v]['mean_max'] - variables[v]['mean_min']) / numerical[v]['mean']
        obj += (variables[v]['var_max'] - variables[v]['var_min']) / numerical[v]['var']
    for c in categorical:
        obj += 1e4 * lpSum([variables[c][i] for i in tuples[c]])
    model += obj
    return model


def create_entity_constraints(model, variables, entities, groups):
    for e in entities:
        model += lpSum([variables['x'][(e, g)] for g in groups]) == 1, "entity_%s" % e
    return model


def add_numerical_constraints(model, df, variables, numerical, groups, group_size):
    for g in groups:
        model += lpSum([variables['x'][(i, g)] for i in df]) == group_size[g], '%s' % g
        for v in numerical:
            model += lpSum([df[i][v] * variables['x'][(i, g)] for i in df]) \
                >= group_size[g] * variables[v]['mean_min']
            model += lpSum([df[i][v] * variables['x'][(i, g)] for i in df]) \
                <= group_size[g] * variables[v]['mean_max']
            model += lpSum([pow(df[i][v] - numerical[v]['mean'], 2) * variables['x'][(i, g)] for i in df]) \
                >= group_size[g] * variables[v]['var_min']
            model += lpSum([pow(df[i][v] - numerical[v]['mean'], 2) * variables['x'][(i, g)] for i in df]) \
                <= group_size[g] * variables[v]['var_max']
    return model


def add_categorical_constraints(model, df, variables, categorical, groups, n_entities, group_size):
    for g in groups:
        for c in categorical:
            for (l, n) in categorical[c]:
                model += lpSum([variables['x'][(i, g)] for i in df if df[i][c] == l]) + variables[c][(l, g)] >= int(
                    n / n_entities * group_size[g])
                model += lpSum([variables['x'][(i, g)] for i in df if df[i][c] == l]) - variables[c][(l, g)] <= int(
                    n / n_entities * group_size[g]) + 1
    return model


def create_problem(db_data, n_groups):
    df = db_data['entity_data']
    categorical = db_data['categorical_data']
    numerical = db_data['numerical_data']
    n_entities = len(df)
    entities = df.keys()

    groups, group_size = create_groups(n_groups, n_entities)
    tuples = dict()
    tuples['entity'] = [(e, g) for e in entities for g in groups]
    for c in categorical:
        tuples[c] = [(i, g) for (i, n) in categorical[c] for g in groups]

    model = LpProblem('Partition', LpMinimize)
    variables = create_variables(categorical, numerical, tuples)
    model = create_objective_function(model, variables, categorical, numerical, tuples)
    model = create_entity_constraints(model, variables, entities, groups)
    model = add_numerical_constraints(model, df, variables, numerical, groups, group_size)
    model = add_categorical_constraints(model, df, variables, categorical, groups, n_entities, group_size)
    return model, variables


def extract_results(variables):
    allocation = {'entity-group': dict(), 'group-entity': dict()}
    for (e, g) in variables['x']:
        if variables['x'][(e, g)].value() == 1:
            allocation['entity-group'][e] = g
            if g not in allocation['group-entity']:
                allocation['group-entity'][g] = list(e)
            else:
                allocation['group-entity'][g].append(e)
    return allocation


def get_numerical_solution_quality(allocation, df, numerical):
    quality = dict()
    for v in numerical:
        quality[v] = {'mean': {'max': None, 'min': None, 'mean': None, 'sd': None},
                      'var': {'max': None, 'min': None, 'mean': None, 'sd': None}}
        mean_list = list()
        var_list = list()
        for g in allocation['group-entity']:
            values = [df[e][v] for e in allocation['group-entity'][g]]
            mean_list.append(mean(values))
            var_list.append(var(values, mean_list[-1]))
        quality[v]['mean']['max'] = max(mean_list)
        quality[v]['mean']['min'] = min(mean_list)
        quality[v]['mean']['mean'] = mean(mean_list)
        quality[v]['mean']['sd'] = pow(var(mean_list), 0.5)
        quality[v]['var']['max'] = max(var_list)
        quality[v]['var']['min'] = min(var_list)
        quality[v]['var']['mean'] = mean(var_list)
        quality[v]['var']['sd'] = pow(var(var_list), 0.5)
    return quality


def get_categorical_solution_quality(allocation, variables, categorical):
    quality = dict()
    for c in categorical:
        quality[c] = dict()
        for (l, n) in categorical[c]:
            quality[c][l] = {'max': None, 'min': None, 'mean': None, 'sd': None}
            violation_list = [variables[c][(l, g)].value() for g in allocation['group-entity']]
            quality[c][l]['max'] = max(violation_list)
            quality[c][l]['min'] = min(violation_list)
            quality[c][l]['mean'] = mean(violation_list)
            quality[c][l]['sd'] = pow(var(violation_list), 0.5)
    return quality


def get_solution_quality(allocation, df, variables):
    quality = {'numerical': get_numerical_solution_quality(allocation, df['entity_data'], df['numerical_data']),
               'categorical': get_categorical_solution_quality(allocation, variables, df['categorical_data'])}
    return quality


def mean(x):
    return sum(x) / float(len(x))


def var(x, u=None):
    if u is None:
        u = mean(x)
    return sum([pow(i - u, 2) for i in x]) / len(x)


def partition_entities(df, n_groups, time_limit):
    model, variables = create_problem(df, n_groups)
    try:
        # New PuLP needs this
        model.solve(solvers.COIN_CMD(maxSeconds=time_limit))
    except:
        # Old PuLP needs this
        model.solve(solvers.PULP_CBC_CMD(maxSeconds=time_limit))
    allocation = extract_results(variables)
    quality = get_solution_quality(allocation, df, variables)
    return allocation, quality


#
# Now we want to choose n people that match a distribution as closely as possible
#
def create_distribution_problem(db_data, n_people):
    df = db_data['entity_data']
    categorical = db_data['categorical_data']
    numerical = db_data['numerical_data']
    entities = df.keys()

    model = LpProblem('Distribution', LpMinimize)
    variables = create_distribution_variables(categorical, numerical, entities)
    model = create_distribution_objective_function(model, variables, categorical, numerical)
    model = add_distribution_entity_constraints(model, variables, entities, n_people)
    model = add_distribution_numeric_constraints(model, data, variables, numerical, n_people)
    model = add_distribution_categorical_constraints(model, data, variables, categorical, n_people)
    return model, variables


def create_distribution_variables(categorical, numerical, entities):
    variables = dict()
    variables['x'] = LpVariable.dicts('x', entities, None, None, LpBinary)
    for c in categorical:
        variables[c] = LpVariable.dicts('%s_violation' % c, [a for a, b in categorical[c]], 0, None)
    for v in numerical:
        variables[v] = dict()
        variables[v]['mean_p'] = LpVariable('%s_mean_p' % v, 0, None)
        variables[v]['mean_n'] = LpVariable('%s_mean_n' % v, 0, None)
        variables[v]['var_p'] = LpVariable('%s_var_p' % v, 0, None)
        variables[v]['var_n'] = LpVariable('%s_var_n' % v, 0, None)
    return variables


def create_distribution_objective_function(model, variables, categorical, numerical):
    obj = None
    for v in numerical:
        obj += variables[v]['mean_p'] + variables[v]['mean_n']
        obj += variables[v]['var_p'] + variables[v]['var_n']
    obj += 1e4 * lpSum([variables[c] for c in categorical])
    model += obj
    return model


def add_distribution_entity_constraints(model, variables, entities, n):
    model += lpSum([variables['x'][i] for i in entities]) == n
    return model


def add_distribution_numeric_constraints(model, df, variables, numerical, n_people):
    for v in numerical:
        model += lpSum([df[i][v] * variables['x'][i] for i in df]) / n_people - numerical[v]["mean"] == \
            variables[v]['mean_p'] - variables[v]['mean_n']
        model += lpSum([pow(df[i][v] - numerical[v]['mean'], 2) * variables['x'][i] for i in df]) / n_people - \
            numerical[v]['var'] == variables[v]['var_p'] - variables[v]['var_n']
    return model


def add_distribution_categorical_constraints(model, df, variables, categorical, n_people):
    for c in categorical:
        for (l, n) in categorical[c]:
            model += lpSum([variables['x'][i] for i in df if df[i][c] == l]) + variables[c][l] \
                >= int(n * n_people)
            model += lpSum([variables['x'][i] for i in df if df[i][c] == l]) - variables[c][l] \
                <= int(n * n_people) + 1
    return model


def extract_distribution_results(variables):
    return [i for i in variables['x'] if variables['x'][i].value() == 1]


def create_similar_population(df, n_people, time_limit):
    model, variables = create_distribution_problem(df, n_people)
    try:
        # New PuLP needs this
        model.solve(solvers.COIN_CMD(msg=1, maxSeconds=time_limit))
    except:
        # Old PuLP needs this
        model.solve(solvers.PULP_CBC_CMD(msg=1, maxSeconds=time_limit))
    allocation = extract_distribution_results(variables)
    quality = get_distribution_solution_quality(allocation, df, variables)
    return allocation, quality


def get_distribution_numerical_solution_quality(allocation, df, numerical):
    quality = dict()
    for v in numerical:
        quality[v] = dict()
        x = [df[a][v] for a in allocation]
        quality[v]['mean'] = abs(mean(x) - numerical[v]['mean']) * 100
        quality[v]['var'] = abs(var(x, quality[v]['mean']) - numerical[v]['var']) * 100
    return quality


def get_distribution_categorical_solution_quality(variables, categorical):
    quality = dict()
    for c in categorical:
        quality[c] = dict()
        for (l, n) in categorical[c]:
            quality[c][l] = variables[c][l].value()
    return quality


def get_distribution_solution_quality(allocation, df, variables):
    quality = {
        'numerical': get_distribution_numerical_solution_quality(allocation,
                                                                 df['entity_data'], df['numerical_data']),
        'categorical': get_distribution_categorical_solution_quality(variables, df['categorical_data'])}
    return quality
