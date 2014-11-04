#
# Example usage of opti-group
#
# Copyright (C) 2014,  Oscar Dowson
#
import dataio
import model

server = '.'
database = 'enggen403'
entity_data_table = 'class_data'
variable_classification_table = 'categories'
data = dataio.getDataFromDB(server, database, entity_data_table, variable_classification_table)

n_groups = 23
time_limit = 30

allocation, quality = model.createAndRunModel(data, n_groups, time_limit)
