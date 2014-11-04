#
# This program takes a set of entities and divides them into groups
# based on numerical and categorical variables
#
# Copyright (C) 2014,  Oscar Dowson
#
from pulp import *


def createGroups(n_groups, n_entities):
    GROUPS = range(1, n_groups+1)
    # Number of groups with floor(n_entities/n_groups) people
    k = n_groups - int(n_entities - int(n_entities / n_groups) * n_groups)
    group_size = dict()
    for g in GROUPS:
        if g<=k:
            group_size[g] = int(n_entities/n_groups)
        else:
            group_size[g] = int(n_entities/n_groups) + 1
    return GROUPS, group_size


def createVariables(categorical, numerical, tuples):
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
    return(variables)


def createObjectiveFunction(model, variables, categorical, numerical, tuples):
    obj = None
    for v in numerical:
        obj += (variables[v]['mean_max'] - variables[v]['mean_min'])/numerical[v]['mean']
        obj += (variables[v]['var_max'] - variables[v]['var_min'])/numerical[v]['var']
    for c in categorical:
        obj += 1e4 * lpSum([variables[c][i] for i in tuples[c]])
    model += obj
    return model


def addEntityConstraints(model, variables, ENTITIES, GROUPS):
    for e in ENTITIES:
        model += lpSum([variables['x'][(e, g)] for g in GROUPS]) == 1, 'entity_%s' % e
    return model


def addNumericConstraints(model, data, variables, numerical, GROUPS, group_size):
    for g in GROUPS:
        model += lpSum([variables['x'][(i, g)] for i in data]) == group_size[g], '%s' % g
        for v in numerical:
            model += lpSum([data[i][v] * variables['x'][(i, g)] for i in data]) >= group_size[g] * variables[v]['mean_min']
            model += lpSum([data[i][v] * variables['x'][(i, g)] for i in data]) <= group_size[g] * variables[v]['mean_max']
            model += lpSum([pow(data[i][v] - numerical[v]['mean'], 2) * variables['x'][(i, g)] for i in data]) >= group_size[g] * variables[v]['var_min']
            model += lpSum([pow(data[i][v] - numerical[v]['mean'], 2) * variables['x'][(i, g)] for i in data]) <= group_size[g] * variables[v]['var_max']
    return model


def addCategoricalConstraints(model, data, variables, categorical, GROUPS, n_entities, group_size):
    for g in GROUPS:
        for c in categorical:
            for (l, n) in categorical[c]:
                model += lpSum([variables['x'][(i, g)] for i in data if data[i][c]==l]) + variables[c][(l, g)] >= int(n/n_entities * group_size[g])
                model += lpSum([variables['x'][(i, g)] for i in data if data[i][c]==l]) - variables[c][(l, g)] <= int(n/n_entities * group_size[g])+1
    return model    


def createProblem(db_data, n_groups):
    data = db_data['entity_data']
    categorical = db_data['categorical_data']
    numerical = db_data['numerical_data']
    n_entities = len(data)
    ENTITIES = data.keys()
    
    GROUPS, group_size = createGroups(n_groups, n_entities)
    tuples = dict()
    tuples['entity'] = [(e, g) for e in ENTITIES for g in GROUPS]
    for c in categorical:
        tuples[c] = [(i, g) for (i, n) in categorical[c] for g in GROUPS]

    model = LpProblem('Partition', LpMinimize)
    variables = createVariables(categorical, numerical, tuples)
    model = createObjectiveFunction(model, variables, categorical, numerical, tuples)
    model = addEntityConstraints(model, variables, ENTITIES, GROUPS)
    model = addNumericConstraints(model, data, variables, numerical, GROUPS, group_size)
    model = addCategoricalConstraints(model, data, variables, categorical, GROUPS, n_entities, group_size)
    return model, variables


def extractResults(variables):
    allocation = {'entity-group':dict(), 'group-entity':dict()}
    for (e, g) in variables['x']:
        if variables['x'][(e, g)].value() == 1:
            allocation['entity-group'][e] = g
            if allocation['group-entity'].has_key(g):
                allocation['group-entity'][g].append(e)
            else:
                allocation['group-entity'][g] = [e]
    return allocation


def getNumericalSolutionQuality(allocation, data, numerical):
    quality = dict()
    for v in numerical:
        quality[v] = {'mean':{'max':None,'min':None,'mean':None,'sd':None},
                      'var':{'max':None,'min':None,'mean':None,'sd':None}}
        mean_list = list()
        var_list = list()
        for g in allocation['group-entity']:
            values = [data[e][v] for e in allocation['group-entity'][g]]
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


def getCategoricalSolutionQuality(allocation, variables, categorical):
    quality = dict()
    for c in categorical:
        quality[c] = dict()
        for (l, n) in categorical[c]:
            quality[c][l] = {'max':None,'min':None,'mean':None,'sd':None}
            violation_list = [variables[c][(l, g)].value() for g in allocation['group-entity']]
            quality[c][l]['max'] = max(violation_list)
            quality[c][l]['min'] = min(violation_list)
            quality[c][l]['mean'] = mean(violation_list)
            quality[c][l]['sd'] = pow(var(violation_list), 0.5)
    return quality


def getSolutionQuality(allocation, data, variables):
    quality = {'numerical':getNumericalSolutionQuality(allocation, data['entity_data'], data['numerical_data']),
               'categorical':getCategoricalSolutionQuality(allocation, variables, data['categorical_data'])}
    return quality


def mean(x):
    return sum(x)/float(len(x))


def var(x, u=None):
    if u is None:
        u = mean(x)
    return sum([pow(i - u, 2) for i in x])


def createAndRunModel(data, n_groups, time_limit):
    model, variables = createProblem(data, n_groups)
    model.solve(solvers.PULP_CBC_CMD(maxSeconds=time_limit))
    allocation = extractResults(variables)
    quality = getSolutionQuality(allocation, data, variables)
    return allocation, quality    
