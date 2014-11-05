#
# Example usage of opti-group
#
# Copyright (C) 2014,  Oscar Dowson
#
import dataio
import model

#
# Presently this is restricted to a SQL Server DB. Modify dataio for others.
# Will make this easier in future.  
#

# Set this flag to true if you have data in a database
use_database = False

#
# There should be two tables in your database.
# One containing the entity data, and the other declaring the variables
# as numeric of categorical.
#
# variable_classification_table(Variable, IsCategorical)
#
#   i.e., if variables 1 & 3 are categorical, and variable 2 is numerical,
#   then the following is required:
#
#   Variable    |   IsCategorical
#   ------------------------------
#   variable1   |       1
#   variable2   |       0
#   variable3   |       1
#
#
# entity_data_table(ID, variable1, variable2, variable3)
#
#   ID  |   v1  |   v2  |   v3
#   ------------------------------
#   A01 |   A   |   1.5 |   Z
#   A02 |   B   |   0.5 |   Y
#   BB1 |   AA  |   3.0 |   Z
#

if use_database:
    server = '.'                # location of server. '.' = localhost
    database = 'enggen403'      # name of database
    entity_tab = 'class_data'   # name of entity_classification_table
    class_tab = 'categories'    # name of entity_classification_table
    # dictionary containing data
    data = dataio.getDataFromDB(server, database, entity_tab, class_table)
else:
    f_entity = 'entity_data.txt'    # name of entity_classification_table
    f_class = 'classification.txt'  # name of entity_classification_table
    # dictionary containing data
    data = dataio.getDataFromFlatFiles(f_class, f_entity)


# number of groups to divide into
n_groups = 2

# time limit for optimisation (seconds)
time_limit = 30

#
# Allocation is a dictionary containing entity to group allocations
#   allocation['group-entity'][group] = list of entities in group
#   allocation['entity-group'][entity] = group
#
# Quality is a dictionary containing statistical metrics of solution quality
#
allocation, quality = model.partitionEntities(data, n_groups, time_limit)

