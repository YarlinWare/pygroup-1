import database as db
from pulp import *


def createGroups(n_groups, n_entities):
    GROUPS = range(1, n_groups+1)
    # Number of groups with floor(n_entities/n_groups) people
    k = n_groups - int(n_entities - int(n_entities / n_groups) * n_groups)
    group_size = dict()
    for g in GROUPS:
        if g<k:
            group_size[g] = int(n_entities/n_groups)
        else:
            group_size[g] = int(n_entities/n_groups) + 1
    return GROUPS, group_size


def createVariables(categorical, numerical, tuples):
    variables = dict()
    variables['x'] = LpVariable.dicts('x', tuples['entity'], None, None, LpBinary)
    for v in categorical:
        variables[v] = LpVariable.dicts('%s_violation' % v, tuples[v], 0, None)
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
    for v in categorical:
        obj += lpSum([variables[v][i] for i in tuples[v]])
    model += obj
    return model


def addEntityConstraints(model, variables, ENTITIES, GROUPS):
    for e in ENTITIES:
        model += lpSum([variables['x'][(e, g)] for g in GROUPS]) == 1, 'entity_%s' % e
    return model


def addNumericConstraints(model, data, variables, numerical, GROUPS, group_size):
    for g in GROUPS:
        model += lpSum([variables['x'][(d['ID'], g)] for d in data]) == group_size[g]
        for v in numerical:
            model += lpSum([d[v]*variables['x'][(d['ID'], g)] for d in data]) >= group_size[g] * variables[v]['mean_min']
            model += lpSum([d[v]*variables['x'][(d['ID'], g)] for d in data]) <= group_size[g] * variables[v]['mean_max']
            model += lpSum([pow(d[v] - numerical[v]['mean'], 2)*variables['x'][(d['ID'], g)] for d in data]) >= group_size[g] * variables[v]['var_min']
            model += lpSum([pow(d[v] - numerical[v]['mean'], 2)*variables['x'][(d['ID'], g)] for d in data]) <= group_size[g] * variables[v]['var_max']
    return model


def addCategoricalConstraints(model, data, variables, categorical, GROUPS, n_entities):
    for g in GROUPS:
        for c in categorical:
            for (l, n) in categorical[c]:
                model += lpSum([variables['x'][(d['ID'], g)] for d in data if d[c]==l]) + variables[c] >= int(n/n_entities)
    return model    


def createProblem(data, categorical, numerical, n_groups):
    n_entities = len(data)
    ENTITIES = [d['ID'] for d in data]
    
    GROUPS, group_size = createGroups(n_groups, n_entities)
    tuples = dict()
    tuples['entity'] = [(e, g) for e in ENTITIES for g in GROUPS]
    for c in categorical:
        tuples[c] = [(i, g) for i in categorical[c] for g in GROUPS]

    model = LpProblem('Partition', LpMinimize)
    variables = createVariables(categorical, numerical, tuples)
    model = createObjectiveFunction(model, variables, categorical, numerical, tuples)
    model = addEntityConstraints(model, variables, ENTITIES, GROUPS)
    model = addNumericConstraints(model, data, variables, numerical, GROUPS, group_size)
    model = addCategoricalConstraints(model, data, variables, categorical, GROUPS, n_entities)

    return model

# =================================================
server = '.'
database = 'enggen403'
con, cursor = db.connectToDatabase(server, database)

# =================================================
classification = db.grabCategories(cursor, 'categories')
entity_data = db.buildDataDictionary(cursor, 'class_data')

categorical = db.getCategoryLevels(cursor, 'class_data', classification)
numerical = db.getNumericalMetrics(cursor, 'class_data', classification)

# =================================================
n_groups = 20

model = createProblem(entity_data, categorical, numerical, n_groups)

model.solve(solvers.PULP_CBC_CMD(keepFiles=1, msg=2, maxSeconds=10))
