import database as db
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
        model += lpSum([variables['x'][(d['ID'], g)] for d in data]) == group_size[g], '%s' % g
        for v in numerical:
            model += lpSum([d[v] * variables['x'][(d['ID'], g)] for d in data]) >= group_size[g] * variables[v]['mean_min']
            model += lpSum([d[v] * variables['x'][(d['ID'], g)] for d in data]) <= group_size[g] * variables[v]['mean_max']
            model += lpSum([pow(d[v] - numerical[v]['mean'], 2) * variables['x'][(d['ID'], g)] for d in data]) >= group_size[g] * variables[v]['var_min']
            model += lpSum([pow(d[v] - numerical[v]['mean'], 2) * variables['x'][(d['ID'], g)] for d in data]) <= group_size[g] * variables[v]['var_max']
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
        tuples[c] = [(i, g) for (i, n) in categorical[c] for g in GROUPS]

    model = LpProblem('Partition', LpMinimize)
    variables = createVariables(categorical, numerical, tuples)
    model = createObjectiveFunction(model, variables, categorical, numerical, tuples)
    model = addEntityConstraints(model, variables, ENTITIES, GROUPS)
    model = addNumericConstraints(model, data, variables, numerical, GROUPS, group_size)
    model = addCategoricalConstraints(model, data, variables, categorical, GROUPS, n_entities)
    return model, variables


def extractResults(variables):
    allocation = dict()
    for (e, g) in variables['x']:
        if variables['x'][(e, g)].value() == 1:
            allocation[e] = g
    return allocation


##def getSolutionQuality(variables, categorical, numerical):
##    quality = {'categorical':dict(), 'numerical':dict()}
##    for c in categorical:
##        max_violation = 0
##        quality['categorical'][c] = dict()
##        for (l, n) in categorical[c]:
##            quality['categorical'][c][l]

def getDataFromDB(server, database, entity_data_table, variable_classification_table):
    con, cursor = db.connectToDatabase(server, database)
    classification = db.grabCategories(cursor, variable_classification_table)
    entity_data = db.buildDataDictionary(cursor, entity_data_table)
    categorical = db.getCategoryLevels(cursor, entity_data_table, classification)
    numerical = db.getNumericalMetrics(cursor, entity_data_table, classification)
    db_data = dict()
    db_data['entity_data'] = entity_data
    db_data['categorical_data'] = categorical
    db_data['numerical_data'] = numerical
    return db_data
    
# =================================================
server = '.'
database = 'enggen403'
entity_data_table = 'class_data'
variable_classification_table = 'categories'

n_groups = 20
time_limit = 10
# =================================================
db_data = getDataFromDB(server, database, entity_data_table, variable_classification_table)
model, variables = createProblem(db_data['entity_data'], db_data['categorical_data'], db_data['numerical_data'], n_groups)
status = model.solve(solvers.PULP_CBC_CMD(maxSeconds=timelimit))

allocation = extractResults(variables)
