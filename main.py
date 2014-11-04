import database as db
from pulp import *

def createVariables(variables, tuples):
    prob_variables = dict()
    prob_variables['x'] = LpVariable.dicts('x', tuples['entity'], None, None, LpBinary)
    for v in variables['categorical']:
        prob_variables[v] = LpVariable.dicts('%s_violation' % v, tuples[v], 0, None)
    for v in variables['numerical']:
        prob_variables[v] = dict()
        prob_variables[v]['mean_min'] = LpVariable('%s_mean_min' % v, None, None)
        prob_variables[v]['mean_max'] = LpVariable('%s_mean_max' % v, None, None)
        prob_variables[v]['var_min'] = LpVariable('%s_var_min' % v, 0, None)
        prob_variables[v]['var_max'] = LpVariable('%s_var_max' % v, 0, None)
    return(prob_variables)

def createObjectiveFunction(prob, prob_variables, variables, numerical):
    obj = None
    for v in variables['numerical']:
        obj += (prob_variables[v]['%s_mean_max' % v] - prob_variables[v]['%s_mean_min' % v])/numerical[v]['mean']
        obj += (prob_variables[v]['%s_var_max' % v] - prob_variables[v]['%s_var_min' % v])/numerical[v]['var']

    for v in variables['categorical']:
        obj += lpSum([prob_variables[v][i] for i in tuples[v]])

    prob += obj
    return prob

def addEntityConstraints(prob, ENTITIES, GROUPS, prob_variables):
    for e in ENTITIES:
        prob += lpSum([prob_variables['x'][(e, g)] for g in GROUPS]) == 1, 'entity_%s' % e
    return prob


# =================================================
server = '.'
database = 'enggen403'
con, cursor = db.connectToDatabase(server, database)

# =================================================
variables = db.grabCategories(cursor, 'categories')
data = db.buildDataDictionary(cursor, 'class_data')

categorical = db.getCategoryLevels(cursor, 'class_data', variables)
numerical = db.getNumericalMetrics(cursor, 'class_data', variables)

# =================================================
n_groups = 20
n_entities = len(data)

ENTITIES = [d['ID'] for d in data]
GROUPS = range(1, n_groups+1)

# Number of groups with floor(n_entities/n_groups) people
k = n_groups - int(n_entities - int(n_entities / n_groups) * n_groups)

GROUPS1 = GROUPS[:k+1]
GROUPS2 = GROUPS[k+1:]

tuples['entity'] = [(e, g) for e in ENTITIES for g in GROUPS]
for c in variables['categorical']:
    tuples[c] = [(i, g) for i in categorical[c] for g in GROUPS]
