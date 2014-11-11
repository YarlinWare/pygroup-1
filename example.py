"""
 Example usage of pygroup

 Copyright (C) 2014,  Oscar Dowson
"""
import pygroup

# ====================================================================================================================
#
#   Example 1:       Partitioning a number of entities into equitable groups
#
#       Data if loaded from the .txt files in the example_files directory
#
# ====================================================================================================================

# filepath to entity data txt file
f_entity = 'example_files/entity_data.txt'

# filepath to classification txt file
f_class = 'example_files/classification.txt'

# Entity data
data1 = pygroup.FlatFile(f_class, f_entity)

# number of groups to divide into
n_groups = 2

# time limit for optimisation (seconds)
time_limit = 5

# Create the partition model
partition_model = pygroup.PartitionModel(data1, n_groups)

# Solve the model
allocation, quality = partition_model.solve(time_limit)

print allocation
print quality

# ====================================================================================================================
#
#   Example 2:      Selecting a subset of a population to match the characteristics of another
#
#       I have a SQL database on my local machine called enggen403
#       It has two tables. These are identical to the two .txt files in the example_files folder
#             1.    categories(Variable, IsCategorical)
#
#                   i.e., if variables 1 & 3 are categorical, and variable 2 is numerical,
#                   then the following is required:
#
#                   Variable    |   IsCategorical
#                   ------------------------------
#                   variable1   |       1
#                   variable2   |       0
#                   variable3   |       1
#
#              2.   class_data(ID, variable1, variable2, variable3)
#
#                   ID  |   v1  |   v2  |   v3
#                   ------------------------------
#                   A01 |   A   |   1.5 |   Z
#                   A02 |   B   |   0.5 |   Y
#                   BB1 |   AA  |   3.0 |   Z
#
# ====================================================================================================================

# location of server. '.' = localhost
server = '.'

# name of database
database = 'enggen403'

# name of entity_classification_table
entity_tab = 'class_data'

# name of entity_classification_table
class_tab = 'categories'

# People in our `control' group
data_a = pygroup.DataBase(server, database, entity_tab, class_tab, where='ID > 200')

# People in our population to select out of
data_b = pygroup.DataBase(server, database, entity_tab, class_tab, where='ID <= 200')

# Number of people to select
n_people = 10

# Time limit for optimisation
time_limit = 60

# Create Model
distribution_model = pygroup.DistributionModel(data_a, data_b, n_people)

# Solve
allocation1, quality1 = distribution_model.solve(time_limit)

print allocation1
print quality1